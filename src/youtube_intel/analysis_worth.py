from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io_utils import read_json, write_json, write_text
from .reporting import render_analysis_worth_markdown

SCHEMA_VERSION = "youtube_analysis_worth_v0.1"

HIGH_VALUE_TYPES = {
    "economic_forecast",
    "policy_claim",
    "political_claim",
    "technical_explanation",
    "factual_claim",
    "medical_advice",
    "health_claim",
    "investment_opinion",
}

HIGH_RISK_GENRES = {
    "finance_economy",
    "health_medical",
    "news_politics",
    "real_estate_local",
}

ENTERTAINMENT_MARKERS = {
    "music video",
    "lyrics",
    "dance challenge",
    "vlog",
    "reaction",
    "highlight",
}

TIME_SENSITIVE_MARKERS = {
    "today",
    "this week",
    "this month",
    "interest rate",
    "earnings",
    "election",
    "policy",
    "budget",
    "오늘",
    "어제",
    "이번 주",
    "이번달",
    "이번 달",
    "최신",
    "금리",
    "환율",
    "정책",
    "선거",
    "속보",
    "실적",
}

PROMOTIONAL_NOISE_MARKERS = {
    "sponsored",
    "affiliate",
    "vendor",
    "brochure",
    "sales page",
    "case study",
    "guaranteed",
    "exclusive offer",
    "limited time",
    "협찬",
    "유료광고",
    "광고 포함",
    "제휴",
    "분양상담",
    "투자문의",
    "무료 상담",
    "무료상담",
    "수익 인증",
    "원금 보장",
    "구매링크",
    "멤버십",
}

LOW_QUALITY_INFO_MARKERS = {
    "copied claim",
    "viral claim",
    "everyone says",
    "no source",
    "rumor",
    "hype",
    "might be wrong",
    "not sure",
    "충격",
    "반드시 보세요",
    "난리났다",
    "역대급",
    "모르면 손해",
    "삭제되기 전에",
    "출처 없음",
    "소문",
    "카더라",
}


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in re.finditer(r"[0-9A-Za-z가-힣]+", text or "") if len(m.group(0)) > 1}


