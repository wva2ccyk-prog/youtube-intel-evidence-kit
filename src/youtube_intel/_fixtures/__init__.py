"""Package resource paths for default synthetic fixtures.

Keeps one canonical fixture source (``examples/`` in the source tree,
``src/youtube_intel/_fixtures/`` in the installed wheel). All demo commands
and MCP defaults resolve through this module so they work identically from a
source checkout and from a wheel installation.
"""

from __future__ import annotations

import importlib.resources as _resources
from pathlib import Path


def fixture_path(name: str) -> Path:
    """Return a Path to a packaged fixture.

    When the package is installed (wheel), the fixture is loaded from
    ``youtube_intel._fixtures`` package data. When running from a source
    checkout, the same file is resolved from the repository-root ``examples/``
    directory so both modes use the same canonical source.
    """
    try:
        return Path(_resources.files("youtube_intel._fixtures").joinpath(name))
    except (ModuleNotFoundError, TypeError, AttributeError):
        return Path(__file__).resolve().parents[2] / "examples" / name


def fixture_exists(name: str) -> bool:
    try:
        return fixture_path(name).exists()
    except (ModuleNotFoundError, TypeError, OSError):
        return False


def is_source_checkout() -> bool:
    """True when running from a git source checkout (not an installed wheel)."""
    examples = Path(__file__).resolve().parents[2] / "examples"
    return examples.is_dir()


def is_installed_package() -> bool:
    """True when the package is installed and its resources are accessible."""
    try:
        _resources.files("youtube_intel._fixtures")
        return True
    except (ModuleNotFoundError, TypeError, AttributeError):
        return False
