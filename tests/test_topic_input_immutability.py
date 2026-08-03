"""P0-B: build_topic_collection must never mutate input VideoKnowledgeRecords.

Clustering used to write claim_group_key / claim_group_label /
normalized_tokens directly onto the input claim dicts, so a VideoKnowledgeRecord
changed depending on which other videos were grouped with it, on input order,
and on clusterer/threshold choice. The persisted per-video records must stay
byte-stable regardless of collection construction, and recorded input hashes
must describe the original inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

from youtube_intel.topic_collection import (
    _stable_json_hash,
    build_topic_collection,
    build_video_knowledge_record,
)
from youtube_intel.io_utils import read_json

ROOT = Path(__file__).resolve().parents[1]


def _records() -> list[dict]:
    package = read_json(ROOT / "examples" / "synthetic_package.json", {})
    package_b = json.loads(json.dumps(package))
    package_b["video"] = dict(package_b.get("video") or {})
    package_b["video"]["video_id"] = "synthetic-field-demo-b"
    package_b["video"]["title"] = "Synthetic Orchard Sensor Field Notes B"
    return [
        build_video_knowledge_record(package, topic_id="synthetic-orchard-sensors", topic_title="Synthetic orchard sensor adoption terrain"),
        build_video_knowledge_record(package_b, topic_id="synthetic-orchard-sensors", topic_title="Synthetic orchard sensor adoption terrain"),
    ]


def _serialized(records: list[dict]) -> str:
    return json.dumps(records, ensure_ascii=False, sort_keys=True)


def test_build_topic_collection_does_not_mutate_input_records():
    records = _records()
    before = _serialized(records)
    build_topic_collection(records, topic_id="synthetic-orchard-sensors", topic_title="Synthetic orchard sensor adoption terrain")
    assert _serialized(records) == before, "input records changed after build_topic_collection"


def test_both_clusterers_leave_inputs_unchanged():
    records = _records()
    before = _serialized(records)
    build_topic_collection(records, topic_id="t", topic_title="T", clusterer="normalized")
    assert _serialized(records) == before
    build_topic_collection(records, topic_id="t", topic_title="T", clusterer="token_jaccard", token_jaccard_threshold=0.45)
    assert _serialized(records) == before


def test_input_record_hashes_describe_original_records():
    records = _records()
    expected_hashes = [_stable_json_hash(r) for r in records]
    collection = build_topic_collection(records, topic_id="t", topic_title="T")
    assert collection["provenance"]["input_record_hashes"] == expected_hashes
    # And the hashes must still match the untouched inputs after the build.
    assert [_stable_json_hash(r) for r in records] == expected_hashes


def test_consecutive_builds_do_not_contaminate_each_other():
    records = _records()
    before = _serialized(records)
    first = build_topic_collection(records, topic_id="t", topic_title="T", clusterer="normalized")
    second = build_topic_collection(records, topic_id="t", topic_title="T", clusterer="normalized")
    assert first["claim_groups"] == second["claim_groups"]
    assert first["claim_index"] == second["claim_index"]
    assert first["provenance"]["input_record_hashes"] == second["provenance"]["input_record_hashes"]
    # Inputs still pristine after both builds. Compare against the pre-build
    # snapshot (not a fresh _records() call): build_video_knowledge_record embeds
    # a second-resolution created_at_utc, so two separate calls can straddle a
    # second boundary and differ only in that volatile timestamp.
    assert _serialized(records) == before


def test_persisted_records_stay_stable_across_clusterer_choice(tmp_path: Path):
    records = _records()
    before = _serialized(records)
    build_topic_collection(records, topic_id="t", topic_title="T", clusterer="normalized")
    after_normalized = _serialized(records)
    assert after_normalized == before
    build_topic_collection(records, topic_id="t", topic_title="T", clusterer="token_jaccard", token_jaccard_threshold=0.45)
    assert _serialized(records) == before
