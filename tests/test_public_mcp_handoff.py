from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_MCP = REPO_ROOT / "docs" / "mcp_handoff"
OVERLAY_PATH = REPO_ROOT / "examples" / "synthetic_overlay_demo" / "operator_overlay.json"


def test_docs_ai_app_mcp_handoff_exists():
    assert (DOCS_MCP / "AI_APP_MCP_HANDOFF.md").is_file()


def test_docs_codex_usage_exists():
    assert (DOCS_MCP / "CODEX_USAGE.md").is_file()


def test_docs_mcp_tool_policy_exists():
    assert (DOCS_MCP / "MCP_TOOL_POLICY.md").is_file()


def test_docs_video_analysis_request_template_exists():
    assert (DOCS_MCP / "VIDEO_ANALYSIS_REQUEST_TEMPLATE.md").is_file()


def test_docs_limited_release_usage_exists():
    assert (DOCS_MCP / "LIMITED_RELEASE_USAGE.md").is_file()


def test_synthetic_overlay_fixture_exists():
    assert OVERLAY_PATH.is_file()


def test_manifest_schema_version():
    from youtube_mcp_handoff.server import get_mcp_tool_manifest
    m = get_mcp_tool_manifest()
    assert m["schema_version"] == "public_ai_app_mcp_handoff_manifest.v1"


def test_manifest_status():
    from youtube_mcp_handoff.server import get_mcp_tool_manifest
    m = get_mcp_tool_manifest()
    assert m["status"] == "PUBLIC_SYNTHETIC_DEMO_READY"


def test_manifest_tool_count():
    from youtube_mcp_handoff.server import get_mcp_tool_manifest
    m = get_mcp_tool_manifest()
    assert len(m["tools"]) == 4


def test_manifest_all_tools_read_only():
    from youtube_mcp_handoff.server import get_mcp_tool_manifest
    m = get_mcp_tool_manifest()
    assert all(t["read_only"] for t in m["tools"])


def test_allowed_tools_include_overlay_summary():
    from youtube_mcp_handoff.policy import ALLOWED_READ_ONLY_TOOLS
    assert "overlay.summary" in ALLOWED_READ_ONLY_TOOLS


def test_allowed_tools_include_overlay_groups():
    from youtube_mcp_handoff.policy import ALLOWED_READ_ONLY_TOOLS
    assert "overlay.groups" in ALLOWED_READ_ONLY_TOOLS


def test_allowed_tools_include_overlay_group_detail():
    from youtube_mcp_handoff.policy import ALLOWED_READ_ONLY_TOOLS
    assert "overlay.group_detail" in ALLOWED_READ_ONLY_TOOLS


def test_allowed_tools_include_overlay_limitations():
    from youtube_mcp_handoff.policy import ALLOWED_READ_ONLY_TOOLS
    assert "overlay.limitations" in ALLOWED_READ_ONLY_TOOLS


def test_forbidden_capabilities_include_truth_judgment():
    from youtube_mcp_handoff.policy import FORBIDDEN_CAPABILITIES
    assert "truth_judgment" in FORBIDDEN_CAPABILITIES


def test_forbidden_capabilities_include_fact_check():
    from youtube_mcp_handoff.policy import FORBIDDEN_CAPABILITIES
    assert "fact_check" in FORBIDDEN_CAPABILITIES


def test_forbidden_capabilities_include_overlay_mutation():
    from youtube_mcp_handoff.policy import FORBIDDEN_CAPABILITIES
    assert "overlay_mutation" in FORBIDDEN_CAPABILITIES


def test_overlay_summary_count():
    from youtube_mcp_handoff.server import mcp_overlay_summary
    s = mcp_overlay_summary(str(OVERLAY_PATH))
    assert s["overlay_group_count"] == 4


def test_overlay_groups_count():
    from youtube_mcp_handoff.server import mcp_overlay_groups
    g = mcp_overlay_groups(str(OVERLAY_PATH))
    assert g["overlay_group_count"] == 4


def test_invalid_overlay_group_returns_not_found():
    from youtube_mcp_handoff.server import mcp_overlay_group_detail
    r = mcp_overlay_group_detail("nonexistent_group_id", str(OVERLAY_PATH))
    assert r.get("error") == "overlay_group_not_found"


def test_public_demo_overlay_validation_passes():
    from youtube_mcp_handoff.overlay_service import load_operator_overlay, validate_overlay_for_public_demo
    overlay = load_operator_overlay(OVERLAY_PATH)
    errors = validate_overlay_for_public_demo(overlay)
    assert errors == []


def test_answer_guard_catches_fact_checked():
    from youtube_mcp_handoff.answer_guard import validate_public_demo_answer
    errors = validate_public_demo_answer("This was fact checked and verified.")
    assert any("forbidden_phrase" in e for e in errors)


