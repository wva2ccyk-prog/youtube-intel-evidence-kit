from __future__ import annotations

import copy
from pathlib import Path

from youtube_intel.analysis_worth import build_analysis_worth
from youtube_intel.io_utils import write_json
from youtube_mcp_handoff.answer_guard import validate_public_demo_answer_payload
from youtube_mcp_handoff.overlay_service import load_operator_overlay, overlay_groups, validate_overlay_for_public_demo
from youtube_mcp_handoff.stdio_server import handle_jsonrpc_request


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY_PATH = REPO_ROOT / "examples" / "synthetic_overlay_demo" / "operator_overlay.json"


def test_analysis_worth_detects_korean_markers(tmp_path: Path):
    package_path = tmp_path / "ko_package.json"
    write_json(
        package_path,
        {
            "video": {"video_id": "ko-demo", "title": "오늘 금리 정책과 협찬 투자문의", "language": "ko"},
            "genre": {"genre": "finance_economy", "risk_domain": "high"},
            "claim_candidates": [
                {
                    "claim_id": "C0001",
                    "text": "오늘 금리 정책이 바뀌어서 원금 보장 수익 인증이 가능하다는 주장이 나옵니다.",
                    "time_ref": "00:10",
                    "content_type": "investment_opinion",
                    "evidence": "inference",
                    "confidence": "low",
                    "aside_type": "type2_unformed_thought",
                    "aside_score": 2,
                }
            ],
        },
    )
    result = build_analysis_worth(package_path=package_path, output_dir=tmp_path / "worth")
    decision = result["decision"]
    assert "time_sensitive_claims" in decision["why_analyze"]
    assert decision["information_risks"]["promotional_or_hype_noise"] is True
    assert decision["recommended_route"] == "needs_source_verification"
    assert Path(result["paths"]["markdown"]).is_file()


def test_overlay_groups_tolerates_missing_optional_shape_without_keyerror():
    result = overlay_groups({"overlay_groups": [{"overlay_group_id": "g1"}]})
    assert result["overlay_group_count"] == 1
    assert result["groups"][0]["source_group_id"] == ""


def test_overlay_validation_rejects_missing_required_fields():
    overlay = load_operator_overlay(OVERLAY_PATH)
    bad = copy.deepcopy(overlay)
    del bad["overlay_groups"][0]["truth_status"]
    errors = validate_overlay_for_public_demo(bad)
    assert any("missing_group_field:truth_status" in e for e in errors)


def test_structured_answer_guard_requires_limitations_field():
    errors = validate_public_demo_answer_payload({"answer": "This is a synthetic fixture answer."})
    assert any("missing_limitation:synthetic_fixture_only" in e for e in errors)


def test_structured_answer_guard_accepts_required_limitations():
    errors = validate_public_demo_answer_payload(
        {
            "answer": "This is a synthetic fixture answer with no truth judgment.",
            "limitations": ["synthetic_fixture_only", "caption_fragment_claim_risk", "not truth-ranked", "not fact-checked"],
        }
    )
    assert errors == []


def test_stdio_server_tools_list_contract():
    response = handle_jsonrpc_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, overlay_path=OVERLAY_PATH)
    assert response is not None
    assert response["result"]["tools"]
    assert any(tool["name"] == "overlay.summary" for tool in response["result"]["tools"])
