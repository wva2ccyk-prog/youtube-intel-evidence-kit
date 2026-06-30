from __future__ import annotations

import json
from pathlib import Path

from youtube_intel.io_utils import read_json
from youtube_intel.topic_collection import (
    GROUPING_METHOD,
    build_topic_demo_from_segments,
    evaluate_topic_collection,
)


def test_grouping_method_is_alpha_not_synthetic_keyword_demo() -> None:
    assert GROUPING_METHOD["name"] == "deterministic_normalized_similarity_alpha"
    assert GROUPING_METHOD["requires_upgrade_for_real_topics"] is True
    assert "embedding" in GROUPING_METHOD["optional_upgrade_path"]


def test_labeled_topic_fixture_scores_pair_agreement(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    topic_dir = root / "examples" / "topic_demo"
    manifest = build_topic_demo_from_segments(
        topic_dir,
        topic_id="synthetic-orchard-sensors",
        topic_title="Synthetic orchard sensor adoption terrain",
        output_dir=tmp_path,
    )
    evaluation = manifest["grouping_evaluation"]
    assert evaluation["status"] == "pass"
    assert evaluation["score"] >= 0.75
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
    assert result["status"] == "pass"
    bad = {"threshold": 1.0, "must_link": [["The subsidy deadline is pushing sensor adoption faster than farmer demand.", "This might be wrong, but local salinity may explain the yield bump more than the sensor software."]]}
    assert evaluate_topic_collection(collection, bad)["status"] == "fail"
