from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from youtube_intel.io_utils import read_json
from youtube_intel.topic_collection import (
    TOPIC_COLLECTION_SCHEMA_VERSION,
    VIDEO_RECORD_SCHEMA_VERSION,
    build_topic_collection,
    build_topic_demo_from_segments,
    build_video_knowledge_record,
)


def _schema(name: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "schemas" / name).read_text(encoding="utf-8"))


def _validate(instance: dict, schema_name: str) -> None:
    schema = _schema(schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    assert not errors, "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


def _topic_demo(tmp_path: Path) -> dict:
    root = Path(__file__).resolve().parents[1]
    return build_topic_demo_from_segments(
        root / "examples" / "topic_demo",
        topic_id="synthetic-orchard-sensors",
        topic_title="Synthetic orchard sensor adoption terrain",
        output_dir=tmp_path,
    )


def test_video_knowledge_record_marks_single_video_as_input_layer():
    root = Path(__file__).resolve().parents[1]
    package = read_json(root / "examples" / "synthetic_package.json", {})
    record = build_video_knowledge_record(
        package,
        topic_id="synthetic-orchard-sensors",
        topic_title="Synthetic orchard sensor adoption terrain",
    )
    assert record["schema_version"] == VIDEO_RECORD_SCHEMA_VERSION
    assert record["analysis_layer"] == "single_video_input_for_topic_collection"
    assert record["truth_status"] == "not_evaluated"
    assert record["fact_check_status"] == "not_performed"
    assert record["claim_records"]
    assert record["evidence_records"]
    first = record["claim_records"][0]
    assert first["claim_uid"].startswith("synthetic-field-demo:")
    assert first["claim_group_key"]
    assert first["modality_sources"]
    assert first["evidence_coordinate"]["video_id"] == first["source_video_id"]
    assert first["evidence_ids"]
    assert first["verification_status"] == "video_internal_not_fact_checked"
    assert set(first["need_gates"]) == {
        "asr",
        "ocr_vision",
        "speaker_diarization",
        "external_verification",
        "strong_model_review",
    }
    _validate(record, "video_knowledge_record.schema.json")


def test_topic_collection_maps_repeated_disagreement_and_outlier(tmp_path: Path):
    manifest = _topic_demo(tmp_path)
    collection = json.loads(Path(manifest["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))
    assert collection["schema_version"] == TOPIC_COLLECTION_SCHEMA_VERSION
    assert collection["analysis_layer"] == "cross_video_topic_collection"
    assert collection["video_record_count"] == 3
    assert collection["claim_total"] >= 9
    assert collection["terrain"]["truth_status"] == "not_evaluated"
    assert collection["terrain"]["fact_check_status"] == "not_performed"
    assert collection["terrain"]["operator_judgment_required"] is True
    assert collection["terrain"]["repeated_claim_group_ids"]
    assert collection["terrain"]["disagreement_group_ids"]
    assert collection["terrain"]["disagreement_relations"]
    assert collection["terrain"]["outlier_group_ids"]
    assert collection["terrain"]["outlier_details"]
    assert collection["claim_index"]
    assert collection["evidence_index"]
    assert collection["grouping_method"]["requires_upgrade_for_real_topics"] is True
    _validate(collection, "topic_collection.schema.json")


def test_generated_video_knowledge_records_validate_against_schema(tmp_path: Path):
    manifest = _topic_demo(tmp_path)
    for path_text in manifest["paths"]["video_knowledge_records"]:
        record = json.loads(Path(path_text).read_text(encoding="utf-8"))
        _validate(record, "video_knowledge_record.schema.json")


def test_topic_collection_schema_files_are_public_contracts():
    video_schema = _schema("video_knowledge_record.schema.json")
    topic_schema = _schema("topic_collection.schema.json")
    assert video_schema["title"] == "VideoKnowledgeRecord"
    assert topic_schema["title"] == "TopicCollection"
    assert "claim_records" in video_schema["required"]
    assert "evidence_records" in video_schema["required"]
    assert "claim_groups" in topic_schema["required"]
    assert "evidence_index" in topic_schema["required"]


def test_claim_uids_are_resolvable_and_have_evidence_coordinates(tmp_path: Path):
    manifest = _topic_demo(tmp_path)
    collection = json.loads(Path(manifest["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))
    claim_index = collection["claim_index"]
    evidence_index = collection["evidence_index"]
    for group in collection["claim_groups"]:
        assert group["member_claim_uids"] == group["claim_uids"]
        for uid in group["claim_uids"]:
            assert uid in claim_index
            claim = claim_index[uid]
            assert claim["evidence_coordinate"]["video_id"] == claim["source_video_id"]
            assert claim["evidence_ids"]
            for evidence_id in claim["evidence_ids"]:
                assert evidence_id in evidence_index


def test_topic_handoff_manifest_file_matches_returned_manifest(tmp_path: Path):
    manifest = _topic_demo(tmp_path)
    on_disk = json.loads((tmp_path / "topic_handoff_manifest.json").read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert on_disk["bundle_type"] == "topic_collection_handoff"
    assert on_disk["entrypoint"] == "topic_collection.json"
    assert "residual_packages" in on_disk["paths"]
    assert "validations" in on_disk["paths"]
    assert on_disk["claim_group_count"] == len(json.loads(Path(on_disk["paths"]["topic_collection_json"]).read_text(encoding="utf-8"))["claim_groups"])


def test_group_subset_markdown_contains_claim_coordinates(tmp_path: Path):
    manifest = _topic_demo(tmp_path)
    for key in ("repeated_claims_md", "disagreements_md", "outliers_md"):
        text = Path(manifest["paths"][key]).read_text(encoding="utf-8")
        assert "claim_uid=" in text
        assert "video=" in text
        assert "time=" in text
        assert "speaker=" in text
        assert "modality=" in text
        assert "text:" in text


def test_handoff_prompt_prevents_truth_collapse(tmp_path: Path):
    manifest = _topic_demo(tmp_path)
    text = Path(manifest["paths"]["topic_handoff_prompt_md"]).read_text(encoding="utf-8")
    assert "Repeated claims are terrain signals" in text
    assert "Disagreement groups are candidate relations" in text
    assert "claim_uid" in text and "video_id" in text and "timestamp" in text


def test_topic_mcp_facade_reads_generated_topic_collection(tmp_path: Path):
    manifest = _topic_demo(tmp_path)
    from youtube_intel.topic_mcp_facade import (
        handle_jsonrpc_request,
        load_topic_collection,
        topic_claim_group_detail,
        topic_claim_groups,
        topic_summary,
    )

    collection = load_topic_collection(manifest["paths"]["topic_collection_json"])
    summary = topic_summary(collection)
    assert summary["facade_type"] == "mcp_ready_read_only_topic_handoff_facade"
    assert summary["not_full_mcp_server"] is True
    groups = topic_claim_groups(collection)
    assert groups["claim_group_count"] == len(collection["claim_groups"])
    gid = collection["claim_groups"][0]["group_id"]
    detail = topic_claim_group_detail(collection, gid)
    assert detail["ok"] is True
    assert detail["claims"]
    assert detail["claims"][0]["evidence_coordinate"]
    response = handle_jsonrpc_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        manifest["paths"]["topic_collection_json"],
    )
    assert response and response["result"]["tools"]
    response = handle_jsonrpc_request(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "topic.summary", "arguments": {}}},
        manifest["paths"]["topic_collection_json"],
    )
    assert response and response["result"]["content"]
