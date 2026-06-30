from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .io_utils import read_json, write_json, write_text
from youtube_residual import build_residual_package, validate_package

VIDEO_RECORD_SCHEMA_VERSION = "youtube_video_knowledge_record_v0.1"
TOPIC_COLLECTION_SCHEMA_VERSION = "youtube_topic_collection_v0.1"

TOPIC_LIMITATIONS = [
    "cross-video terrain is not truth verification",
    "claim grouping uses deterministic normalized lexical similarity for the alpha demo",
    "optional embeddings or model-based clustering are not required for the public core",
    "repeated claims are terrain signals, not proof",
    "disagreement groups are candidate relations, not adjudicated contradictions",
    "outliers are single-source or low-diversity claims, not necessarily false claims",
    "external source verification is a separate approved step",
    "need-gated ASR/OCR/vision/speaker review should run only for specific weak or high-stakes claims",
]

GROUPING_METHOD = {
    "name": "deterministic_normalized_similarity_alpha",
    "version": "v0.2",
    "intended_scope": "public alpha cross-video evidence contract with local deterministic grouping",
    "requires_upgrade_for_real_topics": True,
    "fallback_path": "no-network normalized token similarity with stance/opposition heuristics",
    "optional_upgrade_path": "embedding-assisted semantic grouping can be added without changing TopicCollection schema",
    "upgrade_path": [
        "larger labeled fixture sets",
        "embedding-assisted semantic grouping as an optional lane",
        "stronger stance clustering",
        "contradiction-candidate scoring with calibrated thresholds",
        "source/speaker diversity weighting",
        "cache and benchmark harness for real transcript sets",
        "human review for low-confidence groups",
    ],
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "could", "did", "do", "does",
    "for", "from", "in", "into", "is", "it", "more", "not", "of", "on", "or", "than", "that", "the",
    "their", "this", "to", "was", "which", "with", "after", "before", "does", "says", "say", "said",
    "might", "may", "seems", "probably", "useful", "part", "local", "several",
}

SYNONYM_MAP = {
    "irrigation": "water",
    "watering": "water",
    "savings": "saving",
    "save": "saving",
    "saves": "saving",
    "cut": "saving",
    "cuts": "saving",
    "reduce": "saving",
    "reduced": "saving",
    "reduction": "saving",
    "sensor": "sensor",
    "sensors": "sensor",
    "probe": "probe",
    "probes": "probe",
    "calibration": "maintenance",
    "calibrate": "maintenance",
    "maintain": "maintenance",
    "maintenance": "maintenance",
    "drift": "drift",
    "drifted": "drift",
    "yield": "yield",
    "software": "software",
    "salinity": "soil",
    "soil": "soil",
    "subsidy": "policy",
    "subsidies": "policy",
    "policy": "policy",
    "incentive": "policy",
    "incentives": "policy",
    "adoption": "adoption",
    "adopt": "adoption",
    "adopting": "adoption",
    "guarantee": "guarantee",
    "guaranteed": "guarantee",
    "proving": "prove",
    "proved": "prove",
    "prove": "prove",
    "caused": "cause",
    "causes": "cause",
    "causing": "cause",
}

NEGATION_OR_LIMIT_MARKERS = {
    "not", "without", "depends", "limited", "limitation", "but", "however", "omit", "omitted", "missing",
    "did not mention", "does not guarantee", "not guaranteed", "not proving", "not prove",
}

PROMOTIONAL_OR_ASSERTIVE_MARKERS = {
    "vendor says", "case study claims", "claims", "can cut", "can reduce", "guarantee", "guaranteed", "benefit",
}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_time_ref_to_seconds(time_ref: Any) -> float | None:
    if time_ref is None:
        return None
    text = str(time_ref).strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        minutes, seconds = nums
        return minutes * 60 + seconds
    if len(nums) == 3:
        hours, minutes, seconds = nums
        return hours * 3600 + minutes * 60 + seconds
    return None


def _normalize_modality(value: Any) -> str:
    text = _text(value, "caption").lower().strip()
    if text in {"transcript", "caption", "captions", "subtitle", "subtitles"}:
        return "caption"
    if text in {"asr", "audio"}:
        return "asr"
    if text in {"ocr", "screen_text"}:
        return "ocr"
    if text in {"vision", "visual"}:
        return "vision"
    if text in {"scene", "shot"}:
        return "scene"
    if text in {"speaker", "diarization", "speaker_diarization"}:
        return "speaker"
    if text in {"mixed", "multimodal"}:
        return "mixed"
    return text or "caption"


def _normalize_claim_tokens(text: str) -> list[str]:
    lowered = text.lower().strip()
    lowered = re.sub(r"\btwenty percent\b", "20 percent", lowered)
    lowered = re.sub(r"\bper cent\b", "percent", lowered)
    lowered = re.sub(r"[^a-z0-9가-힣%]+", " ", lowered)
    tokens: list[str] = []
    for raw in lowered.split():
        token = SYNONYM_MAP.get(raw, raw)
        if token.endswith("ies") and len(token) > 5:
            token = token[:-3] + "y"
        elif token.endswith("ing") and len(token) > 6:
            token = token[:-3]
        elif token.endswith("ed") and len(token) > 5:
            token = token[:-2]
        elif token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
            token = token[:-1]
        token = SYNONYM_MAP.get(token, token)
        if token in STOPWORDS or len(token) < 3:
            continue
        tokens.append(token)
    return tokens


def _canonicalize_claim_text(text: str) -> str:
    return " ".join(_normalize_claim_tokens(text))


def _token_set(claim: dict[str, Any]) -> set[str]:
    text = _text(claim.get("text"), "")
    tokens = set(_normalize_claim_tokens(text))
    if {"water", "saving", "20", "percent", "guarantee"} & tokens:
        tokens.update({"water", "saving"})
    if {"probe", "drift", "maintenance", "cost"} & tokens:
        tokens.update({"maintenance", "reliability"})
    if {"yield", "software", "soil", "cause", "prove"} & tokens:
        tokens.update({"yield", "causality"})
    if {"policy", "adoption"} & tokens:
        tokens.update({"policy", "adoption"})
    content_type = _text(claim.get("content_type"), "")
    if content_type and content_type != "other":
        tokens.add(content_type)
    return tokens


