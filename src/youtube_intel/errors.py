"""Structured failure types for expected input and integrity errors.

The CLI contract is: expected input failures (missing, empty, malformed, or
internally inconsistent evidence) are raised as ``InvalidInputError`` and
rendered as structured JSON with exit code 2 -- never an unhandled traceback
and never a misleading ``ok: true`` artifact. Programming errors are NOT
wrapped by this type; only explicitly-raised expected failures use it.
"""

from __future__ import annotations


class InvalidInputError(Exception):
    """Raised when an input is missing, empty, malformed, or inconsistent.

    Used by library entry points (topic-demo, package, worth, handoff,
    hesitation-demo, MCP facades, clean) so the CLI can fail closed with a
    structured ``{"ok": false, "error": "InvalidInputError", ...}`` response.
    """


class EvidenceIntegrityError(InvalidInputError):
    """Raised when identifiers or references are duplicated, empty, or dangling.

    Subtype of :class:`InvalidInputError` so the CLI renders it the same way
    while callers can still distinguish integrity failures programmatically.
    """
