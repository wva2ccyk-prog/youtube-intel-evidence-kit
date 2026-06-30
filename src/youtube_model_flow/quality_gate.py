from __future__ import annotations

from typing import Any, Dict, List

from youtube_quality.gate import evaluate_report_payload


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def collect_segment_ids(run_segments: List[Dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for item in run_segments:
        if not isinstance(item, dict):
            continue
        sid = item.get("segment_id") or item.get("id")
        if sid:
            ids.add(str(sid))
    return ids


def run_quality_gate(
    model_result: Dict[str, Any],
    run_segments: List[Dict[str, Any]] | None = None,
    pack_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Public-safe adapter that propagates final-report blocking semantics.

    The private runtime has richer Gemini-specific validation. The public kit keeps
    the stable contract: evidence ids, high-risk context, timeline, claims, and
    final-report blocking all flow through `evaluate_report_payload`.
    """

    run_segments = run_segments or []
    pack_data = pack_data or {}
    known_ids = collect_segment_ids(run_segments)
    allowed_ids = set(str(x) for x in _as_list(pack_data.get("allowed_evidence_ids")))
    payload = {
        "claims": model_result.get("claims", []) if isinstance(model_result.get("claims", []), list) else [],
        "known_evidence_ids": sorted(known_ids),
        "allowed_evidence_ids": sorted(allowed_ids),
        "codex_task_candidates": model_result.get("codex_task_candidates", []),
        "video_internal_summary": model_result.get("video_internal_summary") or model_result.get("video_summary"),
        "timeline": model_result.get("timeline", []),
        "genre": model_result.get("genre") or pack_data.get("genre"),
        "risk_domain": model_result.get("risk_domain") or pack_data.get("risk_domain"),
        "final_report_created": model_result.get("final_report_created", False),
        "quality_gate_status": model_result.get("quality_gate_status"),
    }
    result = evaluate_report_payload(payload)
    return {
        "status": "fail" if result.get("block_final_report") else result.get("status", "pass"),
        "error_count": result.get("error_count", 0),
        "warning_count": result.get("warning_count", 0),
        "blocker_count": result.get("blocker_count", 0),
        "block_final_report": result.get("block_final_report", False),
        "issues": result.get("issues", []),
    }
