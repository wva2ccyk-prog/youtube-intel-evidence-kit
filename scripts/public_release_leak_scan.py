from __future__ import annotations

import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules"}
TARGET_EXTENSIONS = {".py", ".md", ".json", ".toml", ".txt", ".yaml", ".yml"}

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
    ("pilot_runs", "private_pilot_reference"),
    ("browser session", "session_reference"),
    ("refresh_token", "token_reference"),
    ("access_token", "token_reference"),
    ("bearer_token", "token_reference"),
    ("cookie", "cookie_reference"),
]

API_KEY_ASSIGNMENT_PATTERNS = [
    "api_key=",
    "api_key:",
    '"api_key"',
    "'api_key'",
    "API_KEY=",
    "API_KEY:",
]


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


def scan_file(path: Path, extra_patterns: list[tuple[str, str]] | None = None) -> list[str]:
    violations: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return violations
    all_patterns = FORBIDDEN_PATTERNS + (extra_patterns or [])
    for line_num, line in enumerate(text.splitlines(), 1):
        for pattern, label in all_patterns:
            if pattern.lower() in line.lower():
                violations.append(f"{path}:{line_num}: [{label}] {pattern}")
        for pat in API_KEY_ASSIGNMENT_PATTERNS:
            if pat in line:
                violations.append(f"{path}:{line_num}: [api_key_assignment] {pat}")
                break
    return violations


def scan_repo(root: Path) -> list[str]:
    all_violations: list[str] = []
    skip_files = {_SELF_PATH, _TEST_LEAK_PATH}
    extra_patterns = _load_local_denylist(root)
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.resolve() in skip_files:
            continue
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        if any(part in FORBIDDEN_PATH_PARTS for part in parts):
            all_violations.append(f"{p}: [generated_artifact] path contains forbidden part")
            continue
        if p.suffix.lower() in FORBIDDEN_SUFFIXES:
            all_violations.append(f"{p}: [generated_artifact] forbidden suffix {p.suffix}")
            continue
        if p.suffix.lower() not in TARGET_EXTENSIONS:
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
    import sys as _sys
    root_arg = Path(_sys.argv[1]) if len(_sys.argv) > 1 else None
    raise SystemExit(main(root_arg))
