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
