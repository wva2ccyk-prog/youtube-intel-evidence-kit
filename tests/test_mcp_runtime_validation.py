"""Section 11 (corrective): MCP runtime paths must validate source artifacts.

The TopicCollection MCP facade validates loaded collections with the
``dependency-free validator`` so invalid documents can never become plausible
successful tool responses. The overlay MCP server validates the operator
overlay through ``load_validated_operator_overlay`` in every public entry
point (summary, groups, group detail, limitations).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from youtube_intel.errors import InvalidInputError
from youtube_intel._fixtures import fixture_path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_valid_collection(tmp: Path) -> dict:
    from youtube_intel.topic_collection import build_topic_demo_from_segments
    manifest = build_topic_demo_from_segments(
        fixture_path("topic_demo"), topic_id="t", topic_title="T", output_dir=tmp
    )
    return json.loads(Path(manifest["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))


# --- TopicCollection MCP facade ------------------------------------------------


def test_topic_mcp_rejects_empty_object(tmp_path) -> None:
    from youtube_intel.topic_mcp_facade import load_topic_collection
    f = tmp_path / "empty.json"
    f.write_text("{}", encoding="utf-8")
    with pytest.raises(InvalidInputError, match="not a structurally valid TopicCollection"):
        load_topic_collection(f)


def test_topic_mcp_rejects_missing_groups(tmp_path) -> None:
    from youtube_intel.topic_mcp_facade import load_topic_collection
    f = tmp_path / "doc.json"
    f.write_text(json.dumps({"analysis_layer": "cross_video_topic_collection", "claim_groups": [], "claim_total": 0}), encoding="utf-8")
    with pytest.raises(InvalidInputError):
        load_topic_collection(f)


def test_topic_mcp_rejects_dangling_claim_reference(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    c["claim_groups"][0]["claim_uids"] = ["does-not-exist"]
    assert any("does not resolve" in i for i in validate_topic_collection_document(c))


def test_topic_mcp_rejects_dangling_evidence_reference(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    c["claim_groups"][0]["evidence_ids"] = ["does-not-exist-e"]
    assert any("does not resolve" in i for i in validate_topic_collection_document(c))


def test_topic_mcp_rejects_coordinate_mismatch(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    group = c["claim_groups"][0]
    if group["evidence_coordinates"]:
        group["evidence_coordinates"][0]["speaker"] = "WRONG-SPEAKER"
    assert any("coordinate speaker differs" in i for i in validate_topic_collection_document(c))


def test_topic_mcp_rejects_invalid_representative(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    c["claim_groups"][0]["representative_claim_uid"] = "not-in-this-group"
    assert any("representative_claim_uid" in i for i in validate_topic_collection_document(c))


def test_topic_mcp_accepts_valid_generated_collection(tmp_path) -> None:
    from youtube_intel.topic_mcp_facade import load_topic_collection
    c = _build_valid_collection(tmp_path)
    f = tmp_path / "collection.json"
    f.write_text(json.dumps(c), encoding="utf-8")
    loaded = load_topic_collection(f)
    assert loaded["claim_total"] > 0


# --- Overlay MCP runtime -------------------------------------------------------


def _overlay() -> dict:
    return json.loads(fixture_path("operator_overlay.json").read_text(encoding="utf-8"))


def _write_overlay(tmp_path: Path, overlay: dict) -> Path:
    f = tmp_path / "overlay.json"
    f.write_text(json.dumps(overlay), encoding="utf-8")
    return f


def _valid_overlay_copy() -> dict:
    import copy
    return copy.deepcopy(_overlay())


def test_valid_packaged_overlay_succeeds() -> None:
    from youtube_mcp_handoff.overlay_service import load_validated_operator_overlay
    overlay = load_validated_operator_overlay(fixture_path("operator_overlay.json"))
    assert overlay["ok"] is True


def _expect_public_tool_rejection(tmp_path, mutate) -> None:
    overlay = _valid_overlay_copy()
    mutate(overlay)
    path = _write_overlay(tmp_path, overlay)
    from youtube_mcp_handoff import server
    for tool in (
        lambda: server.mcp_overlay_summary(path),
        lambda: server.mcp_overlay_groups(path),
        lambda: server.mcp_overlay_group_detail("g1", path),
        lambda: server.mcp_overlay_limitations(path),
    ):
        with pytest.raises(InvalidInputError):
            tool()


def test_invalid_overlay_rejected_through_every_public_tool(tmp_path) -> None:
    def mutate(o):
        o["overlay_groups"] = []
        o["overlay_group_count"] = 0
    _expect_public_tool_rejection(tmp_path, mutate)


def test_duplicate_group_id_rejected(tmp_path) -> None:
    def mutate(o):
        o["overlay_groups"][1]["overlay_group_id"] = o["overlay_groups"][0]["overlay_group_id"]
    _expect_public_tool_rejection(tmp_path, mutate)


def test_missing_required_limitations_rejected(tmp_path) -> None:
    def mutate(o):
        o["limitations"] = []
    _expect_public_tool_rejection(tmp_path, mutate)


def test_invalid_policy_flags_rejected(tmp_path) -> None:
    def mutate(o):
        o["policy"]["truth_ranking_performed"] = True  # must be False
    _expect_public_tool_rejection(tmp_path, mutate)


def test_topic_mcp_rejects_claim_with_empty_source_video(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    uid = next(iter(c["claim_index"]))
    c["claim_index"][uid]["source_video_id"] = ""
    assert any("source_video_id is empty" in i for i in validate_topic_collection_document(c))


def test_topic_mcp_rejects_evidence_with_empty_video_id(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    eid = next(iter(c["evidence_index"]))
    c["evidence_index"][eid]["video_id"] = ""
    assert any("video_id is empty" in i for i in validate_topic_collection_document(c))


def test_topic_mcp_rejects_claim_index_uid_not_covered_by_group(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    uid = next(iter(c["claim_index"]))
    # Remove the uid from every group's member list and group ids.
    for g in c["claim_groups"]:
        g["claim_uids"] = [u for u in g["claim_uids"] if u != uid]
        g["member_claim_uids"] = [u for u in g["member_claim_uids"] if u != uid]
    assert any("not covered by any claim group" in i for i in validate_topic_collection_document(c))


def test_topic_mcp_rejects_claim_without_evidence_coordinate(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    uid = next(iter(c["claim_index"]))
    del c["claim_index"][uid]["evidence_coordinate"]
    assert any("missing evidence_coordinate" in i for i in validate_topic_collection_document(c))


# --- Third pass: dependency-free validator fail-closed on the public loader ---


def _mutate_and_assert_rejected(tmp_path: Path, mutate) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    c = _build_valid_collection(tmp_path)
    mutate(c)
    assert validate_topic_collection_document(c), "expected rejection, got no issues"


def _mutate_and_assert_loader_rejects(tmp_path: Path, mutate) -> None:
    from youtube_intel.topic_mcp_facade import load_topic_collection
    c = _build_valid_collection(tmp_path)
    mutate(c)
    f = tmp_path / "mutated.json"
    f.write_text(json.dumps(c), encoding="utf-8")
    with pytest.raises(InvalidInputError):
        load_topic_collection(f)


def test_mcp_rejects_wrong_schema_version(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(tmp_path, lambda c: c.update(schema_version="invalid"))


def test_mcp_rejects_empty_topic_id(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(tmp_path, lambda c: c["topic"].update(topic_id="  "))


def test_mcp_rejects_empty_topic_title(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(tmp_path, lambda c: c["topic"].update(title=""))


def test_mcp_rejects_empty_source_videos(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(tmp_path, lambda c: c.update(source_videos=[]))


def test_mcp_rejects_duplicate_source_video_ids(tmp_path) -> None:
    def _dup(c):
        c["source_videos"].append(dict(c["source_videos"][0]))
    _mutate_and_assert_loader_rejects(tmp_path, _dup)


def test_mcp_rejects_missing_video_record_count(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(tmp_path, lambda c: c.pop("video_record_count"))


def test_mcp_rejects_non_integer_video_record_count(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(tmp_path, lambda c: c.update(video_record_count="2"))


def test_mcp_rejects_video_count_mismatch(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(tmp_path, lambda c: c.update(video_record_count=99))


def test_mcp_rejects_claim_index_key_uid_mismatch(tmp_path) -> None:
    def _mutate(c):
        uid = next(iter(c["claim_index"]))
        c["claim_index"]["other-key"] = c["claim_index"].pop(uid)
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_empty_claim_text(tmp_path) -> None:
    def _mutate(c):
        uid = next(iter(c["claim_index"]))
        c["claim_index"][uid]["text"] = " "
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_secondary_dangling_evidence_id(tmp_path) -> None:
    def _mutate(c):
        uid = next(iter(c["claim_index"]))
        c["claim_index"][uid]["evidence_ids"].append("ghost-secondary-evidence")
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_duplicate_claim_evidence_ids(tmp_path) -> None:
    def _mutate(c):
        uid = next(iter(c["claim_index"]))
        eid = c["claim_index"][uid]["evidence_ids"][0]
        c["claim_index"][uid]["evidence_ids"].append(eid)
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_evidence_index_key_id_mismatch(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"]["other-eid"] = c["evidence_index"].pop(eid)
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_coordinate_time_ref_mismatch(tmp_path) -> None:
    def _mutate(c):
        uid = next(iter(c["claim_index"]))
        c["claim_index"][uid]["evidence_coordinate"]["time_ref"] = "99:99"
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_coordinate_speaker_confidence_mismatch(tmp_path) -> None:
    def _mutate(c):
        uid = next(iter(c["claim_index"]))
        c["claim_index"][uid]["evidence_coordinate"]["speaker_confidence"] = "medium"
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_coordinate_modality_mismatch(tmp_path) -> None:
    def _mutate(c):
        uid = next(iter(c["claim_index"]))
        c["claim_index"][uid]["evidence_coordinate"]["modality"] = ["ocr"]
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_claim_member_arrays_mismatch(tmp_path) -> None:
    def _mutate(c):
        g = c["claim_groups"][0]
        g["member_claim_uids"] = [g["claim_uids"][0], "extra-fake"]
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_empty_group_evidence_ids(tmp_path) -> None:
    def _mutate(c):
        c["claim_groups"][0]["evidence_ids"] = []
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_empty_group_evidence_coordinates(tmp_path) -> None:
    def _mutate(c):
        c["claim_groups"][0]["evidence_coordinates"] = []
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_evidence_id_without_group_coordinate(tmp_path) -> None:
    def _mutate(c):
        g = c["claim_groups"][0]
        g["evidence_ids"].append("extra-evidence-no-coord")
        c["evidence_index"]["extra-evidence-no-coord"] = dict(c["evidence_index"][next(iter(c["evidence_index"]))])
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_group_coordinate_with_unlisted_evidence_id(tmp_path) -> None:
    def _mutate(c):
        g = c["claim_groups"][0]
        g["evidence_coordinates"].append(dict(g["evidence_coordinates"][0]))
        g["evidence_coordinates"][-1]["evidence_id"] = "unlisted-coord"
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_terrain_dangling_group_id(tmp_path) -> None:
    def _mutate(c):
        c["terrain"]["repeated_claim_group_ids"].append("ghost-group")
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_disagreement_dangling_group_id(tmp_path) -> None:
    def _mutate(c):
        c["terrain"]["disagreement_relations"].append({"relation_id": "R1", "claim_group_id": "ghost-group", "claim_uids": []})
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_outlier_dangling_group_id(tmp_path) -> None:
    def _mutate(c):
        c["terrain"]["outlier_details"].append({"claim_group_id": "ghost-group", "claim_uids": []})
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_accepts_valid_generated_collection_still(tmp_path) -> None:
    from youtube_intel.topic_collection import validate_topic_collection_document
    assert validate_topic_collection_document(_build_valid_collection(tmp_path)) == []


# --- Fourth pass: Section 5.9 public-loader mutation coverage -----------------


def test_mcp_rejects_missing_source_video_title(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(
        tmp_path, lambda c: c["source_videos"][0].pop("title")
    )


def test_mcp_rejects_missing_source_video_role(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(
        tmp_path, lambda c: c["source_videos"][0].pop("role_in_topic")
    )


def test_mcp_rejects_missing_transcript_source(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(
        tmp_path, lambda c: c["source_videos"][0].pop("transcript_source")
    )


def test_mcp_rejects_missing_transcript_quality(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(
        tmp_path, lambda c: c["source_videos"][0].pop("transcript_quality")
    )


def test_mcp_rejects_evidence_timestamp_string(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["timestamp_start"] = "banana"
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_evidence_timestamp_nan(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["timestamp_start"] = float("nan")
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_evidence_timestamp_infinity(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["timestamp_end"] = float("inf")
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_evidence_timestamp_boolean(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["timestamp_start"] = True
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_evidence_timestamp_negative(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["timestamp_start"] = -1.0
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_evidence_end_before_start(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["timestamp_start"] = 5.0
        c["evidence_index"][eid]["timestamp_end"] = 2.0
        uid = next(iter(c["claim_index"]))
        c["claim_index"][uid]["evidence_coordinate"]["timestamp_start"] = 5.0
        c["claim_index"][uid]["evidence_coordinate"]["timestamp_end"] = 2.0
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_numeric_time_ref(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["time_ref"] = 42
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_invalid_speaker_type(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["speaker"] = 123
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_invalid_confidence_enum(tmp_path) -> None:
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["speaker_confidence"] = "sorta"
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_identical_invalid_values_across_layers(tmp_path) -> None:
    # The same invalid timestamp is set in evidence, claim coordinate, and group
    # coordinate. Equality alone must not make the pair valid; independent type
    # validation must reject it.
    def _mutate(c):
        eid = next(iter(c["evidence_index"]))
        c["evidence_index"][eid]["timestamp_start"] = False
        uid = next(iter(c["claim_index"]))
        c["claim_index"][uid]["evidence_coordinate"]["timestamp_start"] = False
        for group in c["claim_groups"]:
            for coord in group["evidence_coordinates"]:
                if coord["evidence_id"] == eid:
                    coord["timestamp_start"] = False
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_claim_in_two_groups(tmp_path) -> None:
    def _mutate(c):
        if len(c["claim_groups"]) >= 2:
            uid = c["claim_groups"][0]["claim_uids"][0]
            c["claim_groups"][1]["claim_uids"].append(uid)
            c["claim_groups"][1]["member_claim_uids"].append(uid)
            c["claim_groups"][1]["claim_count"] = len(c["claim_groups"][1]["member_claim_uids"])
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_malformed_terrain_list_type(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(
        tmp_path, lambda c: c["terrain"].update(repeated_claim_group_ids="not-a-list")
    )


def test_mcp_rejects_missing_terrain_list(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(
        tmp_path, lambda c: c["terrain"].pop("repeated_claim_group_ids")
    )


def test_mcp_rejects_duplicate_terrain_group_id(tmp_path) -> None:
    def _mutate(c):
        if c["terrain"]["repeated_claim_group_ids"]:
            gid = c["terrain"]["repeated_claim_group_ids"][0]
            c["terrain"]["repeated_claim_group_ids"].append(gid)
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_duplicate_relation_id(tmp_path) -> None:
    def _mutate(c):
        if c["terrain"]["disagreement_relations"]:
            rid = c["terrain"]["disagreement_relations"][0]["relation_id"]
            c["terrain"]["disagreement_relations"].append(
                dict(c["terrain"]["disagreement_relations"][0], relation_id=rid)
            )
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_relation_claim_outside_group(tmp_path) -> None:
    def _mutate(c):
        if len(c["claim_groups"]) >= 2:
            other_uid = c["claim_groups"][1]["claim_uids"][0]
            rel = c["terrain"]["disagreement_relations"][0]
            rel["claim_uids"].append(other_uid)
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_outlier_claim_outside_group(tmp_path) -> None:
    def _mutate(c):
        if len(c["claim_groups"]) >= 2:
            other_uid = c["claim_groups"][1]["claim_uids"][0]
            od = c["terrain"]["outlier_details"][0]
            od["claim_uids"].append(other_uid)
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_limitations_invalid_item_type(tmp_path) -> None:
    def _mutate(c):
        c["limitations"].append(123)
    _mutate_and_assert_loader_rejects(tmp_path, _mutate)


def test_mcp_rejects_limitations_wrong_type(tmp_path) -> None:
    _mutate_and_assert_loader_rejects(
        tmp_path, lambda c: c.update(limitations="not-a-list")
    )
