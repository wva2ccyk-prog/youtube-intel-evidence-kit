from __future__ import annotations

ALLOWED_READ_ONLY_TOOLS: tuple[str, ...] = (
    "overlay.summary",
    "overlay.groups",
    "overlay.group_detail",
    "overlay.limitations",
)

FORBIDDEN_CAPABILITIES: tuple[str, ...] = (
    "truth_judgment",
    "fact_check",
    "truth_ranking",
    "conflict_relation_creation",
    "topic_collection_mutation",
    "vkr_mutation",
    "overlay_mutation",
    "canonical_pointer_change",
)

REQUIRED_USER_FACING_LIMITATIONS: tuple[str, ...] = (
    "synthetic fixture only",
    "caption fragment claim risk",
    "not truth-ranked",
    "not fact-checked",
)


def validate_requested_tool(tool_name: str) -> list[str]:
    errors: list[str] = []
    if tool_name not in ALLOWED_READ_ONLY_TOOLS:
        errors.append(f"tool_not_allowed:{tool_name}")
    return errors


def _walk_values(value: object):
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _walk_values(v)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_values(item)
    else:
        yield str(value)


def validate_no_forbidden_capabilities(request: dict) -> list[str]:
    errors: list[str] = []
    seen = set(_walk_values(request))
    for cap in FORBIDDEN_CAPABILITIES:
        if cap in seen:
            errors.append(f"forbidden_capability:{cap}")
    return errors
