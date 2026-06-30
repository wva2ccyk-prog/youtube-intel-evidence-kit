from __future__ import annotations

from pathlib import Path

TARGET_EXTENSIONS = {
    ".md", ".py", ".json", ".yaml", ".yml", ".toml", ".txt"
}

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache",
    ".youtube_intel", "codex_state", "outputs", "smoke_outputs",
}

def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS or part.startswith("outputs_") or part.startswith("tmp_thread") for part in path.parts)

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failed: list[str] = []

    for path in root.rglob("*"):
        if should_skip(path):
            continue
        if not path.is_file() or path.suffix.lower() not in TARGET_EXTENSIONS:
            continue

        data = path.read_bytes()
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            failed.append(str(path.relative_to(root)))

    if failed:
        print("Encoding check failed. These files are not valid UTF-8 or UTF-8-SIG:")
        for item in failed:
            print(f"- {item}")
        return 1

    print("Encoding check passed. All target files decode as UTF-8 or UTF-8-SIG.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
