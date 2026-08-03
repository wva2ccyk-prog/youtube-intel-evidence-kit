"""P1-H: packaged fixtures must stay in byte-for-byte sync with the
human-facing repository-root ``examples/`` tree (one canonical fixture source),
and fixture resolution must work from both a source checkout and an installed
package.
"""

from __future__ import annotations

from pathlib import Path

from youtube_intel._fixtures import fixture_path, is_installed_package, is_source_checkout

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGED_ROOT = Path(__file__).resolve().parents[1] / "src" / "youtube_intel" / "_fixtures"

# Files that are intentionally allowed to differ (e.g. READMEs are not copied).
_DIFF_ALLOWED = {"README.md", "__init__.py"}


def _relative(target: Path) -> list[Path]:
    return sorted(p.relative_to(target) for p in target.rglob("*") if p.is_file())


def _relative_examples(target: Path) -> list[Path]:
    """Return example files that should have a packaged counterpart.

    Files in example subdirectories that are extracted into the flat packaged
    tree (e.g. ``synthetic_overlay_demo/operator_overlay.json`` stored as
    ``operator_overlay.json``) are mapped to their basename.
    """
    files: list[Path] = []
    for p in sorted(target.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(target)
        if rel.parts[-1] in _DIFF_ALLOWED:
            continue
        # Flatten one-level-deep example subdirs if the file is directly
        # present in the packaged tree by its basename.
        flat = PACKAGED_ROOT / rel.parts[-1]
        if len(rel.parts) > 1 and flat.is_file():
            files.append(Path(rel.parts[-1]))
        else:
            files.append(rel)
    return files


def test_packaged_fixtures_match_examples_byte_for_byte() -> None:
    import hashlib

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    for rel in _relative_examples(REPO_ROOT / "examples"):
        # 1) Direct path: examples/<rel> (top-level files and preserved
        #    subdirectory trees like topic_demo/video_a.json).
        examples_path = REPO_ROOT / "examples" / rel
        if not examples_path.is_file() and len(rel.parts) == 1:
            # 2) Flattened single-part name: search example subdirectories
            #    (e.g. synthetic_overlay_demo/operator_overlay.json).
            examples_path = next(
                (REPO_ROOT / "examples" / sub / rel.parts[0])
                for sub in sorted((REPO_ROOT / "examples").iterdir())
                if sub.is_dir() and (sub / rel.parts[0]).is_file()
            )
        packaged_path = PACKAGED_ROOT / rel
        assert packaged_path.is_file(), f"packaged fixture missing: {rel}"
        assert digest(examples_path) == digest(packaged_path), (
            f"packaged fixture differs from examples/: {rel}  ({examples_path} vs {packaged_path})"
        )
    # The packaged tree must not contain stale files absent from examples/.
    examples_files: set[Path] = {
        p.relative_to(REPO_ROOT / "examples")
        for p in (REPO_ROOT / "examples").rglob("*")
        if p.is_file()
    }
    examples_basenames: set[str] = {p.name for p in examples_files}
    for rel in _relative(PACKAGED_ROOT):
        if rel.parts[-1] in _DIFF_ALLOWED or "__pycache__" in rel.parts:
            continue
        assert rel.parts[-1] in examples_basenames, f"packaged fixture not in examples/: {rel}"


def test_fixture_path_resolves_examples_in_source_checkout() -> None:
    # In a source checkout the repository-root examples/ dir must exist.
    assert (REPO_ROOT / "examples").is_dir()
    path = fixture_path("synthetic_segments.json")
    assert Path(path).is_file()


def test_fixture_path_reports_runtime_mode() -> None:
    # In the test environment (source checkout) we expect at least one of the
    # mode helpers to resolve; both may be true when running from a checkout
    # with the package importable.
    assert is_source_checkout() or is_installed_package()
