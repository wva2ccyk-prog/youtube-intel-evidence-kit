from youtube_quality.gate import evaluate_report_payload


def issue_codes(result):
    return {issue["code"] for issue in result["issues"]}


def issues_by_code(result, code):
    return [issue for issue in result["issues"] if issue["code"] == code]


def test_quality_gate_catches_missing_evidence_refs():
    result = evaluate_report_payload({"claims": [{"claim": "x", "type": "fact"}]})
    assert "claim_without_evidence" in issue_codes(result)
    assert result["block_final_report"] is False


def test_quality_gate_blocks_important_missing_evidence_refs():
    result = evaluate_report_payload({
        "claims": [{"claim": "x", "type": "fact", "confidence": "high"}],
    })
    assert "claim_without_evidence" in issue_codes(result)
    assert result["block_final_report"] is True
    assert result["status"] == "fail"
    assert issues_by_code(result, "claim_without_evidence")[0]["blocking"] is True


def test_quality_gate_catches_and_blocks_important_claim_without_time_anchor():
    result = evaluate_report_payload({
        "claims": [{"claim": "x", "type": "fact", "confidence": "high", "evidence_refs": ["e1"]}],
        "known_evidence_ids": ["e1"],
    })
    assert "important_claim_without_time_anchor" in issue_codes(result)
    assert result["block_final_report"] is True
    assert result["status"] == "fail"


def test_quality_gate_catches_unknown_evidence_ref():
    result = evaluate_report_payload({
        "claims": [{"claim": "x", "type": "fact", "evidence_refs": ["S999"]}],
        "allowed_evidence_ids": ["S001"],
    })
    assert "unknown_evidence_ref" in issue_codes(result)
    assert result["block_final_report"] is False


def test_quality_gate_blocks_important_unknown_evidence_ref():
    result = evaluate_report_payload({
        "claims": [{"claim": "x", "type": "fact", "confidence": "high", "evidence_refs": ["S999"]}],
        "allowed_evidence_ids": ["S001"],
    })
    assert "unknown_evidence_ref" in issue_codes(result)
    assert result["block_final_report"] is True
    assert result["status"] == "fail"


def test_quality_gate_catches_high_risk_claim_without_caution():
    result = evaluate_report_payload({
        "genre": "health_medical",
        "claims": [{"claim": "혈압은 반드시 이 방법으로 해결된다", "type": "fact", "evidence_refs": ["S001"]}],
        "known_evidence_ids": ["S001"],
    })
    assert "high_risk_claim_without_caution" in issue_codes(result)
    assert result["block_final_report"] is True


def test_quality_gate_dict_genre_triggers_high_risk_caution():
    result = evaluate_report_payload({
        "genre": {"genre": "health_medical", "risk_domain": "high"},
        "claims": [{"claim": "약은 무조건 줄여도 된다", "type": "fact", "evidence_refs": ["S001"]}],
        "known_evidence_ids": ["S001"],
    })
    assert result["risk_context"]["genre"] == "health_medical"
    assert result["risk_context"]["high_risk"] is True
    assert "high_risk_claim_without_caution" in issue_codes(result)
    assert result["block_final_report"] is True


def test_quality_gate_risk_domain_high_triggers_high_risk_caution():
    result = evaluate_report_payload({
        "risk_domain": "high",
        "claims": [{"claim": "투자자는 반드시 이 자산을 사야 한다", "type": "fact", "evidence_refs": ["S001"]}],
        "known_evidence_ids": ["S001"],
    })
    assert result["risk_context"]["risk_domain"] == "high"
    assert result["risk_context"]["high_risk"] is True
    assert "high_risk_claim_without_caution" in issue_codes(result)
    assert result["block_final_report"] is True


def test_quality_gate_caution_label_allows_high_risk_claim():
    result = evaluate_report_payload({
        "genre": {"genre": "finance_economy", "risk_domain": "high"},
        "claims": [{
            "claim": "The speaker argues that rates may fall.",
            "type": "fact",
            "evidence_refs": ["S001"],
            "risk_label": "video claim only; not financial advice",
        }],
        "known_evidence_ids": ["S001"],
    })
    assert "high_risk_claim_without_caution" not in issue_codes(result)


def test_quality_gate_catches_and_blocks_external_knowledge_in_internal_summary():
    result = evaluate_report_payload({
        "video_internal_summary": "The video says X. According to external source, Y is also true.",
    })
    assert "external_knowledge_in_video_internal_summary" in issue_codes(result)
    assert result["block_final_report"] is True
    assert result["status"] == "fail"


def test_quality_gate_catches_inference_written_as_fact_without_blocking_by_default():
    result = evaluate_report_payload({
        "claims": [{"claim": "This probably causes the result", "type": "fact", "evidence_refs": ["S001"]}],
        "known_evidence_ids": ["S001"],
    })
    assert "inference_written_as_fact" in issue_codes(result)
    assert result["block_final_report"] is False


def test_quality_gate_catches_visual_and_audio_dependency_without_artifacts():
    result = evaluate_report_payload({
        "claims": [
            {"claim": "The chart shows growth", "type": "fact", "evidence_refs": ["S001"], "requires_visual": True},
            {"claim": "The speaker sounds uncertain", "type": "fact", "evidence_refs": ["S002"], "requires_audio": True},
        ],
        "known_evidence_ids": ["S001", "S002"],
    })
    codes = issue_codes(result)
    assert "visual_needed_without_artifact" in codes
    assert "audio_needed_without_artifact" in codes


def test_quality_gate_catches_codex_task_without_acceptance_criteria():
    result = evaluate_report_payload({
        "codex_task_candidates": [{"title": "Patch parser", "goal": "Improve parsing"}],
    })
    assert "task_without_acceptance_criteria" in issue_codes(result)


def test_quality_gate_catches_front_loaded_long_video_coverage():
    result = evaluate_report_payload({
        "duration_seconds": 4000,
        "timeline": [{"start": 0, "end": 500}, {"start": 600, "end": 800}],
    })
    assert "front_loaded_long_video_coverage" in issue_codes(result)
    assert result["block_final_report"] is False


def test_quality_gate_fails_final_report_created_with_failed_gate():
    result = evaluate_report_payload({
        "final_report_created": True,
        "quality_gate_status": "fail",
    })
    assert result["status"] == "fail"
    assert result["block_final_report"] is True
    assert "final_report_created_with_failed_gate" in issue_codes(result)
