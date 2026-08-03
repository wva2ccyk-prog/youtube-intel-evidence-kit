from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules"}

# Fallback-only extension allowlist (used when Git metadata is unavailable).
# The preferred path scans ALL Git-tracked text files regardless of extension,
# including .env*, .sh, .ini, .cfg, .jsonl, .html, and extensionless configs.
TARGET_EXTENSIONS = {
    ".py", ".md", ".json", ".toml", ".txt", ".yaml", ".yml",
    ".env", ".sh", ".ini", ".cfg", ".jsonl", ".html",
}

FORBIDDEN_PATH_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

FORBIDDEN_SUFFIXES = {
    ".pyc",
    ".pyo",
}

_SELF_PATH = Path(__file__).resolve()
_TEST_LEAK_PATH = _SELF_PATH.parents[1] / "tests" / "test_public_release_leak_scan.py"

LOCAL_DENYLIST_FILENAMES = [
    ".release_private_denylist.local",
    "private_denylist.local",
]

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    ("C:\\Users\\", "windows_user_path"),
    ("@gmail.com", "private_email"),
    ("OPENAI_API_KEY", "api_key_reference"),
    ("pilot_runs/", "private_pilot_reference"),
    ("browser session", "session_reference"),
    ("refresh_token", "token_reference"),
    ("access_token", "token_reference"),
    ("bearer_token", "token_reference"),
    ("cookie", "cookie_reference"),
]

# api keyword assignment in any spacing/quoting shape, e.g. api_key=, api-key :
API_KEY_ASSIGNMENT_RE = re.compile(r"\bapi[_-]?key\b\s*[=:]\s*[\"']?[^\s\"',;]+", re.IGNORECASE)


def _load_local_denylist(root: Path) -> list[tuple[str, str]]:
    patterns: list[tuple[str, str]] = []
    for fname in LOCAL_DENYLIST_FILENAMES:
        p = root / fname
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append((line, "local_denylist"))
    return patterns


def _git_tracked_files(root: Path) -> list[Path] | None:
    """Return Git-tracked files (``git ls-files -z``), or None when Git
    metadata is unavailable so the caller falls back to a full-tree scan."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            text=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [root / p for p in proc.stdout.decode("utf-8", errors="replace").split("\0") if p]


def _fallback_files(root: Path) -> list[Path]:
    """Full-tree scan used only when Git metadata is unavailable.

    Scans every file with a text-like extension from the fallback allowlist,
    plus extensionless files (configuration files such as ``.gitignore``,
    ``Dockerfile``, ``Makefile``). Binary files are filtered later by the NUL
    check in :func:`scan_file`.
    """
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        suffix = p.suffix.lower()
        if suffix not in TARGET_EXTENSIONS and suffix not in FORBIDDEN_SUFFIXES and suffix != "":
            continue
        # FORBIDDEN_PATH_PARTS / FORBIDDEN_SUFFIXES paths are intentionally
        # NOT filtered here: scan_repo's main loop turns them into
        # generated-artifact violations instead of silently skipping them.
        files.append(p)
    return files


def scan_file(path: Path, extra_patterns: list[tuple[str, str]] | None = None) -> list[str]:
    violations: list[str] = []
    try:
        raw = path.read_bytes()
    except OSError:
        return violations
    if b"\x00" in raw[:8192]:
        # Binary file: not a text scan target. The NUL check is the ONLY
        # reason a file is skipped; a failed UTF-8 decode never is.
        return violations
    text = raw.decode("utf-8", errors="replace")
    all_patterns = FORBIDDEN_PATTERNS + (extra_patterns or [])
    for line_num, line in enumerate(text.splitlines(), 1):
        for pattern, label in all_patterns:
            if pattern.lower() in line.lower():
                violations.append(f"{path}:{line_num}: [{label}] {pattern}")
        if API_KEY_ASSIGNMENT_RE.search(line):
            violations.append(f"{path}:{line_num}: [api_key_assignment] api-key assignment")
    return violations


def scan_repo(root: Path) -> list[str]:
    root = Path(root)
    all_violations: list[str] = []
    skip_files = {_SELF_PATH.resolve(), _TEST_LEAK_PATH.resolve()}
    extra_patterns = _load_local_denylist(root)
    denylist_paths = {(root / fname).resolve() for fname in LOCAL_DENYLIST_FILENAMES}

    tracked = _git_tracked_files(root)
    if tracked is None:
        files = _fallback_files(root)
    else:
        files = tracked
        # Local denylist files must never be committed: if Git tracks one,
        # fail the scan so the secret-bearing pattern file cannot ship.
        tracked_resolved = {f.resolve() for f in tracked}
        for fname in LOCAL_DENYLIST_FILENAMES:
            if (root / fname).resolve() in tracked_resolved:
                all_violations.append(
                    f"{root / fname}: [local_denylist] local denylist file is tracked by "
                    f"git; add it to .gitignore instead"
                )

    for p in sorted(files):
        resolved = p.resolve()
        if resolved in skip_files or resolved in denylist_paths:
            continue
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part in FORBIDDEN_PATH_PARTS for part in parts):
            all_violations.append(f"{p}: [generated_artifact] path contains forbidden part")
            continue
        if p.suffix.lower() in FORBIDDEN_SUFFIXES:
            all_violations.append(f"{p}: [generated_artifact] forbidden suffix {p.suffix}")
            continue
        all_violations.extend(scan_file(p, extra_patterns))
    return all_violations


def main(root: Path | None = None) -> int:
    if root is None:
        root = Path(__file__).resolve().parents[1]
    violations = scan_repo(root)
    if violations:
        print(f"LEAK SCAN FAILED: {len(violations)} violation(s) found\n")
        for v in violations:
            print(f"  {v}")
        return 1
    print("LEAK SCAN PASSED: no violations found")
    return 0


if __name__ == "__main__":
    root_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    raise SystemExit(main(root_arg))