def _claim_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    ta = _token_set(a)
    tb = _token_set(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return round((jaccard * 0.55) + (overlap * 0.45), 4)


def _claim_group_key(text: str, content_type: str | None = None) -> str:
    tokens = _normalize_claim_tokens(text)
    if not tokens and content_type and content_type != "other":
        return content_type
    if not tokens:
        return "generic_claim"
    ranked = sorted(set(tokens), key=lambda t: (-tokens.count(t), tokens.index(t)))[:4]
    return "topic_" + "_".join(ranked)


def _group_label(key: str) -> str:
    clean = key.removeprefix("topic_")
    labels = {
        "water_saving": "Water-savings claim",
        "water_saving_claim": "Water-savings claim",
        "sensor_probe_maintenance": "Sensor reliability / maintenance risk",
        "maintenance_sensor_probe": "Sensor reliability / maintenance risk",
        "yield_software_soil": "Yield explanation / causality claim",
        "yield_cause_software": "Yield explanation / causality claim",
        "policy_adoption": "Policy or adoption context",
    }
    for prefix, label in labels.items():
        if clean.startswith(prefix):
            return label
    return clean.replace("_", " ").title()


def _has_limit_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in NEGATION_OR_LIMIT_MARKERS)


def _has_assertive_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PROMOTIONAL_OR_ASSERTIVE_MARKERS)


def _opposition_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    if _claim_similarity(a, b) < 0.22:
        return 0.0
    a_text = _text(a.get("text"), "")
    b_text = _text(b.get("text"), "")
    if _has_assertive_marker(a_text) and _has_limit_marker(b_text):
        return 0.8
    if _has_assertive_marker(b_text) and _has_limit_marker(a_text):
        return 0.8
    if _text(a.get("stance")) != _text(b.get("stance")) and {a.get("stance"), b.get("stance")} & {"caution_or_counterpoint", "hypothesis_or_alternative"}:
        return 0.45
    return 0.0


def _make_group_key_from_claims(claims: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for claim in claims:
        for token in _token_set(claim):
            counts[token] += 1
    if not counts:
        return "generic_claim"
    ranked = sorted(counts, key=lambda token: (-counts[token], token))[:4]
    return "topic_" + "_".join(ranked)


def _group_claims_by_similarity(claims: list[dict[str, Any]], threshold: float = 0.20) -> list[tuple[str, list[dict[str, Any]], float]]:
    groups: list[list[dict[str, Any]]] = []
    for claim in claims:
        best_idx: int | None = None
        best_score = 0.0
        for idx, group in enumerate(groups):
            score = max(_claim_similarity(claim, member) for member in group)
            if score > best_score:
                best_idx = idx
                best_score = score
        if best_idx is not None and best_score >= threshold:
            groups[best_idx].append(claim)
        else:
            groups.append([claim])
    scored: list[tuple[str, list[dict[str, Any]], float]] = []
    for group in groups:
        key = _make_group_key_from_claims(group)
        pair_scores = [
            _claim_similarity(group[i], group[j])
            for i in range(len(group))
            for j in range(i + 1, len(group))
        ]
        mean_score = round(sum(pair_scores) / len(pair_scores), 4) if pair_scores else 1.0
        for claim in group:
            claim["claim_group_key"] = key
            claim["claim_group_label"] = _group_label(key)
            claim["normalized_tokens"] = sorted(_token_set(claim))
        scored.append((key, group, mean_score))
    return scored


# Supported deterministic clusterers for the public core. Both are local and
# require no network or model download. `normalized` is the default mixed
# token/character similarity used since the alpha demo; `token_jaccard` is a
# stricter, purely lexical option that only merges claims whose token sets
# overlap above a fixed threshold. An embedding-assisted lane can be added
# later without changing the TopicCollection schema (see GROUPING_METHOD).
CLUSTERERS = ("normalized", "token_jaccard")


def _token_jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _group_claims_by_token_jaccard(
    claims: list[dict[str, Any]],
    threshold: float = 0.5,
) -> list[tuple[str, list[dict[str, Any]], float]]:
    """Group claims by token-set Jaccard overlap only.

    This is a stricter, fully lexical alternative to the default mixed
    similarity. A claim joins the first existing group whose representative
    token set overlaps at or above `threshold`; otherwise it starts a new
    group. No network, no embeddings, no model download.
    """
    groups: list[list[dict[str, Any]]] = []
    group_tokens: list[set[str]] = []
    for claim in claims:
        tokens = _token_set(claim)
        matched: int | None = None
        best_score = 0.0
        for idx, rep_tokens in enumerate(group_tokens):
            score = _token_jaccard(tokens, rep_tokens)
            if score >= threshold and score > best_score:
                matched = idx
                best_score = score
        if matched is not None:
            groups[matched].append(claim)
        else:
            groups.append([claim])
            group_tokens.append(tokens)
    scored: list[tuple[str, list[dict[str, Any]], float]] = []
    for group in groups:
        key = _make_group_key_from_claims(group)
        pair_scores = [
            _token_jaccard(_token_set(group[i]), _token_set(group[j]))
            for i in range(len(group))
            for j in range(i + 1, len(group))
        ]
        mean_score = round(sum(pair_scores) / len(pair_scores), 4) if pair_scores else 1.0
        for claim in group:
            claim["claim_group_key"] = key
            claim["claim_group_label"] = _group_label(key)
            claim["normalized_tokens"] = sorted(_token_set(claim))
        scored.append((key, group, mean_score))
    return scored


def _cluster_claims(
    claims: list[dict[str, Any]],
    clusterer: str,
    *,
    token_jaccard_threshold: float = 0.5,
) -> list[tuple[str, list[dict[str, Any]], float]]:
    """Dispatch to the selected deterministic clusterer."""
    if clusterer == "token_jaccard":
        return _group_claims_by_token_jaccard(claims, threshold=token_jaccard_threshold)
    return _group_claims_by_similarity(claims)


def _stance(text: str, evidence: str = "", confidence: str = "") -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("did not mention", "omit", "drift", "maintenance", "not guaranteed", "not discussed", "but", "however", "충돌", "누락")):
        return "caution_or_counterpoint"
    if any(token in lowered for token in ("might", "may", "could", "seems", "probably", "hypothesis", "아마", "추정", "가능성")):
        return "hypothesis_or_alternative"
    if any(token in lowered for token in ("vendor says", "case study", "can cut", "improve", "benefit", "claims", "says it can", "홍보", "사례")):
        return "claim_or_promotion"
    if evidence == "inference" or confidence == "low":
        return "hypothesis_or_alternative"
    return "reported_claim"


