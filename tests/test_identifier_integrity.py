"""P0-C: global identifier uniqueness and reference integrity.

`build_topic_collection` must fail closed (EvidenceIntegrityError) when
video_id / claim_uid / evidence_id / local claim ids are duplicated, empty,
or reserved-fallback, and when cross-references dangle or declared counts
disagree with actual arrays. Silent overwrites in maps must never happen.
"""

from __future__ import annotations

import pytest

from youtube_intel.errors import EvidenceIntegrityError
from youtube_intel.topic_collection import build_topic_collection, validate_topic_inputs


def _claim(uid: str, video_id: str, evidence_ids: tuple[str, ...] = (), local_id: str | None = None) -> dict:
    return {
        "claim_uid": uid,
        "source_video_id": video_id,
        "local_claim_id": local_id or uid.rsplit(":", 1)[-1],
        "text": "sample claim text about sensor maintenance",
        "canonical_text": "sample claim text about sensor maintenance",
        "speaker": "A",
        "speaker_confidence": "high",
        "time_ref": "00:00",
        "timestamp_start": 0.0,
        "timestamp_end": None,
        "content_type": "technical_explanation",
        "evidence": "video_internal",
        "evidence_ids": list(evidence_ids),
        "evidence_coordinate": {"video_id": video_id, "evidence_id": "x"},
        "confidence": "medium",
        "modality_sources": ["caption"],
        "claim_group_key": "k",
        "stance": "reported_claim",
        "support_role": "reported_context",
        "verification_status": "video_internal_not_fact_checked",
        "need_gates": {},
    }


def _evidence(eid: str, video_id: str) -> dict:
    return {
        "evidence_id": eid,
        "video_id": video_id,
        "timestamp_start": 0.0,
        "timestamp_end": None,
        "time_ref": "00:00",
        "speaker": "A",
        "speaker_confidence": "high",
        "modality": ["caption"],
        "text": "sample evidence text",
        "confidence": "medium",
        "source_separation": "video_internal_claim_not_external_source",
    }


def _record(video_id: str, claims: list[dict], evidence: list[dict], counts: dict | None = None) -> dict:
    return {
        "schema_version": "youtube_video_knowledge_record_v0.1",
        "topic": {"topic_id": "t", "title": "T"},
        "video": {
            "video_id": video_id,
            "title": "Video",
            "language": "en",
            "role_in_topic": "source_video",
            "transcript_source": "synthetic_caption_fixture",
            "transcript_quality": "demo_high",
        },
        "analysis_layer": "single_video_input_for_topic_collection",
        "truth_status": "not_evaluated",
        "fact_check_status": "not_performed",
        "claim_records": claims,
        "evidence_records": evidence,
        "counts": counts,
        "limitations": [],
    }


def _run(records: list[dict]) -> None:
    build_topic_collection(records, topic_id="t", topic_title="T")


def test_empty_video_id_rejected():
    records = [
        _record("", [_claim(":C1", "")], [_evidence(":E1", "")]),
    ]
    with pytest.raises(EvidenceIntegrityError, match="video_id is empty"):
        _run(records)


def test_empty_claim_uid_rejected():
    records = [
        _record("vid-a", [_claim("", "vid-a")], [_evidence("vid-a:E1", "vid-a")]),
    ]
    with pytest.raises(EvidenceIntegrityError, match="claim_uid is empty"):
        _run(records)


def test_empty_evidence_id_rejected():
    records = [
        _record("vid-a", [_claim("vid-a:C1", "vid-a", ("",))], [_evidence("", "vid-a")]),
    ]
    with pytest.raises(EvidenceIntegrityError, match="evidence_id is empty"):
        _run(records)


def test_repeated_fallback_video_id_rejected():
    records = [
        _record("unknown-video", [_claim("unknown-video:C1", "unknown-video")], [_evidence("unknown-video:E1", "unknown-video")]),
        _record("vid-b", [_claim("vid-b:C1", "vid-b")], [_evidence("vid-b:E1", "vid-b")]),
    ]
    with pytest.raises(EvidenceIntegrityError, match="reserved fallback id"):
        _run(records)


def test_duplicate_local_claim_id_within_video_rejected():
    records = [
        _record(
            "vid-a",
            [_claim("vid-a:C1", "vid-a", local_id="C1"), _claim("vid-a:C2", "vid-a", local_id="C1")],
            [_evidence("vid-a:E1", "vid-a"), _evidence("vid-a:E2", "vid-a")],
        ),
    ]
    with pytest.raises(EvidenceIntegrityError, match="duplicate local claim id 'C1' within video 'vid-a'"):
        _run(records)


def test_dangling_source_video_rejected():
    records = [
        _record("vid-a", [_claim("vid-a:C1", "vid-nonexistent")], [_evidence("vid-a:E1", "vid-a")]),
    ]
    with pytest.raises(EvidenceIntegrityError, match="does not resolve to any video"):
        _run(records)


def test_dangling_evidence_reference_rejected():
    records = [
        _record("vid-a", [_claim("vid-a:C1", "vid-a", ("vid-a:E99",))], [_evidence("vid-a:E1", "vid-a")]),
    ]
    with pytest.raises(EvidenceIntegrityError, match="evidence_id 'vid-a:E99' does not resolve"):
        _run(records)


def test_dangling_evidence_owner_rejected():
    records = [
        _record("vid-a", [_claim("vid-a:C1", "vid-a")], [_evidence("vid-a:E1", "vid-nonexistent")]),
    ]
    with pytest.raises(EvidenceIntegrityError, match="does not resolve to any video"):
        _run(records)


def test_declared_claim_count_mismatch_rejected():
    records = [
        _record(
            "vid-a",
            [_claim("vid-a:C1", "vid-a")],
            [_evidence("vid-a:E1", "vid-a")],
            counts={"claim_total": 5, "evidence_total": 1},
        ),
    ]
    with pytest.raises(EvidenceIntegrityError, match="declared claim_total 5 != actual claim_records 1"):
        _run(records)


def test_declared_evidence_count_mismatch_rejected():
    records = [
        _record(
            "vid-a",
            [_claim("vid-a:C1", "vid-a")],
            [_evidence("vid-a:E1", "vid-a")],
            counts={"claim_total": 1, "evidence_total": 7},
        ),
    ]
    with pytest.raises(EvidenceIntegrityError, match="declared evidence_total 7 != actual evidence_records 1"):
        _run(records)


def test_validate_topic_inputs_returns_issues_without_raising():
    records = [
        _record("vid-a", [_claim("vid-a:C1", "vid-a")], [_evidence("vid-a:E1", "vid-a")]),
        _record("vid-a", [_claim("vid-a:C2", "vid-a")], [_evidence("vid-a:E2", "vid-a")]),
    ]
    issues = validate_topic_inputs(records)
    assert issues, "duplicate video ids must be reported as issues"
    assert any("duplicate video_id" in issue for issue in issues)


def test_valid_records_pass():
    records = [
        _record(
            "vid-a",
            [_claim("vid-a:C1", "vid-a", ("vid-a:E1",))],
            [_evidence("vid-a:E1", "vid-a")],
            counts={"claim_total": 1, "evidence_total": 1},
        ),
        _record(
            "vid-b",
            [_claim("vid-b:C1", "vid-b", ("vid-b:E1",))],
            [_evidence("vid-b:E1", "vid-b")],
            counts={"claim_total": 1, "evidence_total": 1},
        ),
    ]
    collection = build_topic_collection(records, topic_id="t", topic_title="T")
    assert collection["claim_total"] == 2

