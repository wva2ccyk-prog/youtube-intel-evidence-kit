from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "schemas/topic_collection.schema.json",
    '      "required": ["evidence_id", "video_id", "timestamp_start", "timestamp_end", "time_ref", "speaker", "modality", "text", "confidence"],\n',
    '      "required": ["evidence_id", "video_id", "timestamp_start", "timestamp_end", "time_ref", "speaker", "speaker_confidence", "modality", "text", "confidence"],\n',
)
replace_once(
    "schemas/topic_collection.schema.json",
    '''    "evidenceIndexRecord": {\n      "type": "object",\n      "required": ["evidence_id", "video_id", "timestamp_start", "timestamp_end", "time_ref", "speaker", "speaker_confidence", "modality", "text", "confidence"],\n      "properties": {\n        "evidence_id": {"type": "string", "minLength": 1},\n        "video_id": {"type": "string", "minLength": 1},\n        "timestamp_start": {"type": ["number", "null"], "minimum": 0},\n        "timestamp_end": {"type": ["number", "null"], "minimum": 0},\n        "time_ref": {"type": ["string", "null"]},\n        "speaker": {"type": ["string", "null"]},\n        "speaker_confidence": {"type": ["string", "null"]},\n''',
    '''    "evidenceIndexRecord": {\n      "type": "object",\n      "required": ["evidence_id", "video_id", "timestamp_start", "timestamp_end", "time_ref", "speaker", "speaker_confidence", "modality", "text", "confidence"],\n      "properties": {\n        "evidence_id": {"type": "string", "minLength": 1},\n        "video_id": {"type": "string", "minLength": 1},\n        "timestamp_start": {"type": ["number", "null"], "minimum": 0},\n        "timestamp_end": {"type": ["number", "null"], "minimum": 0},\n        "time_ref": {"type": ["string", "null"]},\n        "speaker": {"type": ["string", "null"]},\n        "speaker_confidence": {"enum": ["high", "medium", "low", "unknown"]},\n''',
)

path = Path("tests/test_final_contract_hardening.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    '    assert validate_topic_collection_document(document)\n\n\n@pytest.mark.parametrize(\n    ("field", "value"),\n    [\n        ("outlier_type", []),',
    '    assert validate_topic_collection_document(document)\n    assert _schema_errors(document)\n\n\n@pytest.mark.parametrize(\n    ("field", "value"),\n    [\n        ("outlier_type", []),',
    1,
)
text = text.replace(
    '    assert validate_topic_collection_document(document)\n\n\ndef test_runtime_rejects_non_boolean_operator_judgment',
    '    assert validate_topic_collection_document(document)\n    assert _schema_errors(document)\n\n\ndef test_runtime_rejects_non_boolean_operator_judgment',
    1,
)
text = text.replace(
    '    assert any("operator_judgment_required" in issue for issue in validate_topic_collection_document(document))\n\n\ndef test_schema_and_runtime_both_reject_null_source_title',
    '    assert any("operator_judgment_required" in issue for issue in validate_topic_collection_document(document))\n    assert _schema_errors(document)\n\n\n@pytest.mark.parametrize("field", ["relation_type", "confidence", "human_review_required", "why_flagged"])\ndef test_schema_and_runtime_reject_missing_disagreement_relation_fields(tmp_path: Path, field: str) -> None:\n    document = _collection(tmp_path)\n    assert document["terrain"]["disagreement_relations"]\n    document["terrain"]["disagreement_relations"][0].pop(field)\n    assert validate_topic_collection_document(document)\n    assert _schema_errors(document)\n\n\n@pytest.mark.parametrize("field", ["outlier_type", "followup_priority", "why_outlier"])\ndef test_schema_and_runtime_reject_missing_outlier_fields(tmp_path: Path, field: str) -> None:\n    document = _collection(tmp_path)\n    assert document["terrain"]["outlier_details"]\n    document["terrain"]["outlier_details"][0].pop(field)\n    assert validate_topic_collection_document(document)\n    assert _schema_errors(document)\n\n\ndef test_schema_and_runtime_both_reject_null_source_title',
    1,
)
anchor = '''def test_schema_and_runtime_both_reject_null_coordinate_confidence(tmp_path: Path) -> None:\n    document = _collection(tmp_path)\n    evidence_id = next(iter(document["evidence_index"]))\n    document["evidence_index"][evidence_id]["speaker_confidence"] = None\n    for claim in document["claim_index"].values():\n        if claim["evidence_coordinate"]["evidence_id"] == evidence_id:\n            claim["evidence_coordinate"]["speaker_confidence"] = None\n    for group in document["claim_groups"]:\n        for coordinate in group["evidence_coordinates"]:\n            if coordinate["evidence_id"] == evidence_id:\n                coordinate["speaker_confidence"] = None\n    assert validate_topic_collection_document(document)\n    assert _schema_errors(document)\n\n\n'''
addition = anchor + '''def test_schema_and_runtime_both_require_evidence_speaker_confidence(tmp_path: Path) -> None:\n    document = _collection(tmp_path)\n    evidence_id = next(iter(document["evidence_index"]))\n    document["evidence_index"][evidence_id].pop("speaker_confidence")\n    assert validate_topic_collection_document(document)\n    assert _schema_errors(document)\n\n\n'''
if text.count(anchor) != 1:
    raise RuntimeError("test confidence anchor not found exactly once")
text = text.replace(anchor, addition, 1)
path.write_text(text, encoding="utf-8")

print("schema parity cleanup applied")
