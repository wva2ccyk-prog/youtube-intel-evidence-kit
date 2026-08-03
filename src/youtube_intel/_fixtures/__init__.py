"""Package resource paths for default synthetic fixtures.

Keeps one canonical fixture source: the repository-root ``examples/`` tree in a
source checkout, and the packaged copies under ``src/youtube_intel/_fixtures/``
in an installed wheel. Runtime mode is disambiguated by a repository-root
marker (``pyproject.toml`` + ``src/youtube_intel``), never by assuming a parent
index beneath this file, so an installed module path can never be mistaken for
a source checkout.
"""

from __future__ import annotations

import importlib.resources as _resources
from pathlib import Path
from typing import Union


_SELF = Path(__file__).resolve()

# Explicit mapping from packaged fixture name (as used by demo commands) to the
# canonical repository-root examples/ relative path. Two packaged names must
# never resolve to ambiguous basenames; this map is the single source of truth
# for that mapping and is enforced by tests/test_fixture_parity.py.
PACKAGED_TO_EXAMPLES: dict[str, str] = {
    "synthetic_hesitation.json": "synthetic_hesitation.json",
    "synthetic_package.json": "synthetic_package.json",
    "synthetic_segments.json": "synthetic_segments.json",
    "synthetic_transcript.vtt": "synthetic_transcript.vtt",
    "operator_overlay.json": "synthetic_overlay_demo/operator_overlay.json",
    "release_readiness_report.json": "synthetic_overlay_demo/release_readiness_report.json",
    "topic_demo/expected_groupings.json": "topic_demo/expected_groupings.json",
    "topic_demo/video_a.json": "topic_demo/video_a.json",
    "topic_demo/video_b.json": "topic_demo/video_b.json",
    "topic_demo/video_c.json": "topic_demo/video_c.json",
}


def find_source_root(start: Union[str, Path, None] = None) -> Path | None:
    """Return the repository root containing this source tree, or None.

    Walks upward from the module path and returns the first ancestor that
    contains both ``pyproject.toml`` and ``src/youtube_intel``. Returns None for
    an installed wheel (where the module lives inside site-packages) so
    source-checkout detection is unambiguous.
    """
    current = Path(start or _SELF).resolve()
    candidates = [current.parent, *current.parents]
    for parent in candidates:
        if (
            (parent / "pyproject.toml").is_file()
            and (parent / "src" / "youtube_intel").is_dir()
        ):
            return parent
    return None


def fixture_path(name: str) -> Path:
    """Return a Path to a fixture.

    A detected source checkout resolves the canonical repository-root
    ``examples/`` file via :data:`PACKAGED_TO_EXAMPLES`. An installed package
    (or a name with no source mapping) falls back to ``youtube_intel._fixtures``
    package data.
    """
    root = find_source_root()
    if root is not None:
        examples_rel = PACKAGED_TO_EXAMPLES.get(name)
        if examples_rel:
            examples = root / "examples" / examples_rel
            if examples.is_file():
                return examples
    return Path(_resources.files("youtube_intel._fixtures").joinpath(name))


def fixture_exists(name: str) -> bool:
    try:
        return fixture_path(name).exists()
    except (ModuleNotFoundError, TypeError, OSError):
        return False


def is_source_checkout() -> bool:
    """True when running from a git source checkout (not an installed wheel)."""
    return find_source_root() is not None


def is_installed_package() -> bool:
    """True when the package is installed and resources are accessible but no
    source checkout marker exists (so an installed wheel cannot be reported as
    a source checkout)."""
    if find_source_root() is not None:
        return False
    try:
        _resources.files("youtube_intel._fixtures")
        return True
    except (ModuleNotFoundError, TypeError, AttributeError):
        return False
