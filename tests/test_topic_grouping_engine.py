from __future__ import annotations

import json
import pytest
from pathlib import Path

from youtube_intel.io_utils import read_json
from youtube_intel.topic_collection import (
    GROUPING_METHOD,
    CLUSTERERS,
    build_opinion_groups,
    build_topic_collection,
    build_topic_demo_from_segments,
    evaluate_topic_collection,
)


def test_grouping_method_is_alpha_not_synthetic_keyword_demo() -> None:
    assert GROUPING_METHOD["name"] == "deterministic_normalized_similarity_alpha"
    assert GROUPING_METHOD["requires_upgrade_for_real_topics"] is True
    assert "embedding" in GROUPING_METHOD["optional_upgrade_path"]


def test_labeled_topic_fixture_scores_pair_agreement(tmp_path: Path) -> None:
    # The orchard fixture score is an IN-DOMAIN REGRESSION measurement, not a
    # benchmark: the must_link labels encode semantic topic relatedness, while
    # the alpha clusterer uses lexical normalized similarity. The complete-link
    # cohesion rule (P1-A) deliberately separates weakly bridged claims, so the
    # fixture score moved from 0.875 (single-link, bridge chaining) to ~0.625.
    # The floor here only guards against regressions below the documented
    # complete-link baseline; expected_groupings.json remains the untouched
    # human-labeled ground truth.
    root = Path(__file__).resolve().parents[1]
    topic_dir = root / "examples" / "topic_demo"
    manifest = build_topic_demo_from_segments(
        topic_dir,
        topic_id="synthetic-orchard-sensors",
        topic_title="Synthetic orchard sensor adoption terrain",
        output_dir=tmp_path,
    )
    evaluation = manifest["grouping_evaluation"]
    assert evaluation["score"] >= 0.6
    assert evaluation["total"] >= 6
    assert Path(manifest["paths"]["grouping_evaluation_json"]).exists()


