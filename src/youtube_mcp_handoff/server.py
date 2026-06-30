from __future__ import annotations

import json
from pathlib import Path

from youtube_mcp_handoff import overlay_service
from youtube_mcp_handoff.policy import ALLOWED_READ_ONLY_TOOLS, FORBIDDEN_CAPABILITIES, REQUIRED_USER_FACING_LIMITATIONS

_DEFAULT_OVERLAY: Path | None = None


def _resolve_overlay_path(overlay_path: str | Path | None) -> Path:
    if overlay_path is not None:
        return Path(overlay_path)
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "examples" / "synthetic_overlay_demo" / "operator_overlay.json"


def _wrap_with_guard(data: dict, overlay: dict) -> dict:
    limitations = overlay.get("limitations", [])
    policy = overlay.get("policy", {})
    answer_text = json.dumps(data, ensure_ascii=False)
    answer_text += "\n\nLimitations: " + ", ".join(limitations)
    answer_text += "\n\nThis is a synthetic fixture. " \
                   "Caption fragment claim risk applies. " \
                   "Not truth-ranked. Not fact-checked."
    from youtube_mcp_handoff.answer_guard import validate_public_demo_answer, validate_public_demo_answer_payload
    guard_errors = validate_public_demo_answer(answer_text)
    data["limitations_display"] = limitations
    data["policy_display"] = policy
    guard_errors.extend(validate_public_demo_answer_payload({"answer": answer_text, "limitations": limitations}))
    if guard_errors:
        return {"ok": False, "error": "answer_guard_violation", "violations": guard_errors}
    return data


def mcp_overlay_summary(overlay_path: str | Path | None = None) -> dict:
    path = _resolve_overlay_path(overlay_path)
    overlay = overlay_service.load_operator_overlay(path)
    data = overlay_service.overlay_summary(overlay)
    return _wrap_with_guard(data, overlay)


def mcp_overlay_groups(overlay_path: str | Path | None = None) -> dict:
    path = _resolve_overlay_path(overlay_path)
    overlay = overlay_service.load_operator_overlay(path)
    data = overlay_service.overlay_groups(overlay)
    return _wrap_with_guard(data, overlay)


def mcp_overlay_group_detail(overlay_group_id: str, overlay_path: str | Path | None = None) -> dict:
    path = _resolve_overlay_path(overlay_path)
    overlay = overlay_service.load_operator_overlay(path)
    data = overlay_service.overlay_group_detail(overlay, overlay_group_id)
    return _wrap_with_guard(data, overlay)


def mcp_overlay_limitations(overlay_path: str | Path | None = None) -> dict:
    path = _resolve_overlay_path(overlay_path)
    overlay = overlay_service.load_operator_overlay(path)
    data = overlay_service.overlay_limitations(overlay)
    return _wrap_with_guard(data, overlay)


def get_mcp_tool_manifest() -> dict:
    return {
        "schema_version": "public_ai_app_mcp_handoff_manifest.v1",
        "server_name": "youtube_intel_public_opinion_terrain_mcp",
        "topic_id": "synthetic_opinion_terrain_demo_v1",
        "status": "PUBLIC_SYNTHETIC_DEMO_READY",
        "transport_note": "MCP-ready read-only handoff facade with a minimal JSON-RPC stdio server for local smoke testing",
        "tools": [
            {"name": "overlay.summary", "read_only": True},
            {"name": "overlay.groups", "read_only": True},
            {"name": "overlay.group_detail", "read_only": True, "params": ["overlay_group_id"]},
            {"name": "overlay.limitations", "read_only": True},
        ],
        "forbidden_capabilities": list(FORBIDDEN_CAPABILITIES),
        "required_user_facing_limitations": list(REQUIRED_USER_FACING_LIMITATIONS),
    }
