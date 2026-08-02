"""P1-B: group-level ``evidence_coordinates`` must be real coordinate objects,
not evidence ID strings, and the TopicCollection schema must enforce the
coordinate contract (required fields, non-empty IDs, unique IDs, restricted
additional properties) plus Python-level reference integrity.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from youtube_intel.topic_collection import build_topic_demo_from_segments

REPO_ROOT = Path(__file__).resolve().parents[1]

COORDINATE_FIELDS = (
    "evidence_id",
    "video_id",
    "timestamp_start",
    "timestamp_end",
    "time_ref",
    "speaker",
    "speaker_confidence",
    "modality",
)


def _topic_collection(tmp_path: Path) -> dict:
    manifest = build_topic_demo_from_segments(
        REPO_ROOT / "examples" / "topic_demo",
        topic_id="synthetic-orchard-sensors",
        topic_title="Synthetic orchard sensor adoption terrain",
        output_dir=tmp_path,
    )
    return json.loads(Path(manifest["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))


def test_group_evidence_coordinates_are_objects_not_id_strings(tmp_path: Path) -> None:
    collection = _topic_collection(tmp_path)
    for group in collection["claim_groups"]:
        coords = group["evidence_coordinates"]
        assert isinstance(coords, list)
        for coord in coords:
            assert isinstance(coord, dict), "evidence_coordinates must contain coordinate objects, not ID strings"
            missing = set(COORDINATE_FIELDS) - set(coord)
            assert not missing, f"coordinate missing fields: {sorted(missing)}"


def test_coordinate_evidence_ids_match_group_evidence_ids(tmp_path: Path) -> None:
    collection = _topic_collection(tmp_path)
    for group in collection["claim_groups"]:
        coord_ids = {c["evidence_id"] for c in group["evidence_coordinates"]}
        assert coord_ids <= set(group["evidence_ids"]), (
            "coordinate evidence_ids must resolve within the group's evidence_ids"
        )


def test_coordinates_resolve_in_evidence_index(tmp_path: Path) -> None:
    collection = _topic_collection(tmp_path)
    evidence_index = collection["evidence_index"]
    for group in collection["claim_groups"]:
        for coord in group["evidence_coordinates"]:
            record = evidence_index.get(coord["evidence_id"])
            assert record is not None, f"coordinate evidence_id {coord['evidence_id']!r} dangles"
            assert record["video_id"] == coord["video_id"]
            assert record["timestamp_start"] == coord["timestamp_start"]
            assert record["timestamp_end"] == coord["timestamp_end"]
            assert record["speaker"] == coord["speaker"]


def test_coordinates_are_unique_per_group(tmp_path: Path) -> None:
    collection = _topic_collection(tmp_path)
    for group in collection["claim_groups"]:
        coord_ids = [c["evidence_id"] for c in group["evidence_coordinates"]]
        assert len(coord_ids) == len(set(coord_ids)), "duplicate coordinate evidence_id in one group"


def test_generated_collection_passes_strict_schema(tmp_path: Path) -> None:
    collection = _topic_collection(tmp_path)
    schema = json.loads((REPO_ROOT / "schemas" / "topic_collection.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(collection), key=lambda e: list(e.path))
    assert not errors, "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:8])



def test_schema_rejects_id_string_coordinates() -> None:
    """A group whose evidence_coordinates are bare ID strings must fail the
    schema: a JSON Schema pass must mean structural validity, not merely the
    presence of generic objects."""
    schema = json.loads((REPO_ROOT / "schemas" / "topic_collection.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    bad_group = {
        "group_id": "G0001",
        "claim_group_key": "k",
        "label": "L",
        "video_ids": ["v1"],
        "claim_count": 1,
        "stances": ["reported_claim"],
        "support_roles": ["reported_context"],
        "status": {"repeated_claim": False, "disagreement_point": False, "outlier_claim": True},
        "claim_uids": ["c1"],
        "member_claim_uids": ["c1"],
        "representative_claim_uid": "c1",
        "evidence_ids": ["e1"],
        "evidence_coordinates": ["e1"],  # bare ID string: must be rejected
        "source_diversity": {"video_count": 1, "speaker_count": 1, "channel_count": 1},
        "grouping_method": "x",
        "grouping_confidence": "low",
        "why_grouped": ["x"],
        "human_review_required": True,
    }
    instance = {
        "schema_version": "youtube_topic_collection_v0.1",
        "topic": {"topic_id": "t", "title": "T", "final_objective": "o"},
        "source_videos": [],
        "analysis_layer": "cross_video_topic_collection",
        "claim_groups": [bad_group],
        "terrain": {
            "repeated_claim_group_ids": [],
            "disagreement_group_ids": [],
            "outlier_group_ids": [],
            "disagreement_relations": [],
            "outlier_details": [],
            "operator_judgment_required": True,
            "truth_status": "not_evaluated",
            "fact_check_status": "not_performed",
        },
        "claim_index": {},
        "evidence_index": {},
        "grouping_method": {"name": "x", "version": "v", "intended_scope": "s", "requires_upgrade_for_real_topics": True},
        "provenance": {},
        "limitations": [],
    }
    errors = list(validator.iter_errors(instance))
    assert errors, "bare ID-string coordinates must fail schema validation"


def test_schema_rejects_coordinate_with_empty_evidence_id() -> None:
    schema = json.loads((REPO_ROOT / "schemas" / "topic_collection.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    coord = {
        "evidence_id": "",
        "video_id": "v1",
        "timestamp_start": 0.0,
        "timestamp_end": 1.0,
        "time_ref": "00:00",
        "speaker": "A",
        "speaker_confidence": "high",
        "modality": ["caption"],
    }
    errors = list(validator.iter_errors(coord, validator.schema["$defs"]["evidenceCoordinate"]))
    assert errors, "empty evidence_id must fail schema validation"
