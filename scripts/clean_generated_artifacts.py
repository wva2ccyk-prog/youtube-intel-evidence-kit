from __future__ import annotations

"""Remove generated build/test artifacts from the package tree.

This keeps the public release leak scan and the committed source tree
self-consistent: bytecode caches, pytest/mypy/ruff caches, build outputs, and
egg-info are never part of the published source, so CI removes them before the
release leak scan runs. The scan itself still rejects these artifacts if they
somehow reappear; this script only ensures a clean starting tree.
"""

import shutil
import sys
from pathlib import Path

CACHE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

BUILD_DIR_NAMES = {
    "dist",
    "build",
}

CACHE_SUFFIXES = {".pyc", ".pyo"}


def clean(root: Path) -> list[str]:
    root = root.resolve()
    removed: list[str] = []
    # Remove cache/build directories anywhere under the root.
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue
        resolved = path.resolve()
        if not str(resolved).startswith(str(root)):
            continue
        if path.is_dir() and (
            path.name in CACHE_DIR_NAMES
            or path.name in BUILD_DIR_NAMES
            or path.name.endswith(".egg-info")
        ):
            shutil.rmtree(path, ignore_errors=True)
            removed.append(str(path.relative_to(root)))
        elif path.is_file() and path.suffix.lower() in CACHE_SUFFIXES:
            path.unlink(missing_ok=True)
            removed.append(str(path.relative_to(root)))
    return removed


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    removed = clean(root)
    if removed:
        print(f"Cleaned {len(removed)} generated artifact(s):")
        for item in removed:
            print(f"  - {item}")
    else:
        print("No generated artifacts found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