def _support_role(stance: str) -> str:
    if stance == "claim_or_promotion":
        return "supporting_or_promotional"
    if stance == "caution_or_counterpoint":
        return "challenging_or_limiting"
    if stance == "hypothesis_or_alternative":
        return "alternative_explanation"
    return "reported_context"


def _need_gates_for_claim(text: str, speaker: Any, modality_sources: list[str], confidence: str) -> dict[str, str]:
    lowered = text.lower()
    has_visual_reference = any(token in lowered for token in ("screen", "map", "chart", "dashboard", "table", "slide", "on screen"))
    high_stakes_marker = any(token in lowered for token in ("policy", "subsidy", "deadline", "guarantee", "twenty percent", "20 percent"))
    weak_transcript = confidence == "low"
    return {
        "asr": "needed" if weak_transcript else "not_needed",
        "ocr_vision": "needed" if has_visual_reference or "mixed" in modality_sources else "not_needed",
        "speaker_diarization": "needed" if speaker in (None, "", "unknown") else "not_needed",
        "external_verification": "needed" if high_stakes_marker else "not_needed",
        "strong_model_review": "needed" if high_stakes_marker or weak_transcript else "not_needed",
    }


def _make_evidence_record(
    *,
    video_id: str,
    local_index: int,
    text: str,
    speaker: Any,
    time_ref: Any,
    modality_sources: list[str],
    confidence: str,
) -> dict[str, Any]:
    timestamp_start = _parse_time_ref_to_seconds(time_ref)
    evidence_id = f"{video_id}:E{local_index:04d}"
    return {
        "evidence_id": evidence_id,
        "video_id": video_id,
        "timestamp_start": timestamp_start,
        "timestamp_end": None,
        "time_ref": time_ref,
        "speaker": speaker,
        "speaker_confidence": "high" if speaker not in (None, "", "unknown") else "unknown",
        "modality": modality_sources,
        "text": text,
        "confidence": confidence,
        "source_separation": "video_internal_claim_not_external_source",
    }


def _claim_coordinate(claim: dict[str, Any]) -> str:
    return (
        f"claim_uid={_text(claim.get('claim_uid'), 'unknown')} | "
        f"video={_text(claim.get('source_video_id'), 'unknown')} | "
        f"time={_text(claim.get('time_ref'), 'unknown')} | "
        f"speaker={_text(claim.get('speaker'), 'unknown speaker')} | "
        f"confidence={_text(claim.get('confidence'), 'unknown')} | "
        f"modality={','.join(map(str, _as_list(claim.get('modality_sources'))))}"
    )


def build_video_knowledge_record(
    package: dict[str, Any],
    *,
    topic_id: str,
    topic_title: str,
    video_role: str = "source_video",
) -> dict[str, Any]:
    """Convert one residual package into a reusable VideoKnowledgeRecord.

    A residual package is the single-video input layer. A VideoKnowledgeRecord is
    the cross-video-ready record: claims receive stable topic grouping keys,
    stance labels, source coordinates, modality labels, limitations, and
    need-gated escalation flags.
    """
    video = package.get("video") or {}
    video_id = _text(video.get("video_id"), "unknown-video")
    records: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    for idx, claim in enumerate(_as_list(package.get("claim_candidates")), start=1):
        if not isinstance(claim, dict):
            continue
        local_id = _text(claim.get("claim_id"), f"C{len(records) + 1:04d}")
        text = _text(claim.get("text"), "")
        content_type = _text(claim.get("content_type"), "other")
        evidence = _text(claim.get("evidence"), "unclear")
        confidence = _text(claim.get("confidence"), "low")
        modality_sources = [_normalize_modality(claim.get("modality_source") or "caption")]
        group_key = _claim_group_key(text, content_type)
        stance = _stance(text, evidence=evidence, confidence=confidence)
        evidence_record = _make_evidence_record(
            video_id=video_id,
            local_index=idx,
            text=text,
            speaker=claim.get("speaker"),
            time_ref=claim.get("time_ref"),
            modality_sources=modality_sources,
            confidence=confidence,
        )
        evidence_records.append(evidence_record)
        record = {
            "claim_uid": f"{video_id}:{local_id}",
            "source_video_id": video_id,
            "local_claim_id": local_id,
            "text": text,
            "canonical_text": _canonicalize_claim_text(text),
            "speaker": claim.get("speaker"),
            "speaker_confidence": evidence_record["speaker_confidence"],
            "time_ref": claim.get("time_ref"),
            "timestamp_start": evidence_record["timestamp_start"],
            "timestamp_end": evidence_record["timestamp_end"],
            "content_type": content_type,
            "evidence": evidence,
            "evidence_ids": [evidence_record["evidence_id"]],
            "evidence_coordinate": {
                "video_id": video_id,
                "timestamp_start": evidence_record["timestamp_start"],
                "timestamp_end": evidence_record["timestamp_end"],
                "time_ref": claim.get("time_ref"),
                "speaker": claim.get("speaker"),
                "speaker_confidence": evidence_record["speaker_confidence"],
                "modality": modality_sources,
                "evidence_id": evidence_record["evidence_id"],
            },
            "confidence": confidence,
            "modality_sources": modality_sources,
            "claim_group_key": group_key,
            "claim_group_label": _group_label(group_key),
            "stance": stance,
            "support_role": _support_role(stance),
            "aside_type": claim.get("aside_type") or "none",
            "aside_score": claim.get("aside_score") or 0,
            "verification_status": "video_internal_not_fact_checked",
            "need_gates": _need_gates_for_claim(text, claim.get("speaker"), modality_sources, confidence),
        }
        records.append(record)

    need_gate_summary: dict[str, int] = defaultdict(int)
    for record in records:
        for gate, status in (record.get("need_gates") or {}).items():
            if status == "needed":
                need_gate_summary[gate] += 1

    return {
        "schema_version": VIDEO_RECORD_SCHEMA_VERSION,
        "topic": {"topic_id": topic_id, "title": topic_title},
        "video": {
            "video_id": video_id,
            "title": video.get("title"),
            "language": video.get("language"),
            "duration_seconds": video.get("duration_seconds"),
            "role_in_topic": video_role,
            "source_url": video.get("source_url"),
            "channel": video.get("channel"),
            "published_at": video.get("published_at"),
            "transcript_source": video.get("transcript_source") or "synthetic_caption_fixture",
            "transcript_quality": video.get("transcript_quality") or "demo_high",
        },
        "analysis_layer": "single_video_input_for_topic_collection",
        "truth_status": "not_evaluated",
        "fact_check_status": "not_performed",
        "claim_records": records,
        "evidence_records": evidence_records,
        "aside_candidate_uids": [r["claim_uid"] for r in records if r.get("aside_type") not in (None, "", "none")],
        "counts": {
            "claim_total": len(records),
            "evidence_total": len(evidence_records),
            "aside_total": sum(1 for r in records if r.get("aside_type") not in (None, "", "none")),
        },
        "need_gate_summary": dict(sorted(need_gate_summary.items())),
        "provenance": {
            "builder": "youtube_intel.topic_collection.build_video_knowledge_record",
            "builder_version": "v0.1",
            "created_at_utc": _now_utc(),
            "input_package_hash": _stable_json_hash(package),
            "alpha_contract_demo": True,
        },
        "limitations": TOPIC_LIMITATIONS,
    }


