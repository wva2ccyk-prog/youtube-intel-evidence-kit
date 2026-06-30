from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List


@dataclass
class QualityIssue:
    severity: str
    code: str
    message: str
    item: Dict[str, Any] | None = None
    blocking: bool = False


HIGH_RISK_GENRES = {
    "health_medical",
    "finance_economy",
    "news_politics",
    "real_estate_local",
    "legal",
    "investment",
}

HIGH_RISK_DOMAINS = {"high", "critical", "severe"}

ALWAYS_BLOCKING_CODES = {
    "important_claim_without_time_anchor",
    "external_knowledge_in_video_internal_summary",
    "high_risk_claim_without_caution",
    "final_report_created_with_failed_gate",
}

EXTERNAL_KNOWLEDGE_MARKERS = (
    "according to external",
    "external source",
    "web search",
    "outside the video",
    "not mentioned in the video",
    "as of ",
    "최신 자료",
    "외부 자료",
    "웹 검색",
    "영상에는 없지만",
)

GENERALIZATION_MARKERS = (
    "always",
    "never",
    "everyone",
    "guaranteed",
    "proven cure",
    "risk-free",
    "must buy",
    "무조건",
    "반드시",
    "항상",
    "절대",
    "모두",
    "보장",
    "확실한 수익",
    "완치",
)

INFERENCE_MARKERS = (
    "probably",
    "likely",
    "appears",
    "seems",
    "i think",
    "may indicate",
    "추정",
    "아마",
    "가능성이",
    "보인다",
    "듯하다",
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(v) for v in value)
    return str(value)


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _claim_text(claim: Dict[str, Any]) -> str:
    return _text(claim.get("claim") or claim.get("text") or claim.get("summary") or "")


def _claim_is_important(claim: Dict[str, Any]) -> bool:
    importance = claim.get("importance")
    if claim.get("important") is True or claim.get("is_important") is True:
        return True
    if isinstance(importance, (int, float)) and importance >= 4:
        return True
    if str(importance or "").lower() in {"high", "critical"}:
        return True
    return claim.get("confidence") == "high" and claim.get("type") not in {"uncertainty", "unsupported/needs-review"}


def _has_time_anchor(claim: Dict[str, Any]) -> bool:
    for key in ("segment_id", "timestamp", "start", "start_time", "time_range"):
        if claim.get(key) not in (None, "", []):
            return True
    for ref in _as_list(claim.get("evidence_refs") or claim.get("evidence_ids")):
        ref_text = str(ref)
        if ref_text.startswith("S") or ":" in ref_text:
            return True
    return False


def _has_caution_label(claim: Dict[str, Any]) -> bool:
    for key in ("caution_label", "warning_label", "risk_label", "caution", "warning", "risk_and_uncertainty"):
        if claim.get(key):
            return True
    labels = " ".join(str(x).lower() for x in _as_list(claim.get("labels") or claim.get("tags")))
    return "caution" in labels or "warning" in labels or "risk" in labels or "주의" in labels


def _claim_has_dependency(claim: Dict[str, Any], kind: str) -> bool:
    keys = (f"requires_{kind}", f"{kind}_needed", f"needs_{kind}_check")
    if any(bool(claim.get(key)) for key in keys):
        return True
    dependency_text = _text(claim.get("dependency") or claim.get("evidence_type") or claim.get("needs") or claim.get("risk"))
    return kind in dependency_text.lower()


def _max_timeline_end(timeline: list[Any]) -> float:
    max_end = 0.0
    for item in timeline:
        if not isinstance(item, dict):
            continue
        for key in ("end_seconds", "end", "start_seconds", "start"):
            try:
                value = float(item.get(key))
            except (TypeError, ValueError):
                continue
            max_end = max(max_end, value)
    return max_end


def _normalize_risk_context(payload: Dict[str, Any]) -> tuple[str, str, bool]:
    genre_value = payload.get("genre")
    risk_value = payload.get("risk_domain")

    if isinstance(genre_value, dict):
        risk_value = genre_value.get("risk_domain") or genre_value.get("risk") or risk_value
        genre = str(genre_value.get("genre") or genre_value.get("name") or genre_value.get("id") or "")
    else:
        genre = str(genre_value or "")

    if isinstance(risk_value, dict):
        risk_value = risk_value.get("risk_domain") or risk_value.get("domain") or risk_value.get("level")
    risk_domain = str(risk_value or "").strip().lower()
    genre = genre.strip().lower()
    high_risk = genre in HIGH_RISK_GENRES or risk_domain in HIGH_RISK_DOMAINS
    return genre, risk_domain, high_risk


def _is_blocking_issue(issue: QualityIssue) -> bool:
    if issue.blocking or issue.severity == "error" or issue.code in ALWAYS_BLOCKING_CODES:
        return True
    if issue.code in {"claim_without_evidence", "unknown_evidence_ref"} and isinstance(issue.item, dict):
        return _claim_is_important(issue.item)
    return False


def _mark_blockers(issues: List[QualityIssue]) -> None:
    for issue in issues:
        issue.blocking = _is_blocking_issue(issue)


