"""Claim-level provenance tests: cue indices, timestamps, span, speaker,
modality, and source hint must survive assembly and serialization exactly."""

from __future__ import annotations

from youtube_intel.topic_collection import build_video_knowledge_record
from youtube_residual import build_residual_package


def _segments():
    return [
        {
            "text": "센서 키트가 물 사용량을",
            "time_ref": "00:12",
            "speaker": "vendor_rep",
            "source_hint": "transcript",
            "modality_source": "transcript",
        },
        {
            "text": "20퍼센트 줄일 수 있다고 말합니다",
            "time_ref": "00:15",
            "speaker": "vendor_rep",
            "source_hint": "transcript",
            "modality_source": "transcript",
        },
        {
            "text": "하지만 유지보수 비용은",
            "time_ref": "00:18",
            "speaker": "operator_note",
            "source_hint": "transcript",
            "modality_source": "transcript",
        },
        {
            "text": "공개되지 않았습니다",
            "time_ref": "00:21",
            "speaker": "operator_note",
            "source_hint": "transcript",
            "modality_source": "transcript",
        },
    ]


def _package(sentence_mode: bool):
    return build_residual_package(
        video_id="provenance-video",
        title="Provenance Test Video",
        language="ko",
        segments=_segments(),
        claim_assembly="sentence" if sentence_mode else "cue",
    )


def test_speaker_change_is_not_merged_into_one_claim():
    package = _package(sentence_mode=True)
    speakers = [c.speaker for c in package.claim_candidates]
    assert "vendor_rep" in speakers
    assert "operator_note" in speakers
    # No single candidate may contain text from both speakers.
    for c in package.claim_candidates:
        if c.speaker == "vendor_rep":
            assert "유지보수" not in c.text
        if c.speaker == "operator_note":
            assert "센서" not in c.text


def test_serialized_candidates_keep_full_provenance():
    package = _package(sentence_mode=True)
    first = package.claim_candidates[0]
    d = first.to_dict()
    assert d["cue_indices"] == [0, 1]
    assert d["source_time_refs"] == ["00:12", "00:15"]
    assert d["span_start"] == 12.0
    # Legacy time_ref-only input: no end timestamp exists, so span_end is None
    # (a duration is never fabricated from the final cue start).
    assert d["span_end"] is None
    assert d["source_cue_coordinates"] == [
        {"cue_index": 0, "time_ref": "00:12", "start": 12.0, "end": None},
        {"cue_index": 1, "time_ref": "00:15", "start": 15.0, "end": None},
    ]
    assert d["speaker"] == "vendor_rep"
    assert d["modality_source"] == "transcript"
    assert d["source_hint"] == "transcript"
    assert d["text"] == "센서 키트가 물 사용량을 20퍼센트 줄일 수 있다고 말합니다"


def test_no_cue_index_loss_in_serialized_output():
    package = _package(sentence_mode=True)
    seen: list[int] = []
    for c in package.claim_candidates:
        seen.extend(c.to_dict()["cue_indices"])
    assert sorted(seen) == [0, 1, 2, 3]


def test_no_fabricated_speaker_attribution():
    package = _package(sentence_mode=True)
    for c in package.claim_candidates:
        # The speaker must always come from the source segment, never invented.
        source_speakers = {s["speaker"] for s in _segments()}
        assert c.speaker in source_speakers


def test_knowledge_record_preserves_cue_provenance():
    package = _package(sentence_mode=True)
    record = build_video_knowledge_record(
        package.to_dict(),
        topic_id="provenance-topic",
        topic_title="Provenance Topic",
    )
    claims = record["claim_records"]
    evidence = record["evidence_records"]
    assert len(claims) == len(package.claim_candidates)
    assert len(evidence) == len(package.claim_candidates)
    for claim, ev in zip(claims, evidence):
        assert claim["cue_indices"] == ev["cue_indices"]
        assert claim["source_time_refs"] == ev["source_time_refs"]
        assert claim["span_start"] == ev["span_start"]
        assert claim["span_end"] == ev["span_end"]
    # Every cue index from the source stream appears exactly once.
    all_indices = [i for c in claims for i in c["cue_indices"]]
    assert sorted(all_indices) == [0, 1, 2, 3]