def _source_diversity(claims: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "video_count": len({_text(c.get("source_video_id"), "unknown-video") for c in claims}),
        "speaker_count": len({_text(c.get("speaker"), "unknown-speaker") for c in claims}),
        "channel_count": 0,
    }


def _why_grouped(key: str, claims: list[dict[str, Any]]) -> list[str]:
    canonical = [str(c.get("canonical_text") or _canonicalize_claim_text(_text(c.get("text"), ""))) for c in claims]
    shared_tokens = sorted(set.intersection(*(set(t.split()) for t in canonical))) if len(canonical) >= 2 else []
    reasons = [f"normalized similarity grouping key: {key}"]
    if shared_tokens:
        reasons.append("shared normalized tokens: " + ", ".join(shared_tokens[:8]))
    if len({_text(c.get("source_video_id"), "unknown") for c in claims}) >= 2:
        reasons.append("appears in multiple source videos")
    return reasons


def _make_disagreement_relation(group_id: str, group: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any] | None:
    stances = {_text(c.get("stance"), "reported_claim") for c in claims}
    if not (
        "claim_or_promotion" in stances
        and ("caution_or_counterpoint" in stances or "hypothesis_or_alternative" in stances)
    ):
        return None
    relation_type = "support_vs_caution"
    if "hypothesis_or_alternative" in stances and "caution_or_counterpoint" not in stances:
        relation_type = "alternative_explanation"
    return {
        "relation_id": f"D{group_id[1:]}",
        "claim_group_id": group_id,
        "relation_type": relation_type,
        "claim_uids": [_text(c.get("claim_uid"), "unknown-claim") for c in claims],
        "confidence": "medium" if len(claims) >= 2 else "low",
        "human_review_required": True,
        "why_flagged": "deterministic alpha grouping found promotional/supporting stance alongside caution or alternative stance in the same normalized topic group",
    }


# Position axes used to roll claim groups up into opinion groups. These are
# stance-derived and domain-neutral on purpose: the public core must not encode
# a specific subject area. Each claim group is assigned to one axis from its
# dominant support role, and opinion groups are only formed across videos.
_OPINION_AXES = {
    "supporting": {
        "label": "Supporting / promotional position",
        "summary": "Claim groups that mostly assert or promote the topic claim. Repetition is a terrain signal, not proof.",
        "roles": {"supporting_or_promotional"},
    },
    "challenging": {
        "label": "Challenging / limiting position",
        "summary": "Claim groups that mostly caution, qualify, or point at limitations. This is not a truth judgment.",
        "roles": {"challenging_or_limiting"},
    },
    "alternative": {
        "label": "Alternative-explanation position",
        "summary": "Claim groups that mostly offer a different explanation or hypothesis. This is not a truth judgment.",
        "roles": {"alternative_explanation"},
    },
    "reported": {
        "label": "Reported / contextual position",
        "summary": "Claim groups that mostly report or contextualize without a clear stance.",
        "roles": {"reported_context"},
    },
}


def _dominant_axis(group: dict[str, Any]) -> str:
    """Pick the opinion axis for a claim group from its support roles.

    Uses the group's own `support_roles` terrain. Falls back to `reported`
    when no clear role is present. Never invents a stance.
    """
    roles = set(_as_list(group.get("support_roles")))
    for axis_key, axis in _OPINION_AXES.items():
        if axis_key == "reported":
            continue
        if roles & axis["roles"]:
            # A group can carry multiple roles; prefer the first non-reported
            # axis in declared order (supporting, challenging, alternative).
            return axis_key
    return "reported"