def test_topic_collection_records_contradiction_candidates(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = build_topic_demo_from_segments(
        root / "examples" / "topic_demo",
        topic_id="synthetic-orchard-sensors",
        topic_title="Synthetic orchard sensor adoption terrain",
        output_dir=tmp_path,
    )
    collection = json.loads(Path(manifest["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))
    assert collection["terrain"]["truth_status"] == "not_evaluated"
    assert collection["terrain"]["contradiction_candidates"]
    assert all(item["status"] == "candidate_requires_human_review" for item in collection["terrain"]["contradiction_candidates"])


def test_evaluation_function_reports_fail_for_bad_fixture(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = build_topic_demo_from_segments(
        root / "examples" / "topic_demo",
        topic_id="synthetic-orchard-sensors",
        topic_title="Synthetic orchard sensor adoption terrain",
        output_dir=tmp_path,
    )
    collection = json.loads(Path(manifest["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))
    expected = read_json(root / "examples" / "topic_demo" / "expected_groupings.json", {})
    result = evaluate_topic_collection(collection, expected)
    # The labeled fixture scores as a documented in-domain regression baseline
    # (see test_labeled_topic_fixture_scores_pair_agreement), so the evaluator
    # itself must still report a score and a status consistently.
    assert result["score"] >= 0.6
    bad = {"threshold": 1.0, "must_link": [[
        "The subsidy deadline is pushing sensor adoption faster than farmer demand.",
        "This might be wrong, but local salinity may explain the yield bump more than the sensor software.",
    ]]}
    bad_result = evaluate_topic_collection(collection, bad)
    assert bad_result["status"] == "fail"
    assert bad_result["score"] < result["score"]


def _claim(video_id: str, cid: str, text: str, stance: str, support_role: str) -> dict:
    evidence_id = f"{video_id}:E{cid}"
    return {
        "claim_uid": f"{video_id}:{cid}",
        "text": text,
        "source_video_id": video_id,
        "stance": stance,
        "support_role": support_role,
        "evidence_ids": [evidence_id],
        "evidence_coordinate": {
            "evidence_id": evidence_id,
            "video_id": video_id,
            "timestamp_start": 0.0,
            "timestamp_end": 4.0,
            "time_ref": "00:00",
            "speaker": "A",
            "speaker_confidence": "high",
            "modality": ["caption"],
        },
        "modality_sources": ["caption"],
    }


def _evidence(video_id: str, cid: str, text: str) -> dict:
    return {
        "evidence_id": f"{video_id}:E{cid}",
        "video_id": video_id,
        "timestamp_start": 0.0,
        "timestamp_end": 4.0,
        "time_ref": "00:00",
        "speaker": "A",
        "speaker_confidence": "high",
        "modality": ["caption"],
        "text": text,
        "confidence": "medium",
    }


def _two_video_records() -> list[dict]:
    return [
        {
            "video": {"video_id": "v1", "title": "T", "role_in_topic": "source", "transcript_source": "caption", "transcript_quality": "high"},
            "claim_records": [
                _claim(
                    "v1", "c1",
                    "The vendor says the kit can cut water use by twenty percent.",
                    "claim_or_promotion", "supporting_or_promotional",
                ),
            ],
            "evidence_records": [
                _evidence("v1", "c1", "The vendor says the kit can cut water use by twenty percent."),
            ],
        },
        {
            "video": {"video_id": "v2", "title": "T", "role_in_topic": "source", "transcript_source": "caption", "transcript_quality": "high"},
            "claim_records": [
                _claim(
                    "v2", "c1",
                    "The kit can cut water use, the vendor claims twenty percent.",
                    "claim_or_promotion", "supporting_or_promotional",
                ),
                _claim(
                    "v2", "c2",
                    "But local soil and maintenance discipline may explain it, not the device.",
                    "caution_or_counterpoint", "challenging_or_limiting",
                ),
            ],
            "evidence_records": [
                _evidence("v2", "c1", "The kit can cut water use, the vendor claims twenty percent."),
                _evidence("v2", "c2", "But local soil and maintenance discipline may explain it, not the device."),
            ],
        },
    ]


def test_clusterer_options_are_exposed_and_both_run() -> None:
    assert set(CLUSTERERS) == {"normalized", "token_jaccard"}
    records = _two_video_records()
    for clusterer in CLUSTERERS:
        collection = build_topic_collection(records, topic_id="t", topic_title="T", clusterer=clusterer)
        assert collection["clusterer"] == clusterer
        assert collection["claim_groups"]


def test_unknown_clusterer_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_topic_collection(_two_video_records(), topic_id="t", topic_title="T", clusterer="bogus")


def test_opinion_groups_are_cross_video_position_buckets() -> None:
    collection = build_topic_collection(_two_video_records(), topic_id="t", topic_title="T")
    opinion_groups = collection["opinion_groups"]
    assert opinion_groups, "expected at least one cross-video opinion group"
    supporting = [og for og in opinion_groups if og["axis"] == "supporting"]
    assert supporting, "supporting position should span both videos"
    og = supporting[0]
    assert len(og["source_video_ids"]) >= 2
    assert og["truth_status"] == "not_evaluated"
    assert collection["terrain"]["opinion_group_ids"] == [o["opinion_group_id"] for o in opinion_groups]


def test_single_video_opinion_groups_are_suppressed_by_default() -> None:
    single = _two_video_records()[:1]
    collection = build_topic_collection(single, topic_id="t", topic_title="T")
    assert collection["opinion_groups"] == []
    assert any(
        w.startswith("opinion_group_skipped_single_source")
        for w in collection["terrain"]["opinion_group_warnings"]
    )
    # but the builder can be asked to allow them explicitly
    groups = collection["claim_groups"]
    allowed, _ = build_opinion_groups(groups, allow_single_video=True)
    assert allowed, "single-video opinion groups should appear when explicitly allowed"