def test_answer_guard_catches_sasilo():
    from youtube_mcp_handoff.answer_guard import validate_public_demo_answer
    errors = validate_public_demo_answer("이것은 사실로 판명되었습니다.")
    assert any("forbidden_phrase" in e for e in errors)


def test_answer_guard_requires_synthetic_fixture():
    from youtube_mcp_handoff.answer_guard import validate_public_demo_answer
    errors = validate_public_demo_answer("some answer without required terms")
    assert any("missing_required:synthetic fixture" in e for e in errors)


def test_answer_guard_requires_not_fact_checked():
    from youtube_mcp_handoff.answer_guard import validate_public_demo_answer
    answer = "synthetic fixture demo with caption fragment claim risk, not truth-ranked, not fact-checked"
    errors = validate_public_demo_answer(answer)
    assert errors == []


def test_smoke_test_status_is_passed():
    from youtube_mcp_handoff.smoke import run_public_mcp_handoff_smoke_test
    result = run_public_mcp_handoff_smoke_test(str(OVERLAY_PATH))
    assert result["status"] == "PASSED"


def test_docs_mention_caption_first():
    for name in ("AI_APP_MCP_HANDOFF.md", "CODEX_USAGE.md"):
        text = (DOCS_MCP / name).read_text(encoding="utf-8").lower()
        assert "caption-first" in text or "caption first" in text, f"{name} missing caption-first"


def test_docs_mention_need_gated_escalation():
    text = (DOCS_MCP / "AI_APP_MCP_HANDOFF.md").read_text(encoding="utf-8").lower()
    assert "need-gated" in text or "need gated" in text


def test_docs_mention_not_fact_checker():
    text = (DOCS_MCP / "AI_APP_MCP_HANDOFF.md").read_text(encoding="utf-8").lower()
    assert "not a fact-checker" in text or "not a fact checker" in text


def test_docs_mention_not_truth_ranked():
    text = (DOCS_MCP / "MCP_TOOL_POLICY.md").read_text(encoding="utf-8").lower()
    assert "not truth-ranked" in text or "not truth ranked" in text


def test_validate_requested_tool_allows_summary():
    from youtube_mcp_handoff.policy import validate_requested_tool
    assert validate_requested_tool("overlay.summary") == []


def test_validate_requested_tool_rejects_unknown():
    from youtube_mcp_handoff.policy import validate_requested_tool
    errors = validate_requested_tool("unknown.tool")
    assert errors


def test_validate_forbidden_rejects_capabilities_list():
    from youtube_mcp_handoff.policy import validate_no_forbidden_capabilities
    errors = validate_no_forbidden_capabilities({"capabilities": ["fact_check"]})
    assert any("fact_check" in e for e in errors)


def test_validate_forbidden_rejects_top_level_key():
    from youtube_mcp_handoff.policy import validate_no_forbidden_capabilities
    errors = validate_no_forbidden_capabilities({"fact_check": True})
    assert any("fact_check" in e for e in errors)


def test_validate_forbidden_rejects_nested_value():
    from youtube_mcp_handoff.policy import validate_no_forbidden_capabilities
    errors = validate_no_forbidden_capabilities({"request": {"actions": ["overlay_mutation"]}})
    assert any("overlay_mutation" in e for e in errors)


def test_required_user_facing_limitations_include_synthetic_fixture():
    from youtube_mcp_handoff.policy import REQUIRED_USER_FACING_LIMITATIONS
    assert "synthetic fixture only" in REQUIRED_USER_FACING_LIMITATIONS


def test_required_user_facing_limitations_include_not_fact_checked():
    from youtube_mcp_handoff.policy import REQUIRED_USER_FACING_LIMITATIONS
    assert "not fact-checked" in REQUIRED_USER_FACING_LIMITATIONS


def test_overlay_validation_rejects_residual_allowed_for_model_answer():
    import copy
    from youtube_mcp_handoff.overlay_service import load_operator_overlay, validate_overlay_for_public_demo
    overlay = load_operator_overlay(OVERLAY_PATH)
    bad = copy.deepcopy(overlay)
    bad["overlay_groups"].append({
        "overlay_group_id": "overlay_SYNTH_residual",
        "source_group_id": "SYNTH_RESIDUAL",
        "split_axis": "residual",
        "claim_count": 1,
        "allowed_for_model_answer": True,
        "truth_status": "not_evaluated",
        "fact_check_status": "not_performed",
    })
    bad["overlay_group_count"] = len(bad["overlay_groups"])
    errors = validate_overlay_for_public_demo(bad)
    assert any("residual_group_allowed_for_model_answer" in e for e in errors)


def test_overlay_service_source_has_no_private_pilot_literal():
    text = (REPO_ROOT / "src" / "youtube_mcp_handoff" / "overlay_service.py").read_text(encoding="utf-8")
    assert "national_pension_reform_pilot_v1" not in text