def test_cue_mode_has_empty_provenance_fields():
    package = _package(sentence_mode=False)
    d = package.claim_candidates[0].to_dict()
    assert d["cue_indices"] == []
    assert d["source_time_refs"] == []
    assert d["span_start"] is None
    assert d["span_end"] is None


# --- Section 2: structured cue timing provenance through every layer ---


def _structured_segments():
    return [
        {
            "text": "센서 키트가 물 사용량을",
            "start": 12.0,
            "end": 14.8,
            "time_ref": "00:12",
            "speaker": "vendor_rep",
            "source_hint": "transcript",
            "modality_source": "transcript",
        },
        {
            "text": "20퍼센트 줄일 수 있다고 말합니다",
            "start": 15.0,
            "end": 17.1,
            "time_ref": "00:15",
            "speaker": "vendor_rep",
            "source_hint": "transcript",
            "modality_source": "transcript",
        },
    ]


def test_claim_candidate_serializes_cue_coordinates():
    package = build_residual_package(
        video_id="provenance-video",
        title="Provenance Test Video",
        language="ko",
        segments=_structured_segments(),
        claim_assembly="sentence",
    )
    d = package.claim_candidates[0].to_dict()
    assert d["source_cue_coordinates"] == [
        {"cue_index": 0, "time_ref": "00:12", "start": 12.0, "end": 14.8},
        {"cue_index": 1, "time_ref": "00:15", "start": 15.0, "end": 17.1},
    ]
    assert d["span_start"] == 12.0
    assert d["span_end"] == 17.1


def test_residual_package_to_dict_serializes_cue_coordinates():
    package = build_residual_package(
        video_id="provenance-video",
        title="Provenance Test Video",
        language="ko",
        segments=_structured_segments(),
        claim_assembly="sentence",
    )
    claim = package.to_dict()["claim_candidates"][0]
    assert len(claim["source_cue_coordinates"]) == 2
    assert claim["source_cue_coordinates"][1]["end"] == 17.1


def test_video_knowledge_record_serializes_cue_coordinates():
    package = build_residual_package(
        video_id="provenance-video",
        title="Provenance Test Video",
        language="ko",
        segments=_structured_segments(),
        claim_assembly="sentence",
    )
    record = build_video_knowledge_record(
        package.to_dict(), topic_id="t", topic_title="T"
    )
    claim = record["claim_records"][0]
    evidence = record["evidence_records"][0]
    assert claim["source_cue_coordinates"] == evidence["source_cue_coordinates"]
    assert len(claim["source_cue_coordinates"]) == 2
    assert claim["source_cue_coordinates"][0]["start"] == 12.0
    assert claim["source_cue_coordinates"][1]["end"] == 17.1


def test_topic_collection_evidence_records_keep_cue_coordinates(tmp_path):
    from youtube_intel.topic_collection import build_topic_collection

    package = build_residual_package(
        video_id="provenance-video",
        title="Provenance Test Video",
        language="ko",
        segments=_structured_segments(),
        claim_assembly="sentence",
    )
    record = build_video_knowledge_record(
        package.to_dict(), topic_id="t", topic_title="T"
    )
    collection = build_topic_collection(
        [record], topic_id="t", topic_title="T", allow_single_video_opinions=True
    )
    evidence_index = collection["evidence_index"]
    claim_index = collection["claim_index"]
    assert evidence_index, "expected evidence records"
    ev = next(iter(evidence_index.values()))
    assert len(ev["source_cue_coordinates"]) == 2
    claim = next(iter(claim_index.values()))
    assert len(claim["source_cue_coordinates"]) == 2
    assert claim["span_start"] == 12.0
    assert claim["span_end"] == 17.1
    # TopicCollection claim groups must also resolve every cue coordinate.
    for group in collection["claim_groups"]:
        for coord in group.get("evidence_coordinates", []):
            assert coord["evidence_id"] in evidence_index
