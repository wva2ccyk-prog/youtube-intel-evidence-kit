"""Second corrective pass, Section 4: representative evidence timestamps must
use the real structured span (span_start/span_end) rather than the display
oriented time_ref, with full fractional precision and exact cross-layer
agreement. Also covers the source-checkout fixture resolution fix."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from youtube_intel._fixtures import fixture_path
from youtube_intel.topic_collection import (
    build_topic_collection,
    build_video_knowledge_record,
)
from youtube_residual import build_residual_package

FRACTIONAL = [
    {"text": "first cue", "start": 12.37, "end": 14.81, "time_ref": "00:12", "speaker": "A"},
    {"text": "second cue completes the sentence.", "start": 15.05, "end": 17.10, "time_ref": "00:15", "speaker": "A"},
]


def _package(segments):
    return build_residual_package(
        video_id="real-video",
        title="Real Video",
        language="en",
        segments=segments,
        claim_assembly="sentence",
    )


def _record(segments):
    return build_video_knowledge_record(
        _package(segments).to_dict(), topic_id="t", topic_title="T"
    )


def test_structured_fractional_timestamps_are_the_representative_coordinates() -> None:
    record = _record(FRACTIONAL)
    claim = record["claim_records"][0]
    evidence = record["evidence_records"][0]
    assert evidence["timestamp_start"] == 12.37
    assert evidence["timestamp_end"] == 17.10
    assert claim["timestamp_start"] == 12.37
    assert claim["timestamp_end"] == 17.10


def test_no_precision_loss_with_fractional_timestamps() -> None:
    record = _record([
        {"text": "a", "start": 0.123456, "end": 1.654321, "speaker": "A"},
        {"text": "b completes", "start": 1.700001, "end": 3.000099, "speaker": "A"},
    ])
    evidence = record["evidence_records"][0]
    assert evidence["timestamp_start"] == 0.123456
    assert evidence["timestamp_end"] == 3.000099
    assert evidence["span_start"] == 0.123456
    assert evidence["span_end"] == 3.000099


def test_representative_timestamps_populated_without_time_ref() -> None:
    record = _record([
        {"text": "a", "start": 5.5, "end": 6.25, "speaker": "A"},
        {"text": "b completes", "start": 6.5, "end": 8.0, "speaker": "A"},
    ])
    evidence = record["evidence_records"][0]
    assert evidence["timestamp_start"] == 5.5
    assert evidence["timestamp_end"] == 8.0


def test_legacy_time_ref_only_behaves_without_fabricated_end() -> None:
    record = _record([
        {"text": "a", "time_ref": "00:12", "speaker": "A"},
        {"text": "b completes", "time_ref": "00:15", "speaker": "A"},
    ])
    evidence = record["evidence_records"][0]
    assert evidence["timestamp_start"] == 12.0
    assert evidence["timestamp_end"] is None
    coord = record["claim_records"][0]["evidence_coordinate"]
    assert coord["timestamp_start"] == 12.0
    assert coord["timestamp_end"] is None


def test_cross_layer_timestamp_equality() -> None:
    record = _record(FRACTIONAL)
    collection = build_topic_collection(
        [record], topic_id="t", topic_title="T", allow_single_video_opinions=True
    )
    claim = collection["claim_index"][list(collection["claim_index"])[0]]
    evidence = collection["evidence_index"][claim["evidence_ids"][0]]
    group = collection["claim_groups"][0]
    coord = group["evidence_coordinates"][0]
    assert claim["timestamp_start"] == evidence["timestamp_start"] == coord["timestamp_start"]
    assert claim["timestamp_end"] == evidence["timestamp_end"] == coord["timestamp_end"]
    assert claim["timestamp_start"] == 12.37
    assert claim["timestamp_end"] == 17.10


# --- source-checkout topic_demo fixture resolution (Section 6 related) -------


def test_source_checkout_topic_demo_resolves_examples_dir() -> None:
    path = fixture_path("topic_demo")
    assert str(path).endswith("examples/topic_demo")
    assert (path / "video_a.json").is_file()


def test_default_topic_demo_uses_examples_not_packaged_fixtures(tmp_path: Path) -> None:
    out = tmp_path / "out"
    stat = out.stat().st_dev if out.exists() else None
    from youtube_intel.cli import main
    import os
    rc = main(["topic-demo", "--out", str(out)])
    assert rc == 0
    manifest = json.loads((out / "topic_handoff_manifest.json").read_text(encoding="utf-8"))
    # packages must carry the source video ids, not the packaged fixture ids
    collection = json.loads((out / "topic_collection.json").read_text(encoding="utf-8"))
    assert collection["claim_total"] > 0
    manifest_path = out / "topic_handoff_manifest.json"
    assert manifest_path.is_file()


# --- Third pass: default cue-mode provenance on public paths -----------------


def _cue_fixture(tmp_path: Path, segments) -> Path:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": {"video_id": "rv", "title": "RV", "language": "en"}, "segments": segments}), encoding="utf-8")
    return f


_CUE_FRACTIONAL = [
    {"text": "first cue", "start": 12.37, "end": 14.81, "time_ref": "00:12", "speaker": "A"},
    {"text": "second cue.", "start": 15.05, "end": 17.10, "time_ref": "00:15", "speaker": "A"},
]


def test_package_cli_cue_mode_preserves_fractional_timestamps(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys
    from youtube_intel.cli import main

    fixture = _cue_fixture(tmp_path, _CUE_FRACTIONAL)
    out = tmp_path / "pkg-out"
    rc = main(["package", "--segments", str(fixture), "--out", str(out)])
    assert rc == 0
    package = json.loads((out / "residual_package.json").read_text(encoding="utf-8"))
    claim = package["claim_candidates"][0]
    assert claim["span_start"] == 12.37
    assert claim["span_end"] == 14.81
    assert claim["source_cue_coordinates"][0]["start"] == 12.37
    assert claim["source_cue_coordinates"][0]["end"] == 14.81


def test_topic_demo_cli_cue_mode_preserves_fractional_timestamps(tmp_path: Path) -> None:
    from youtube_intel.cli import main

    topic_dir = tmp_path / "topic"
    topic_dir.mkdir()
    (topic_dir / "video_a.json").write_text(
        json.dumps({"video": {"video_id": "va", "title": "VA", "language": "en"}, "segments": _CUE_FRACTIONAL}),
        encoding="utf-8",
    )
    out = tmp_path / "td-out"
    rc = main(["topic-demo", "--topic-dir", str(topic_dir), "--out", str(out)])
    assert rc == 0
    collection = json.loads((out / "topic_collection.json").read_text(encoding="utf-8"))
    uid = next(iter(collection["claim_index"]))
    claim = collection["claim_index"][uid]
    evidence = collection["evidence_index"][claim["evidence_ids"][0]]
    coord = collection["claim_groups"][0]["evidence_coordinates"][0]
    assert claim["timestamp_start"] == evidence["timestamp_start"] == coord["timestamp_start"]
    assert claim["timestamp_end"] == evidence["timestamp_end"] == coord["timestamp_end"]
    assert claim["timestamp_start"] == 12.37
    assert claim["timestamp_end"] == 14.81


def test_cue_mode_legacy_time_ref_only() -> None:
    package = build_residual_package(
        video_id="rv", title="RV", language="en",
        segments=[{"text": "legacy cue", "time_ref": "00:12", "speaker": "A"}],
    )
    claim = package.claim_candidates[0]
    assert claim.span_start == 12.0
    assert claim.span_end is None
    record = build_video_knowledge_record(package.to_dict(), topic_id="t", topic_title="T")
    ev = record["evidence_records"][0]
    assert ev["timestamp_start"] == 12.0
    assert ev["timestamp_end"] is None


def test_cue_mode_no_time_ref_structured_only() -> None:
    package = build_residual_package(
        video_id="rv", title="RV", language="en",
        segments=[{"text": "structured only cue", "start": 5.5, "end": 6.25, "speaker": "A"}],
    )
    record = build_video_knowledge_record(package.to_dict(), topic_id="t", topic_title="T")
    ev = record["evidence_records"][0]
    assert ev["timestamp_start"] == 5.5
    assert ev["timestamp_end"] == 6.25


def test_invalid_structured_timestamp_rejected_in_cue_mode(tmp_path: Path) -> None:
    import pytest
    from youtube_residual.package import normalize_segment_provenance
    from youtube_intel.errors import InvalidInputError

    with pytest.raises(InvalidInputError, match="is not a valid timestamp"):
        normalize_segment_provenance({"text": "x", "start": "banana", "time_ref": "00:12"}, cue_index=0)
    with pytest.raises(InvalidInputError, match="is not a valid timestamp"):
        normalize_segment_provenance({"text": "x", "start": 1.0, "end": "zzz"}, cue_index=0)


def test_invalid_structured_timestamp_rejected_in_sentence_mode(tmp_path: Path) -> None:
    import pytest
    from youtube_intel.errors import InvalidInputError
    from youtube_residual.package import assemble_segments_to_sentences

    with pytest.raises(InvalidInputError, match="is not a valid timestamp"):
        assemble_segments_to_sentences([{"text": "x", "start": "banana", "time_ref": "00:12"}])