def evaluate_claims(claims: List[Dict[str, Any]], known_evidence_ids: set[str] | None = None) -> List[QualityIssue]:
    known_evidence_ids = known_evidence_ids or set()
    issues: List[QualityIssue] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        refs = claim.get("evidence_refs") or claim.get("evidence_ids") or []
        if not refs:
            issues.append(QualityIssue("warning", "claim_without_evidence", "Claim has no evidence reference.", claim))
        for ref in refs:
            if known_evidence_ids and str(ref) not in known_evidence_ids:
                issues.append(QualityIssue("warning", "unknown_evidence_ref", f"Unknown evidence ref: {ref}", claim))
        if _claim_is_important(claim) and not _has_time_anchor(claim):
            issues.append(QualityIssue("warning", "important_claim_without_time_anchor", "Important claim lacks timestamp or segment_id evidence.", claim))
        if claim.get("type") in {"inference", "opinion"} and claim.get("confidence") == "high":
            issues.append(QualityIssue("warning", "overconfident_inference", "Inference/opinion marked as high confidence.", claim))
        if claim.get("type") == "fact" and _contains_any(_claim_text(claim), INFERENCE_MARKERS):
            issues.append(QualityIssue("warning", "inference_written_as_fact", "Inference or opinion language is typed as fact.", claim))
        if _contains_any(_claim_text(claim), GENERALIZATION_MARKERS):
            issues.append(QualityIssue("warning", "unsupported_generalization", "Claim contains a broad or high-risk generalization that needs qualification.", claim))
    return issues


def evaluate_tasks(tasks: List[Dict[str, Any]]) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if not task.get("acceptance_criteria"):
            issues.append(QualityIssue("warning", "task_without_acceptance_criteria", "Task lacks acceptance criteria.", task))
        if not task.get("title") or not task.get("goal"):
            issues.append(QualityIssue("warning", "underspecified_task", "Task lacks title or goal.", task))
    return issues


def evaluate_report_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[QualityIssue] = []
    known_evidence_ids = set(str(x) for x in _as_list(payload.get("known_evidence_ids")))
    allowed_evidence_ids = set(str(x) for x in _as_list(payload.get("allowed_evidence_ids")))
    evidence_ids = known_evidence_ids | allowed_evidence_ids
    claims = [c for c in _as_list(payload.get("claims")) if isinstance(c, dict)]
    issues.extend(evaluate_claims(claims, evidence_ids))
    issues.extend(evaluate_tasks(_as_list(payload.get("tasks") or payload.get("codex_task_candidates"))))

    summary = _text(
        payload.get("video_internal_summary")
        or payload.get("one_line_summary")
        or payload.get("summary")
        or payload.get("video_summary")
    )
    if summary and _contains_any(summary, EXTERNAL_KNOWLEDGE_MARKERS):
        issues.append(QualityIssue("warning", "external_knowledge_in_video_internal_summary", "Video-internal summary appears to include external knowledge.", {"summary": summary}))

    genre, risk_domain, high_risk = _normalize_risk_context(payload)
    if high_risk:
        for claim in claims:
            if not _has_caution_label(claim):
                issues.append(QualityIssue("warning", "high_risk_claim_without_caution", "High-risk genre claim lacks caution or warning label.", claim))

    visual_needed = payload.get("visual_needed", False)
    visual_artifacts = payload.get("visual_artifacts", []) or []
    claim_visual_needed = any(_claim_has_dependency(claim, "visual") for claim in claims)
    if (visual_needed or claim_visual_needed) and not visual_artifacts:
        issues.append(QualityIssue("warning", "visual_needed_without_artifact", "Visual check needed but no visual artifact is attached."))

    audio_needed = payload.get("audio_needed", False)
    audio_artifacts = payload.get("audio_artifacts", []) or []
    claim_audio_needed = any(_claim_has_dependency(claim, "audio") for claim in claims)
    if (audio_needed or claim_audio_needed) and not audio_artifacts:
        issues.append(QualityIssue("warning", "audio_needed_without_artifact", "Audio check needed but no audio artifact is attached."))

    try:
        duration = float(payload.get("duration_seconds"))
    except (TypeError, ValueError):
        duration = 0.0
    timeline = _as_list(payload.get("timeline"))
    if duration >= 1800 and timeline and _max_timeline_end(timeline) < duration * 0.6:
        issues.append(QualityIssue("warning", "front_loaded_long_video_coverage", "Long-video timeline coverage appears front-loaded.", {"duration_seconds": payload.get("duration_seconds")}))

    if payload.get("final_report_created") and payload.get("quality_gate_status") == "fail":
        issues.append(QualityIssue("error", "final_report_created_with_failed_gate", "Final report was created while quality gate status was fail."))

    _mark_blockers(issues)
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    blocker_count = sum(1 for i in issues if i.blocking)
    block_final_report = blocker_count > 0
    return {
        "status": "fail" if error_count or block_final_report else "pass",
        "error_count": error_count,
        "warning_count": warning_count,
        "blocker_count": blocker_count,
        "block_final_report": block_final_report,
        "risk_context": {"genre": genre, "risk_domain": risk_domain, "high_risk": high_risk},
        "issue_count": len(issues),
        "issues": [asdict(i) for i in issues],
    }
