"""Strict structural validation for residual package dictionaries.

A shared, neutral validator used by the handoff bundle writer and the analysis
``worth`` command so an arbitrary or malformed object can never become a
plausible successful artifact. It requires the expected schema version, a
non-empty video identity (video_id / title / language), and a non-empty list of
claim candidates, each an object with a non-empty claim_id and text (duplicates
rejected, reserved fallback identities rejected).
"""

from __future__ import annotations

from typing import Any

RESERVED_FALLBACK_IDS = {"unknown-video", "unknown-evidence", "unknown-claim", "unknown-group"}
PACKAGE_SCHEMA_VERSION = "youtube_residual_v0.1"


def _text(value: Any, default: str = "") -> str:
    return str(value if value not in (None, "") else default)


def validate_residual_package_dict(package: Any) -> list[str]:
    """Return structural issues for a residual package dictionary.

    Returns an empty list only when the package is structurally valid.
    """
    issues: list[str] = []
    if not isinstance(package, dict):
        return ["package_not_object"]
    if package.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        issues.append(
            f"package schema_version mismatch: expected {PACKAGE_SCHEMA_VERSION!r}, "
            f"got {_text(package.get('schema_version'), '<missing>')!r}"
        )
    video = package.get("video")
    if not isinstance(video, dict) or not video:
        issues.append("package.video is missing or empty")
    else:
        video_id = _text(video.get("video_id"))
        title = _text(video.get("title"))
        language = _text(video.get("language"))
        if not video_id:
            issues.append("package.video.video_id is empty")
        elif video_id in RESERVED_FALLBACK_IDS:
            issues.append(f"package.video.video_id uses reserved fallback id: {video_id!r}")
        if not title:
            issues.append("package.video.title is empty")
        if not language:
            issues.append("package.video.language is empty")
    claims = package.get("claim_candidates")
    if not isinstance(claims, list) or not claims:
        issues.append("package.claim_candidates is empty or not a list")
        return issues
    seen_ids: set[str] = set()
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            issues.append(f"package.claim_candidates[{i}] is not an object")
            continue
        cid = _text(claim.get("claim_id"))
        text = _text(claim.get("text"))
        if not cid:
            issues.append(f"package.claim_candidates[{i}] has empty claim_id")
        elif cid in seen_ids:
            issues.append(f"duplicate claim_id in package: {cid!r}")
        else:
            seen_ids.add(cid)
        if not text:
            issues.append(f"package.claim_candidates[{i}] has empty text")
    return issues


def assert_valid_residual_package_dict(
    package: Any,
    *,
    label: str,
) -> dict[str, Any]:
    """Validate a residual package and return it, raising on structural issues."""
    from .errors import InvalidInputError

    issues = validate_residual_package_dict(package)
    if issues:
        raise InvalidInputError(
            f"{label} is not a valid residual package: " + "; ".join(issues[:8])
        )
    return package