def _jaccard(a: str, b: str) -> float:
    left = _tokens(a)
    right = _tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_package(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return read_json(Path(path), {}) or {}


def _video(package: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    video = package.get("video") or {}
    return {
        "video_id": video.get("video_id") or metadata.get("video_id") or metadata.get("id"),
        "title": video.get("title") or metadata.get("title"),
        "language": video.get("language"),
        "duration_seconds": video.get("duration_seconds") or metadata.get("duration_seconds"),
        "channel": metadata.get("channel") or metadata.get("channel_name"),
    }


def _text_blob(package: dict[str, Any], metadata: dict[str, Any] | None = None) -> str:
    video = _video(package, metadata)
    claims = " ".join(str(c.get("text") or "") for c in _as_list(package.get("claim_candidates")))
    return " ".join(str(part or "") for part in [video.get("title"), claims]).lower()


def _duplicate_report(package: dict[str, Any], compare_packages: list[dict[str, Any]]) -> dict[str, Any]:
    claims = [str(c.get("text") or "") for c in _as_list(package.get("claim_candidates")) if c.get("text")]
    other_claims: list[str] = []
    for other in compare_packages:
        other_claims.extend(str(c.get("text") or "") for c in _as_list(other.get("claim_candidates")) if c.get("text"))

    duplicate_count = 0
    for claim in claims:
        if any(_jaccard(claim, other) >= 0.55 for other in other_claims):
            duplicate_count += 1

    ratio = duplicate_count / len(claims) if claims else 0.0
    return {
        "claim_count": len(claims),
        "likely_duplicate_claim_count": duplicate_count,
        "duplicate_ratio": round(ratio, 3),
    }


def _source_trace(package: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for claim in _as_list(package.get("claim_candidates"))[:limit]:
        trace.append(
            {
                "claim_id": claim.get("claim_id"),
                "time_ref": claim.get("time_ref"),
                "evidence": claim.get("evidence") or "unclear",
                "confidence": claim.get("confidence") or "low",
                "claim_type": claim.get("content_type") or "other",
                "excerpt": str(claim.get("text") or "")[:500],
            }
        )
    return trace


def _information_risks(blob: str, claims: list[Any]) -> dict[str, Any]:
    promotional = sorted(marker for marker in PROMOTIONAL_NOISE_MARKERS if marker in blob)
    low_quality = sorted(marker for marker in LOW_QUALITY_INFO_MARKERS if marker in blob)
    weak_claims = [
        c.get("claim_id")
        for c in claims
        if c.get("evidence") in {"unclear", "inference"} or c.get("confidence") == "low"
    ]
    return {
        "promotional_or_hype_noise": bool(promotional),
        "promotional_markers": promotional,
        "low_quality_or_uncertain_web_claims": bool(low_quality),
        "low_quality_markers": low_quality,
        "weak_claim_ids": [item for item in weak_claims if item],
    }


def _route_for_decision(analysis_worth: str, why_analyze: list[str], hard_skip_reasons: list[str]) -> tuple[str, str, list[str]]:
    if hard_skip_reasons:
        return (
            "skip_expensive_analysis",
            "none",
            ["keep only the caption-first package unless the operator overrides the hard stop"],
        )
    if "time_sensitive_claims" in why_analyze or "high_risk_genre" in why_analyze:
        return (
            "needs_source_verification",
            "medium",
            [
                "verify only bounded high-value or high-risk claims",
                "do not run broad web research without an approved claim list",
            ],
        )
    if "promotional_or_hype_noise" in why_analyze or "low_quality_or_uncertain_information" in why_analyze:
        return (
            "caption_first_with_caution",
            "low_to_medium",
            [
                "preserve promotional and uncertainty labels",
                "escalate only claims with timestamps and explicit evidence gaps",
            ],
        )
    if analysis_worth == "yes":
        return (
            "compact_strong_model_review",
            "low_to_medium",
            ["use a compact evidence packet before any full multimodal review"],
        )
    return (
        "caption_first_only",
        "low",
        ["summarize or archive without expensive ASR/OCR/vision unless the operator adds a new question"],
    )


def _decide(package: dict[str, Any], duplicate: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    claims = _as_list(package.get("claim_candidates"))
    genre = package.get("genre") or {}
    genre_name = str(genre.get("genre") or "")
    blob = _text_blob(package, metadata)

    high_value = [c for c in claims if c.get("content_type") in HIGH_VALUE_TYPES]
    residual = [c for c in claims if str(c.get("aside_type") or "none") != "none" or int(c.get("aside_score") or 0) > 0]
    weak = [c for c in claims if c.get("evidence") in {"unclear", "inference"} or c.get("confidence") == "low"]
    hard_skip_reasons: list[str] = []

    if any(marker in blob for marker in ENTERTAINMENT_MARKERS) and not high_value:
        hard_skip_reasons.append("commodity_entertainment_or_music")
    if duplicate.get("duplicate_ratio", 0) >= 0.6 and duplicate.get("claim_count", 0) >= 2:
        hard_skip_reasons.append("local_duplicate_heavy")

    why_analyze: list[str] = []
    if high_value:
        why_analyze.append("high_value_claim_types")
    if residual:
        why_analyze.append("residual_or_uncertainty_candidates")
    if weak:
        why_analyze.append("weak_or_unclear_evidence")
    if genre_name in HIGH_RISK_GENRES:
        why_analyze.append("high_risk_genre")
    if any(marker in blob for marker in TIME_SENSITIVE_MARKERS):
        why_analyze.append("time_sensitive_claims")
    risks = _information_risks(blob, claims)
    if risks["promotional_or_hype_noise"]:
        why_analyze.append("promotional_or_hype_noise")
    if risks["low_quality_or_uncertain_web_claims"]:
        why_analyze.append("low_quality_or_uncertain_information")

    if hard_skip_reasons:
        analysis_worth = "no"
        max_cost_tier = "none"
    elif high_value or residual or genre_name in HIGH_RISK_GENRES:
        analysis_worth = "yes"
        max_cost_tier = "medium_need_gated"
    else:
        analysis_worth = "maybe"
        max_cost_tier = "caption_first_only"

    recommended_route, estimated_next_cost, recommended_next_actions = _route_for_decision(
        analysis_worth, why_analyze, hard_skip_reasons
    )

    return {
        "analysis_worth": analysis_worth,
        "why_analyze": why_analyze,
        "skip_or_stop_reasons": hard_skip_reasons,
        "max_cost_tier": max_cost_tier,
        "recommended_route": recommended_route,
        "estimated_next_cost": estimated_next_cost,
        "recommended_next_actions": recommended_next_actions,
        "information_risks": risks,
        "auto_gate": {
            "auto_skip_candidate": bool(hard_skip_reasons),
            "authority": "operator_review",
            "rule": "never auto-skip from low score alone; hard skip evidence is required",
        },
    }


def build_analysis_worth(
    *,
    package_path: str | Path | None = None,
    run_dir: str | Path | None = None,
    compare_packages: list[str | Path] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build a compact cost gate from an admitted residual package.

    The packet is a decision aid, not a truth verdict. It asks whether the
    package contains enough residual value, risk, uncertainty, or evidence gaps
    to justify spending on deeper ASR/OCR/vision/source-verification/model lanes.
    """
    run_path = Path(run_dir) if run_dir else None
    metadata = read_json(run_path / "metadata.json", {}) if run_path else {}
    if package_path is None and run_path:
        package_path = run_path / "residual" / "package.json"

    package = _read_package(package_path)
    compare = [_read_package(path) for path in compare_packages or []]
    duplicate = _duplicate_report(package, [item for item in compare if item])
    decision = _decide(package, duplicate, metadata)
    result = {
        "schema_version": SCHEMA_VERSION,
        "video": _video(package, metadata),
        "decision": decision,
        "duplicate_novelty": duplicate,
        "source_trace": _source_trace(package),
        "escalation_gates": {
            "asr": "only_when_captions_missing_suspect_or_audio_tone_matters",
            "ocr_or_vision": "only_when_visual_or_screen_evidence_gap_exists",
            "source_verification": "only_for_bounded_high_value_or_high_risk_claims",
            "human_field_review": "when side_signals_depend_on_tacit_experience_or_local_context",
            "strong_model_review": "only_after_compact_evidence_packet_exists",
        },
    }

    if output_dir:
        output = Path(output_dir)
        json_path = write_json(output / "analysis_worth.json", result)
        markdown_path = write_text(output / "analysis_worth.md", render_analysis_worth_markdown(result))
        result["paths"] = {"json": str(json_path), "markdown": str(markdown_path)}
    return result