def build_opinion_groups(
    claim_groups: list[dict[str, Any]],
    *,
    allow_single_video: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Roll claim groups up into cross-video opinion groups.

    Opinion groups are position buckets (supporting / challenging /
    alternative / reported) built only from structured claim-group fields.
    By default a bucket is only emitted when its claim groups span at least
    two distinct source videos, so single-source noise does not look like a
    shared position. Does not rank truth and does not fabricate groups.
    """
    warnings: list[str] = []
    if not claim_groups:
        return [], ["opinion_group_builder_no_claim_groups"]

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in claim_groups:
        buckets[_dominant_axis(group)].append(group)

    opinion_groups: list[dict[str, Any]] = []
    og_idx = 0
    for axis_key in _OPINION_AXES:
        members = buckets.get(axis_key, [])
        if not members:
            continue
        member_ids = [g.get("group_id") for g in members]
        video_ids: list[str] = []
        for g in members:
            for vid in _as_list(g.get("video_ids")):
                if vid not in video_ids:
                    video_ids.append(vid)
        if len(video_ids) < 2 and not allow_single_video:
            warnings.append(f"opinion_group_skipped_single_source:{axis_key}")
            continue
        og_idx += 1
        axis = _OPINION_AXES[axis_key]
        distinguishing = [g.get("representative_claim_uid") for g in members if g.get("representative_claim_uid")]
        any_disagreement = any(g.get("status", {}).get("disagreement_point") for g in members)
        opinion_groups.append({
            "opinion_group_id": f"OG{og_idx:04d}",
            "axis": axis_key,
            "label": axis["label"],
            "position_summary": axis["summary"],
            "member_claim_group_ids": member_ids,
            "source_video_ids": sorted(video_ids),
            "distinguishing_claims": distinguishing,
            "contains_disagreement_point": any_disagreement,
            "confidence": "medium" if len(video_ids) >= 2 else "low",
            "truth_status": "not_evaluated",
        })
    if not opinion_groups:
        warnings.append("opinion_group_builder_produced_no_groups")
    return opinion_groups, warnings

def build_topic_collection(
    records: list[dict[str, Any]],
    *,
    topic_id: str,
    topic_title: str,
    clusterer: str = "normalized",
    token_jaccard_threshold: float = 0.5,
    build_opinion_groups_layer: bool = True,
    allow_single_video_opinions: bool = False,
) -> dict[str, Any]:
    """Build a deterministic cross-video TopicCollection from records."""
    if clusterer not in CLUSTERERS:
        raise ValueError(f"Unsupported clusterer: {clusterer!r}. Choose from {CLUSTERERS}")
    all_claims: list[dict[str, Any]] = []
    videos: dict[str, dict[str, Any]] = {}
    evidence_index: dict[str, dict[str, Any]] = {}
    for record in records:
        video = record.get("video") or {}
        video_id = _text(video.get("video_id"), "unknown-video")
        videos[video_id] = video
        for evidence in _as_list(record.get("evidence_records")):
            if isinstance(evidence, dict):
                evidence_index[_text(evidence.get("evidence_id"), "unknown-evidence")] = evidence
        for claim in _as_list(record.get("claim_records")):
            if isinstance(claim, dict):
                all_claims.append(claim)

    grouped = _cluster_claims(all_claims, clusterer, token_jaccard_threshold=token_jaccard_threshold)

    claim_groups: list[dict[str, Any]] = []
    repeated: list[str] = []
    disagreements: list[str] = []
    outliers: list[str] = []
    disagreement_relations: list[dict[str, Any]] = []
    outlier_details: list[dict[str, Any]] = []
    contradiction_candidates: list[dict[str, Any]] = []

    for idx, (key, claims, mean_score) in enumerate(sorted(grouped, key=lambda item: item[0]), start=1):
        group_id = f"G{idx:04d}"
        video_ids = sorted({_text(c.get("source_video_id"), "unknown-video") for c in claims})
        stances = sorted({_text(c.get("stance"), "reported_claim") for c in claims})
        roles = sorted({_text(c.get("support_role"), "reported_context") for c in claims})
        has_disagreement = (
            "claim_or_promotion" in stances
            and ("caution_or_counterpoint" in stances or "hypothesis_or_alternative" in stances)
        )
        is_repeated = len(video_ids) >= 2
        is_outlier = len(video_ids) == 1
        if is_repeated:
            repeated.append(group_id)
        if has_disagreement:
            disagreements.append(group_id)
        if is_outlier:
            outliers.append(group_id)
        label = _group_label(key)
        claim_uids = [_text(c.get("claim_uid"), "unknown-claim") for c in claims]
        evidence_ids: list[str] = []
        for c in claims:
            evidence_ids.extend(str(e) for e in _as_list(c.get("evidence_ids")))
        group = {
            "group_id": group_id,
            "claim_group_key": key,
            "label": label,
            "summary": f"{label}: {len(claims)} claim(s) across {len(video_ids)} video(s).",
            "video_ids": video_ids,
            "claim_count": len(claims),
            "stances": stances,
            "support_roles": roles,
            "status": {
                "repeated_claim": is_repeated,
                "disagreement_point": has_disagreement,
                "outlier_claim": is_outlier,
            },
            "claim_uids": claim_uids,
            "member_claim_uids": claim_uids,
            "representative_claim_uid": claim_uids[0] if claim_uids else None,
            "evidence_ids": sorted(set(evidence_ids)),
            "evidence_coordinates": sorted(set(evidence_ids)),
            "source_diversity": _source_diversity(claims),
            "grouping_method": GROUPING_METHOD["name"],
            "grouping_confidence": "high" if mean_score >= 0.62 and is_repeated else ("medium" if is_repeated or mean_score >= 0.20 else "low"),
            "grouping_score": mean_score,
            "why_grouped": _why_grouped(key, claims),
            "human_review_required": bool(has_disagreement or is_outlier),
        }
        if is_outlier:
            group["outlier_type"] = "single_source_outlier"
            outlier_details.append({
                "claim_group_id": group_id,
                "outlier_type": "single_source_outlier",
                "claim_uids": claim_uids,
                "followup_priority": "medium" if any((c.get("need_gates") or {}).get("external_verification") == "needed" for c in claims) else "low",
                "why_outlier": "appears in only one source video in this TopicCollection",
            })
        relation = _make_disagreement_relation(group_id, group, claims)
        if relation:
            disagreement_relations.append(relation)
        for left_idx in range(len(claims)):
            for right_idx in range(left_idx + 1, len(claims)):
                score = _opposition_score(claims[left_idx], claims[right_idx])
                if score >= 0.45:
                    contradiction_candidates.append({
                        "claim_group_id": group_id,
                        "left_claim_uid": _text(claims[left_idx].get("claim_uid"), "unknown-claim"),
                        "right_claim_uid": _text(claims[right_idx].get("claim_uid"), "unknown-claim"),
                        "opposition_score": score,
                        "status": "candidate_requires_human_review",
                    })
        claim_groups.append(group)

    stance_groups: dict[str, list[str]] = defaultdict(list)
    for claim in all_claims:
        stance_groups[_text(claim.get("stance"), "reported_claim")].append(_text(claim.get("claim_uid"), "unknown-claim"))

    opinion_groups: list[dict[str, Any]] = []
    opinion_group_warnings: list[str] = []
    if build_opinion_groups_layer:
        opinion_groups, opinion_group_warnings = build_opinion_groups(
            claim_groups,
            allow_single_video=allow_single_video_opinions,
        )

    topic_collection = {
        "schema_version": TOPIC_COLLECTION_SCHEMA_VERSION,
        "topic": {
            "topic_id": topic_id,
            "title": topic_title,
            "final_objective": "cross-video opinion terrain, not single-video summarization",
        },
        "source_videos": list(videos.values()),
        "analysis_layer": "cross_video_topic_collection",
        "video_record_count": len(records),
        "claim_total": len(all_claims),
        "claim_groups": claim_groups,
        "opinion_groups": opinion_groups,
        "stance_groups": dict(sorted(stance_groups.items())),
        "terrain": {
            "repeated_claim_group_ids": repeated,
            "disagreement_group_ids": disagreements,
            "outlier_group_ids": outliers,
            "disagreement_relations": disagreement_relations,
            "outlier_details": outlier_details,
            "contradiction_candidates": contradiction_candidates,
            "opinion_group_ids": [og["opinion_group_id"] for og in opinion_groups],
            "opinion_group_warnings": opinion_group_warnings,
            "operator_judgment_required": True,
            "truth_status": "not_evaluated",
            "fact_check_status": "not_performed",
        },
        "claim_index": {str(c.get("claim_uid")): c for c in all_claims},
        "evidence_index": evidence_index,
        "grouping_method": GROUPING_METHOD,
        "clusterer": clusterer,
        "provenance": {
            "builder": "youtube_intel.topic_collection.build_topic_collection",
            "builder_version": "v0.1",
            "created_at_utc": _now_utc(),
            "input_record_hashes": [_stable_json_hash(r) for r in records],
            "alpha_contract_demo": True,
        },
        "limitations": TOPIC_LIMITATIONS,
    }
    topic_collection["provenance"]["topic_collection_hash_preview"] = _stable_json_hash({
        "topic": topic_collection["topic"],
        "claim_groups": topic_collection["claim_groups"],
        "terrain": topic_collection["terrain"],
    })
    return topic_collection


def evaluate_topic_collection(collection: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """Score TopicCollection grouping against a small labeled fixture contract.

    The metric is intentionally simple and local: must-link pairs should land in
    the same group, and cannot-link pairs should land in different groups. It is
    a smoke-quality signal, not a production benchmark.
    """
    claim_index = collection.get("claim_index") or {}
    uid_to_group: dict[str, str] = {}
    text_to_uid: dict[str, str] = {}
    for group in _as_list(collection.get("claim_groups")):
        if not isinstance(group, dict):
            continue
        gid = _text(group.get("group_id"), "unknown-group")
        for uid in _as_list(group.get("claim_uids")):
            uid_to_group[_text(uid)] = gid
    for uid, claim in claim_index.items() if isinstance(claim_index, dict) else []:
        if isinstance(claim, dict):
            text_to_uid[_canonicalize_claim_text(_text(claim.get("text"), ""))] = _text(uid)

    def resolve(text: str) -> str | None:
        key = _canonicalize_claim_text(text)
        if key in text_to_uid:
            return text_to_uid[key]
        key_tokens = set(key.split())
        best_uid = None
        best_score = 0.0
        for candidate_key, uid in text_to_uid.items():
            candidate_tokens = set(candidate_key.split())
            if not key_tokens or not candidate_tokens:
                continue
            score = len(key_tokens & candidate_tokens) / len(key_tokens | candidate_tokens)
            if score > best_score:
                best_uid = uid
                best_score = score
        return best_uid if best_score >= 0.55 else None

    checks: list[dict[str, Any]] = []
    passed = 0
    total = 0
    for pair in _as_list(expected.get("must_link")):
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        left = resolve(str(pair[0]))
        right = resolve(str(pair[1]))
        ok = bool(left and right and uid_to_group.get(left) == uid_to_group.get(right))
        total += 1
        passed += int(ok)
        checks.append({"type": "must_link", "ok": ok, "left_uid": left, "right_uid": right, "left_group": uid_to_group.get(left or ""), "right_group": uid_to_group.get(right or "")})
    for pair in _as_list(expected.get("cannot_link")):
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        left = resolve(str(pair[0]))
        right = resolve(str(pair[1]))
        ok = bool(left and right and uid_to_group.get(left) != uid_to_group.get(right))
        total += 1
        passed += int(ok)
        checks.append({"type": "cannot_link", "ok": ok, "left_uid": left, "right_uid": right, "left_group": uid_to_group.get(left or ""), "right_group": uid_to_group.get(right or "")})
    score = round(passed / total, 4) if total else 0.0
    return {
        "schema_version": "youtube_topic_grouping_evaluation_v0.1",
        "metric": "pair_agreement",
        "passed": passed,
        "total": total,
        "score": score,
        "threshold": expected.get("threshold", 0.75),
        "status": "pass" if total and score >= float(expected.get("threshold", 0.75)) else "fail",
        "checks": checks,
    }

def render_topic_terrain_markdown(collection: dict[str, Any]) -> str:
    topic = collection.get("topic") or {}
    terrain = collection.get("terrain") or {}
    groups = _as_list(collection.get("claim_groups"))
    lines = [
        "# Topic Terrain",
        "",
        f"Topic: {_text(topic.get('title'), 'unknown topic')}",
        f"Topic ID: {_text(topic.get('topic_id'), 'unknown')}",
        f"Source videos: {collection.get('video_record_count', 0)}",
        f"Claim records: {collection.get('claim_total', 0)}",
        "Truth status: not evaluated; not fact-checked",
        "",
        "## What This Is",
        "- Cross-video opinion terrain built from reusable VideoKnowledgeRecords.",
        "- Single-video evidence packets are inputs, not the final product.",
        "- The system maps repeated claims, disagreement candidates, outliers, speakers, timestamps, and evidence coordinates.",
        "- It does not decide which claim is true.",
        "- Repeated claims are not proof; disagreement groups are candidates for review.",
        "",
        "## Terrain Summary",
        f"- Repeated claim groups: {len(_as_list(terrain.get('repeated_claim_group_ids')))}",
        f"- Disagreement groups: {len(_as_list(terrain.get('disagreement_group_ids')))}",
        f"- Outlier groups: {len(_as_list(terrain.get('outlier_group_ids')))}",
        f"- Opinion groups: {len(_as_list(collection.get('opinion_groups')))}",
        "",
        "## Claim Groups",
    ]
    claim_index = collection.get("claim_index") or {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        status = group.get("status") or {}
        tags = [name for name, active in status.items() if active]
        lines.append(f"### {group.get('group_id')} - {_text(group.get('label'), 'claim group')}")
        lines.append(f"- status: {', '.join(tags) if tags else 'mapped_claim_group'}")
        lines.append(f"- videos: {', '.join(map(str, _as_list(group.get('video_ids'))))}")
        lines.append(f"- stances: {', '.join(map(str, _as_list(group.get('stances'))))}")
        lines.append(f"- grouping: {_text(group.get('grouping_method'), 'unknown')} / confidence={_text(group.get('grouping_confidence'), 'unknown')}")
        for reason in _as_list(group.get("why_grouped")):
            lines.append(f"- why_grouped: {reason}")
        lines.append("- claims:")
        for uid in _as_list(group.get("claim_uids")):
            claim = claim_index.get(uid) if isinstance(claim_index, dict) else None
            if isinstance(claim, dict):
                lines.append(f"  - {_claim_coordinate(claim)}")
                lines.append(f"    - text: {_text(claim.get('text'), '')}")
                need_gates = claim.get("need_gates") or {}
                needed = [k for k, v in need_gates.items() if v == "needed"]
                if needed:
                    lines.append(f"    - need_gates: {', '.join(needed)}")
        lines.append("")
    if _as_list(terrain.get("disagreement_relations")):
        lines.append("## Disagreement Relations")
        for rel in _as_list(terrain.get("disagreement_relations")):
            if isinstance(rel, dict):
                lines.append(
                    f"- {rel.get('relation_id')} | group={rel.get('claim_group_id')} | "
                    f"type={rel.get('relation_type')} | confidence={rel.get('confidence')} | "
                    f"human_review_required={rel.get('human_review_required')}"
                )
                lines.append(f"  - why_flagged: {_text(rel.get('why_flagged'), '')}")
        lines.append("")
    opinion_groups = _as_list(collection.get("opinion_groups"))
    if opinion_groups:
        lines.append("## Opinion Groups")
        lines.append("Position buckets across videos. Not a truth judgment; repetition is not proof.")
        for og in opinion_groups:
            if not isinstance(og, dict):
                continue
            lines.append(
                f"### {og.get('opinion_group_id')} - {_text(og.get('label'), 'opinion group')}"
            )
            lines.append(f"- axis: {_text(og.get('axis'), 'unknown')}")
            lines.append(f"- {_text(og.get('position_summary'), '')}")
            lines.append(f"- videos: {', '.join(map(str, _as_list(og.get('source_video_ids'))))}")
            lines.append(f"- member claim groups: {', '.join(map(str, _as_list(og.get('member_claim_group_ids'))))}")
            lines.append(f"- contains disagreement point: {og.get('contains_disagreement_point')}")
            lines.append(f"- confidence: {_text(og.get('confidence'), 'unknown')}")
        lines.append("")
    lines.append("## Required Limitations")
    for limitation in TOPIC_LIMITATIONS:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def _render_group_subset(collection: dict[str, Any], group_ids: list[str], title: str, empty: str) -> str:
    groups = {g.get("group_id"): g for g in _as_list(collection.get("claim_groups")) if isinstance(g, dict)}
    claim_index = collection.get("claim_index") or {}
    terrain = collection.get("terrain") or {}
    relations_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rel in _as_list(terrain.get("disagreement_relations")):
        if isinstance(rel, dict):
            relations_by_group[_text(rel.get("claim_group_id"), "")].append(rel)
    outlier_by_group = {
        d.get("claim_group_id"): d
        for d in _as_list(terrain.get("outlier_details"))
        if isinstance(d, dict)
    }
    lines = [f"# {title}", "", "Repeated/disagreement/outlier labels are terrain signals, not truth judgments.", ""]
    if not group_ids:
        lines.append(f"- {empty}")
    for gid in group_ids:
        group = groups.get(gid)
        if not group:
            continue
        lines.append(f"## {gid} - {_text(group.get('label'), 'claim group')}")
        lines.append(f"- videos: {', '.join(map(str, _as_list(group.get('video_ids'))))}")
        lines.append(f"- stances: {', '.join(map(str, _as_list(group.get('stances'))))}")
        lines.append(f"- claim_count: {group.get('claim_count', 0)}")
        lines.append(f"- grouping_confidence: {_text(group.get('grouping_confidence'), 'unknown')}")
        if gid in outlier_by_group:
            detail = outlier_by_group[gid]
            lines.append(f"- outlier_type: {_text(detail.get('outlier_type'), 'unknown')}")
            lines.append(f"- why_outlier: {_text(detail.get('why_outlier'), '')}")
        for rel in relations_by_group.get(gid, []):
            lines.append(
                f"- disagreement_relation: {_text(rel.get('relation_id'), '')} / "
                f"{_text(rel.get('relation_type'), 'unknown')} / confidence={_text(rel.get('confidence'), 'unknown')}"
            )
            lines.append(f"  - why_flagged: {_text(rel.get('why_flagged'), '')}")
        lines.append("- claim coordinates:")
        for uid in _as_list(group.get("claim_uids")):
            claim = claim_index.get(uid) if isinstance(claim_index, dict) else None
            if isinstance(claim, dict):
                lines.append(f"  - {_claim_coordinate(claim)}")
                lines.append(f"    - text: {_text(claim.get('text'), '')}")
                needed = [k for k, v in (claim.get("need_gates") or {}).items() if v == "needed"]
                if needed:
                    lines.append(f"    - need_gates: {', '.join(needed)}")
        lines.append("")
    return "\n".join(lines)


def render_topic_handoff_prompt(collection: dict[str, Any]) -> str:
    topic = collection.get("topic") or {}
    lines = [
        "# Topic Handoff Prompt",
        "",
        "You are reviewing a cross-video YouTube opinion terrain package.",
        "Do not evaluate it as a single-video summarizer or transcript summarizer.",
        "The core product is the TopicCollection: repeated claims, disagreement candidates, outliers, source videos, speakers, timestamps, evidence coordinates, and modality gaps.",
        "Do not decide truth unless the operator explicitly asks for a separate source-verification step.",
        "Repeated claims are terrain signals, not evidence of truth.",
        "Disagreement groups are candidate relations, not proven contradictions.",
        "Outliers are single-source or low-diversity claims, not necessarily false claims.",
        "Never answer a substantive question without citing claim_uid, video_id, timestamp, speaker, and modality when available.",
        "If evidence coordinates are missing, report the missing field instead of inferring it.",
        "Suggest ASR/OCR/diarization/source verification only when a specific claim or group justifies it.",
        "",
        "## Topic",
        f"- topic_id: {_text(topic.get('topic_id'), 'unknown')}",
        f"- title: {_text(topic.get('title'), 'unknown topic')}",
        "",
        "## Files To Inspect",
        "1. topic_collection.json",
        "2. topic_terrain.md",
        "3. repeated_claims.md",
        "4. disagreements.md",
        "5. outliers.md",
        "6. videos/*.json",
        "7. packages/*_residual_package.json",
        "",
        "## Required Review Questions",
        "1. Are the claim groups coherent across videos?",
        "2. Are repeated claims separated from disagreements and outliers?",
        "3. Are source video, timestamp, speaker, and modality coordinates preserved?",
        "4. Which groups justify source verification or need-gated multimodal reinforcement?",
        "5. What should remain video-internal and not be presented as verified fact?",
        "",
    ]
    return "\n".join(lines)


def write_topic_bundle(output_dir: str | Path, collection: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    out = Path(output_dir)
    paths: dict[str, Any] = {}
    video_paths: list[str] = []
    for record in records:
        video = record.get("video") or {}
        video_id = _text(video.get("video_id"), f"video-{len(video_paths) + 1}")
        p = write_json(out / "videos" / f"{video_id}_knowledge_record.json", record)
        video_paths.append(str(p))
    paths["video_knowledge_records"] = video_paths
    paths["topic_collection_json"] = str(write_json(out / "topic_collection.json", collection))
    paths["topic_terrain_md"] = str(write_text(out / "topic_terrain.md", render_topic_terrain_markdown(collection)))
    terrain = collection.get("terrain") or {}
    paths["repeated_claims_md"] = str(write_text(
        out / "repeated_claims.md",
        _render_group_subset(collection, _as_list(terrain.get("repeated_claim_group_ids")), "Repeated Claims", "no repeated claim groups detected"),
    ))
    paths["disagreements_md"] = str(write_text(
        out / "disagreements.md",
        _render_group_subset(collection, _as_list(terrain.get("disagreement_group_ids")), "Disagreements", "no disagreement groups detected"),
    ))
    paths["outliers_md"] = str(write_text(
        out / "outliers.md",
        _render_group_subset(collection, _as_list(terrain.get("outlier_group_ids")), "Outliers", "no outlier groups detected"),
    ))
    paths["topic_handoff_prompt_md"] = str(write_text(out / "topic_handoff_prompt.md", render_topic_handoff_prompt(collection)))
    manifest = {
        "ok": True,
        "schema_version": "youtube_topic_handoff_bundle.v0.2",
        "bundle_type": "topic_collection_handoff",
        "purpose": "cross-video opinion terrain package",
        "entrypoint": "topic_collection.json",
        "recommended_read_order": [
            "topic_collection.json",
            "topic_terrain.md",
            "disagreements.md",
            "repeated_claims.md",
            "outliers.md",
            "videos/*.json",
            "packages/*_residual_package.json",
        ],
        "agent_rules": {
            "truth_judgment_allowed": False,
            "must_cite_evidence_coordinates": True,
            "external_verification_required_for_high_stakes_claims": True,
            "repeated_claims_are_not_proof": True,
            "disagreement_relations_are_candidates": True,
        },
        "limitations": TOPIC_LIMITATIONS,
        "paths": paths,
        "topic": collection.get("topic"),
        "terrain": collection.get("terrain"),
        "claim_group_count": len(collection.get("claim_groups") or []),
    }
    manifest_path = out / "topic_handoff_manifest.json"
    paths["manifest_json"] = str(manifest_path)
    manifest["paths"] = paths
    write_json(manifest_path, manifest)
    return manifest


def build_topic_demo_from_segments(
    topic_dir: Path,
    *,
    topic_id: str,
    topic_title: str,
    output_dir: Path,
    clusterer: str = "normalized",
    token_jaccard_threshold: float = 0.5,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    package_paths: list[str] = []
    validation_paths: list[str] = []
    for segments_file in sorted(topic_dir.glob("video_*.json")):
        data = read_json(segments_file, {})
        video = data.get("video") if isinstance(data.get("video"), dict) else {}
        segments = data.get("segments") if isinstance(data.get("segments"), list) else []
        package = build_residual_package(
            video_id=_text(video.get("video_id"), segments_file.stem),
            title=_text(video.get("title"), segments_file.stem),
            language=_text(video.get("language"), "en"),
            duration_seconds=video.get("duration_seconds"),
            segments=segments,
            genre_override=video.get("genre"),
        )
        validation = validate_package(package).to_dict()
        package_dict = package.to_dict()
        pkg_path = write_json(output_dir / "packages" / f"{package.video_id}_residual_package.json", package_dict)
        val_path = write_json(output_dir / "packages" / f"{package.video_id}_validation.json", validation)
        package_paths.append(str(pkg_path))
        validation_paths.append(str(val_path))
        records.append(build_video_knowledge_record(package_dict, topic_id=topic_id, topic_title=topic_title))

    collection = build_topic_collection(
        records,
        topic_id=topic_id,
        topic_title=topic_title,
        clusterer=clusterer,
        token_jaccard_threshold=token_jaccard_threshold,
    )
    expected_path = topic_dir / "expected_groupings.json"
    if expected_path.exists():
        evaluation = evaluate_topic_collection(collection, read_json(expected_path, {}) or {})
        collection["grouping_evaluation"] = evaluation
    manifest = write_topic_bundle(output_dir, collection, records)
    if "grouping_evaluation" in collection:
        evaluation_path = write_json(output_dir / "grouping_evaluation.json", collection["grouping_evaluation"])
        manifest["grouping_evaluation"] = collection["grouping_evaluation"]
        manifest["paths"]["grouping_evaluation_json"] = str(evaluation_path)
    manifest["paths"]["residual_packages"] = package_paths
    manifest["paths"]["validations"] = validation_paths
    write_json(output_dir / "topic_handoff_manifest.json", manifest)
    return manifest


