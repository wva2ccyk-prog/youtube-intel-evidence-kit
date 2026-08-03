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
    coord_evidence_id = evidence_ids[0] if evidence_ids else "x"
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
        "evidence_coordinate": {
            "video_id": video_id,
            "evidence_id": coord_evidence_id,
            "timestamp_start": 0.0,
            "timestamp_end": None,
            "time_ref": "00:00",
            "speaker": "A",
            "speaker_confidence": "high",
            "modality": ["caption"],
        },
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


# --- Section 8: strengthened topic input and evidence reference integrity ---


from youtube_intel.topic_collection import validate_topic_collection_document


def _valid_record() -> dict:
    return _record(
        "vid-a",
        [_claim("vid-a:C1", "vid-a", ("vid-a:E1",))],
        [_evidence("vid-a:E1", "vid-a")],
    )


def test_empty_claim_source_video_rejected():
    claim = _claim("vid-a:C1", "vid-a", ("vid-a:E1",))
    claim["source_video_id"] = ""
    issues = validate_topic_inputs([_record("vid-a", [claim], [_evidence("vid-a:E1", "vid-a")])])
    assert any("source_video_id is empty" in i for i in issues)


def test_empty_evidence_owner_video_rejected():
    evidence = _evidence("vid-a:E1", "vid-a")
    evidence["video_id"] = ""
    issues = validate_topic_inputs([_record("vid-a", [_claim("vid-a:C1", "vid-a", ("vid-a:E1",))], [evidence])])
    assert any("video_id is empty" in i for i in issues)


def test_claim_with_no_evidence_ids_rejected():
    issues = validate_topic_inputs([_record("vid-a", [_claim("vid-a:C1", "vid-a")], [])])
    assert any("no evidence ids" in i for i in issues)


def test_coordinate_id_not_in_claim_evidence_ids_rejected():
    claim = _claim("vid-a:C1", "vid-a", ("vid-a:E1",))
    claim["evidence_coordinate"]["evidence_id"] = "other-id"
    issues = validate_topic_inputs([
        _record("vid-a", [claim], [_evidence("vid-a:E1", "vid-a")])
    ])
    assert any("not in evidence_ids" in i for i in issues)


def test_coordinate_id_dangling_rejected():
    claim = _claim("vid-a:C1", "vid-a", ("vid-a:E1",))
    claim["evidence_ids"] = ["vid-a:E1", "missing-e"]
    claim["evidence_coordinate"]["evidence_id"] = "missing-e"
    issues = validate_topic_inputs([
        _record("vid-a", [claim], [_evidence("vid-a:E1", "vid-a")])
    ])
    assert any("does not resolve" in i for i in issues)


def test_coordinate_timestamp_mismatch_rejected():
    claim = _claim("vid-a:C1", "vid-a", ("vid-a:E1",))
    claim["evidence_coordinate"]["timestamp_start"] = 99.0  # evidence has 0.0
    issues = validate_topic_inputs([
        _record("vid-a", [claim], [_evidence("vid-a:E1", "vid-a")])
    ])
    assert any("timestamp_start" in i and "does not match" in i for i in issues)


def test_coordinate_speaker_mismatch_rejected():
    claim = _claim("vid-a:C1", "vid-a", ("vid-a:E1",))
    claim["evidence_coordinate"]["speaker"] = "Mr-X"  # evidence has "A"
    issues = validate_topic_inputs([
        _record("vid-a", [claim], [_evidence("vid-a:E1", "vid-a")])
    ])
    assert any("coordinate.speaker" in i for i in issues)


def test_coordinate_modality_mismatch_rejected():
    claim = _claim("vid-a:C1", "vid-a", ("vid-a:E1",))
    claim["evidence_coordinate"]["modality"] = ["ocr"]  # evidence has ["caption"]
    issues = validate_topic_inputs([
        _record("vid-a", [claim], [_evidence("vid-a:E1", "vid-a")])
    ])
    assert any("coordinate.modality" in i for i in issues)


def test_non_dict_claim_row_rejected():
    record = _valid_record()
    record["claim_records"].append("not-a-dict")
    issues = validate_topic_inputs([record])
    assert any("claim row" in i and "not an object" in i for i in issues)


def test_non_dict_evidence_row_rejected():
    record = _valid_record()
    record["evidence_records"].append(42)
    issues = validate_topic_inputs([record])
    assert any("evidence row" in i and "not an object" in i for i in issues)


# --- collection-level integrity (validate_topic_collection_document) ----------


def _base_collection() -> dict:
    return {
        "schema_version": "youtube_topic_collection_v0.1",
        "topic": {"topic_id": "t", "title": "T", "final_objective": "o"},
        "source_videos": [{"video_id": "vid-a"}],
        "analysis_layer": "cross_video_topic_collection",
        "claim_groups": [
            {
                "group_id": "G0001",
                "claim_group_key": "k",
                "label": "L",
                "claim_count": 1,
                "claim_uids": ["vid-a:C1"],
                "member_claim_uids": ["vid-a:C1"],
                "representative_claim_uid": "vid-a:C1",
                "evidence_ids": ["vid-a:E1"],
                "evidence_coordinates": [],
            }
        ],
        "terrain": {},
        "claim_index": {"vid-a:C1": {"claim_uid": "vid-a:C1"}},
        "evidence_index": {
            "vid-a:E1": {"evidence_id": "vid-a:E1", "video_id": "vid-a", "timestamp_start": 0.0, "timestamp_end": None, "time_ref": "00:00", "speaker": "A", "speaker_confidence": "high", "modality": ["caption"]}
        },
        "grouping_method": {},
        "provenance": {},
        "limitations": [],
        "claim_total": 1,
    }


def test_dangling_group_claim_uid_rejected():
    c = _base_collection()
    c["claim_groups"][0]["claim_uids"] = ["ghost-claim"]
    assert any("member claim uid does not resolve" in i for i in validate_topic_collection_document(c))


def test_dangling_group_evidence_id_rejected():
    c = _base_collection()
    c["claim_groups"][0]["evidence_ids"] = ["ghost-evidence"]
    assert any("evidence id does not resolve" in i for i in validate_topic_collection_document(c))


def test_invalid_representative_claim_uid_rejected():
    c = _base_collection()
    c["claim_groups"][0]["representative_claim_uid"] = "not-in-group"
    assert any("representative_claim_uid" in i for i in validate_topic_collection_document(c))


def test_incorrect_group_claim_count_rejected():
    c = _base_collection()
    c["claim_groups"][0]["claim_count"] = 5  # actual member uids = 1
    assert any("claim_count 5 != member uids 1" in i for i in validate_topic_collection_document(c))


def test_incorrect_collection_claim_total_rejected():
    c = _base_collection()
    c["claim_total"] = 99  # claim_index size = 1
    assert any("claim_total 99 != claim_index size 1" in i for i in validate_topic_collection_document(c))


def test_duplicate_coordinate_id_rejected():
    c = _base_collection()
    coord = {"evidence_id": "vid-a:E1", "video_id": "vid-a", "timestamp_start": 0.0, "timestamp_end": None, "time_ref": "00:00", "speaker": "A", "speaker_confidence": "high", "modality": ["caption"]}
    c["claim_groups"][0]["evidence_coordinates"] = [coord, dict(coord)]
    assert any("duplicate coordinate evidence id" in i for i in validate_topic_collection_document(c))
