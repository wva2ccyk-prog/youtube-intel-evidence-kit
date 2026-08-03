"""Strict structural validation for residual package dictionaries.

A shared, neutral validator used by the handoff bundle writer and the analysis
``worth`` command so an arbitrary or malformed object can never become a
plausible successful artifact. It requires the expected schema version, a
non-empty video identity (video_id / title / language), and a non-empty list of
claim candidates, each an object with a non-empty claim_id and text (duplicates
rejected, reserved fallback identities rejected).

Identity and required text fields are validated with strict type checks: a
value must actually be a ``str`` and non-empty after stripping. Generic string
coercion via ``str()`` is never used for identity or required text, so values
such as ``123``, ``{}``, ``[]``, ``true`` or whitespace-only strings are
rejected rather than silently normalized. Duplicate and reserved-ID checks use
the stripped normalized value.
"""

from __future__ import annotations

from typing import Any

RESERVED_FALLBACK_IDS = {"unknown-video", "unknown-evidence", "unknown-claim", "unknown-group"}
PACKAGE_SCHEMA_VERSION = "youtube_residual_v0.1"


def _required_nonempty_string(
    value: Any,
    *,
    field: str,
    issues: list[str],
) -> str | None:
    """Return the stripped value when ``value`` is a non-empty string.

    Non-string types and whitespace-only strings are reported as issues and
    return ``None``. Never coerces via ``str()``.
    """
    if not isinstance(value, str):
        issues.append(f"{field} must be a string")
        return None
    normalized = value.strip()
    if not normalized:
        issues.append(f"{field} is empty")
        return None
    return normalized


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
            f"got {package.get('schema_version', '<missing>')!r}"
        )
    video = package.get("video")
    if not isinstance(video, dict) or not video:
        issues.append("package.video is missing or empty")
    else:
        video_id = _required_nonempty_string(video.get("video_id"), field="package.video.video_id", issues=issues)
        if video_id and video_id in RESERVED_FALLBACK_IDS:
            issues.append(f"package.video.video_id uses reserved fallback id: {video_id!r}")
        _required_nonempty_string(video.get("title"), field="package.video.title", issues=issues)
        _required_nonempty_string(video.get("language"), field="package.video.language", issues=issues)
    claims = package.get("claim_candidates")
    if not isinstance(claims, list) or not claims:
        issues.append("package.claim_candidates is empty or not a list")
        return issues
    seen_ids: set[str] = set()
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            issues.append(f"package.claim_candidates[{i}] is not an object")
            continue
        cid = _required_nonempty_string(
            claim.get("claim_id"), field=f"package.claim_candidates[{i}].claim_id", issues=issues
        )
        if cid is None:
            # The generic helper already reported the strict type/emptiness issue;
            # keep a compatible wording for the empty case.
            if not isinstance(claim.get("claim_id"), str):
                pass  # already reported as "must be a string"
            else:
                issues.append(f"package.claim_candidates[{i}] has empty claim_id")
        elif cid in RESERVED_FALLBACK_IDS:
            issues.append(f"package.claim_candidates[{i}].claim_id uses reserved fallback id: {cid!r}")
        elif cid in seen_ids:
            issues.append(f"duplicate claim_id in package: {cid!r}")
        else:
            seen_ids.add(cid)
        if _required_nonempty_string(
            claim.get("text"), field=f"package.claim_candidates[{i}].text", issues=issues
        ) is None and isinstance(claim.get("text"), str):
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