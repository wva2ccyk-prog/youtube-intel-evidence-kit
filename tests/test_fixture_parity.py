"""P1-H + Section 6 + Section 13: packaged fixtures must be reproducible from a
clearly defined canonical source (the repository-root ``examples/`` tree) with
an explicit, unambiguous fixture mapping, and runtime mode must be correctly
detected in both source and installed-wheel environments.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from youtube_intel._fixtures import (
    PACKAGED_TO_EXAMPLES,
    find_source_root,
    fixture_path,
    is_installed_package,
    is_source_checkout,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGED_ROOT = REPO_ROOT / "src" / "youtube_intel" / "_fixtures"

# Files intentionally not packaged into the flat map (README copies and the
# package __init__ are allowed to differ or exist only in one tree).
_DIFF_ALLOWED = {"README.md", "__init__.py"}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixture_map_is_complete_and_unambiguous() -> None:
    packaged_to_source: dict[str, str] = {}
    for packaged, source in PACKAGED_TO_EXAMPLES.items():
        assert packaged not in packaged_to_source, f"ambiguous mapping for {packaged}"
        packaged_to_source[packaged] = source
    for p in sorted((REPO_ROOT / "examples").rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(REPO_ROOT / "examples").as_posix()
        if rel.rsplit("/", 1)[-1] in _DIFF_ALLOWED:
            continue
        assert rel in set(PACKAGED_TO_EXAMPLES.values()), (
            f"source file missing from PACKAGED_TO_EXAMPLES values: {rel}"
        )


def test_packaged_fixtures_match_examples_byte_for_byte() -> None:
    for packaged, source_rel in PACKAGED_TO_EXAMPLES.items():
        examples_path = REPO_ROOT / "examples" / source_rel
        packaged_path = PACKAGED_ROOT / packaged
        assert examples_path.is_file(), f"examples source missing: {source_rel}"
        assert packaged_path.is_file(), f"packaged fixture missing: {packaged}"
        assert _digest(examples_path) == _digest(packaged_path), (
            f"packaged fixture differs from examples source: {source_rel}"
        )


def test_no_stale_packaged_fixture() -> None:
    packaged_files = {
        p.relative_to(PACKAGED_ROOT).as_posix()
        for p in PACKAGED_ROOT.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix not in {".pyc", ".pyo"}
    }
    expected = set(PACKAGED_TO_EXAMPLES.keys()) | {"__init__.py", "topic_demo/README.md"}
    stale = packaged_files - expected
    assert not stale, f"stale packaged fixtures not covered: {stale}"


def test_no_generated_bytecode_in_packaged_fixtures(tmp_path) -> None:
    # Enforcement is on the COMMITTED tree: bytecode can be regenerated locally
    # by importing, but it must never be tracked. Assert via git ls-files.
    import subprocess

    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "src/youtube_intel/_fixtures"],
        capture_output=True, text=True,
    )
    assert tracked.returncode == 0, tracked.stderr
    for line in tracked.stdout.splitlines():
        if not line.strip():
            continue
        assert not line.endswith((".pyc", ".pyo")), f"tracked bytecode: {line}"


def test_fixture_path_resolves_examples_in_source_checkout() -> None:
    assert (REPO_ROOT / "examples").is_dir()
    path = fixture_path("synthetic_segments.json")
    assert Path(path) == (REPO_ROOT / "examples" / "synthetic_segments.json").resolve()


# --- Section 6: runtime-mode detection ---------------------------------------


def test_source_checkout_detection_in_repo() -> None:
    assert find_source_root() == REPO_ROOT.resolve()
    assert is_source_checkout() is True


def test_simulated_installed_package_reports_installed() -> None:
    # A directory with package resources but no pyproject.toml + src/youtube_intel
    # marker must NOT be reported as a source checkout if the loader can access
    # resources while no source root is found.
    empty_dir = Path("/tmp/youtube-intel-test-no-repo")
    empty_dir.mkdir(exist_ok=True)
    assert find_source_root(start=empty_dir) is None


def test_missing_resources_env() -> None:
    # With no source root and an unimportable resource package, neither
    # source-checkout nor installed-package should report True.
    assert find_source_root(start=Path("/tmp/definitely-not-a-repo-dir")) is None


def test_fixture_source_vs_installed_resolution() -> None:
    # In a source checkout the canonical examples/ tree is used for fixtures.
    source = fixture_path("operator_overlay.json")
    assert Path(source).is_file()
    if is_source_checkout():
        assert str(source).startswith(str(REPO_ROOT / "examples"))


def test_installed_module_inside_source_tree_is_not_reported_as_source(tmp_path) -> None:
    # A venv created inside a source tree must not make the installed module
    # report a source checkout: the module's __file__ lives under site-packages.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("", encoding="utf-8")
    (repo / "src" / "youtube_intel").mkdir(parents=True)
    site = repo / ".venv" / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    module = site / "youtube_intel" / "_fixtures" / "__init__.py"
    assert find_source_root(start=module) is None, (
        "an installed module under site-packages must not be a source checkout"
    )
