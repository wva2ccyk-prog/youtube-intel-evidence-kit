from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from youtube_intel._fixtures import fixture_path
from youtube_intel.errors import InvalidInputError
from youtube_intel.reporting import validate_handoff_inputs, write_handoff_bundle
from youtube_intel.sentence_assembly import parse_structured_timestamp
from youtube_intel.topic_collection import (
    build_topic_demo_from_segments,
    validate_topic_collection_document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _collection(tmp_path: Path) -> dict:
    manifest = build_topic_demo_from_segments(
        fixture_path("topic_demo"),
        topic_id="contract-hardening",
        topic_title="Contract hardening",
        output_dir=tmp_path,
    )
    return json.loads(Path(manifest["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))


def _schema_errors(document: dict) -> list:
    schema = json.loads((REPO_ROOT / "schemas" / "topic_collection.schema.json").read_text(encoding="utf-8"))
    return list(Draft202012Validator(schema).iter_errors(document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("relation_type", {}),
        ("confidence", 123),
        ("human_review_required", "yes"),
        ("why_flagged", None),
    ],
)
def test_runtime_rejects_invalid_disagreement_relation_fields(tmp_path: Path, field: str, value) -> None:
    document = _collection(tmp_path)
    assert document["terrain"]["disagreement_relations"]
    document["terrain"]["disagreement_relations"][0][field] = value
    assert validate_topic_collection_document(document)
    assert _schema_errors(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("outlier_type", []),
        ("followup_priority", "urgent"),
        ("why_outlier", None),
    ],
)
def test_runtime_rejects_invalid_outlier_fields(tmp_path: Path, field: str, value) -> None:
    document = _collection(tmp_path)
    assert document["terrain"]["outlier_details"]
    document["terrain"]["outlier_details"][0][field] = value
    assert validate_topic_collection_document(document)
    assert _schema_errors(document)


def test_runtime_rejects_non_boolean_operator_judgment(tmp_path: Path) -> None:
    document = _collection(tmp_path)
    document["terrain"]["operator_judgment_required"] = "true"
    assert any("operator_judgment_required" in issue for issue in validate_topic_collection_document(document))
    assert _schema_errors(document)


@pytest.mark.parametrize("field", ["relation_type", "confidence", "human_review_required", "why_flagged"])
def test_schema_and_runtime_reject_missing_disagreement_relation_fields(tmp_path: Path, field: str) -> None:
    document = _collection(tmp_path)
    assert document["terrain"]["disagreement_relations"]
    document["terrain"]["disagreement_relations"][0].pop(field)
    assert validate_topic_collection_document(document)
    assert _schema_errors(document)


@pytest.mark.parametrize("field", ["outlier_type", "followup_priority", "why_outlier"])
def test_schema_and_runtime_reject_missing_outlier_fields(tmp_path: Path, field: str) -> None:
    document = _collection(tmp_path)
    assert document["terrain"]["outlier_details"]
    document["terrain"]["outlier_details"][0].pop(field)
    assert validate_topic_collection_document(document)
    assert _schema_errors(document)


def test_schema_and_runtime_both_reject_null_source_title(tmp_path: Path) -> None:
    document = _collection(tmp_path)
    document["source_videos"][0]["title"] = None
    assert validate_topic_collection_document(document)
    assert _schema_errors(document)


def test_schema_and_runtime_both_reject_null_coordinate_confidence(tmp_path: Path) -> None:
    document = _collection(tmp_path)
    evidence_id = next(iter(document["evidence_index"]))
    document["evidence_index"][evidence_id]["speaker_confidence"] = None
    for claim in document["claim_index"].values():
        if claim["evidence_coordinate"]["evidence_id"] == evidence_id:
            claim["evidence_coordinate"]["speaker_confidence"] = None
    for group in document["claim_groups"]:
        for coordinate in group["evidence_coordinates"]:
            if coordinate["evidence_id"] == evidence_id:
                coordinate["speaker_confidence"] = None
    assert validate_topic_collection_document(document)
    assert _schema_errors(document)


def test_schema_and_runtime_both_require_evidence_speaker_confidence(tmp_path: Path) -> None:
    document = _collection(tmp_path)
    evidence_id = next(iter(document["evidence_index"]))
    document["evidence_index"][evidence_id].pop("speaker_confidence")
    assert validate_topic_collection_document(document)
    assert _schema_errors(document)


@pytest.mark.parametrize("value", ["00:60", "01:-05", "01:60:00", "01:02:60", "1.5:30"])
def test_strict_timestamp_rejects_invalid_clock_components(value: str) -> None:
    with pytest.raises(InvalidInputError):
        parse_structured_timestamp(value, field="timestamp")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("90:00", 5400.0), ("01:02:03.125", 3723.125), ("00:59.999", 59.999)],
)
def test_strict_timestamp_accepts_valid_clock_components(value: str, expected: float) -> None:
    assert parse_structured_timestamp(value, field="timestamp") == expected


def _handoff_pair() -> tuple[dict, dict]:
    package = {
        "schema_version": "youtube_residual_v0.1",
        "video": {"video_id": "v1", "title": "Title", "language": "en"},
        "claim_candidates": [
            {
                "claim_id": "C0001",
                "text": "A claim",
                "content_type": "other",
                "evidence": "video_internal",
                "confidence": "medium",
                "time_ref": None,
            }
        ],
    }
    worth = {
        "schema_version": "youtube_analysis_worth_v0.1",
        "video": {"video_id": "v1", "title": "Title"},
        "decision": {"analysis_worth": "maybe", "recommended_route": "review"},
        "source_trace": [
            {
                "claim_id": "C0001",
                "claim_type": "other",
                "evidence": "video_internal",
                "confidence": "medium",
                "time_ref": None,
            }
        ],
    }
    return package, worth


@pytest.mark.parametrize("field", ["content_type", "evidence", "confidence", "time_ref"])
def test_handoff_rejects_missing_source_semantic_field(field: str) -> None:
    package, worth = _handoff_pair()
    package["claim_candidates"][0].pop(field)
    assert validate_handoff_inputs(package, worth)


@pytest.mark.parametrize("field", ["content_type", "evidence", "confidence"])
@pytest.mark.parametrize("value", [None, "   ", 123])
def test_handoff_rejects_invalid_source_semantic_field(field: str, value) -> None:
    package, worth = _handoff_pair()
    package["claim_candidates"][0][field] = value
    assert validate_handoff_inputs(package, worth)


@pytest.mark.parametrize("value", ["", "   ", 123, []])
def test_handoff_rejects_invalid_source_time_ref(value) -> None:
    package, worth = _handoff_pair()
    package["claim_candidates"][0]["time_ref"] = value
    assert validate_handoff_inputs(package, worth)


@pytest.mark.parametrize("value", [None, "", "   ", 123])
def test_handoff_rejects_invalid_trace_claim_type(value) -> None:
    package, worth = _handoff_pair()
    worth["source_trace"][0]["claim_type"] = value
    assert validate_handoff_inputs(package, worth)


def test_handoff_semantic_failure_writes_no_artifacts(tmp_path: Path) -> None:
    package, worth = _handoff_pair()
    package["claim_candidates"][0].pop("evidence")
    with pytest.raises(InvalidInputError):
        write_handoff_bundle(tmp_path, package=package, worth=worth)
    assert list(tmp_path.iterdir()) == []


def test_handoff_valid_complete_semantics_still_pass() -> None:
    package, worth = _handoff_pair()
    assert validate_handoff_inputs(package, worth) == []
