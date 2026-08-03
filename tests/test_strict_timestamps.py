"""Fourth corrective pass, Section 6: strict structured timestamp parsing.

Both the default cue path and the sentence path share one strict parser
(parse_structured_timestamp) that rejects booleans, NaN/Infinity, negative
values, reversed intervals, and unparseable strings while preserving fractional
precision and overriding legacy ``time_ref`` only as a start fallback.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from youtube_intel.errors import InvalidInputError
from youtube_intel.sentence_assembly import parse_structured_timestamp
from youtube_residual.package import assemble_segments_to_sentences, normalize_segment_provenance

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run([sys.executable, "-m", "youtube_intel", *args], cwd=REPO_ROOT, env=env, text=True, capture_output=True)


# --- parse_structured_timestamp unit behavior ----------------------------------


def test_valid_integer():
    assert parse_structured_timestamp(12, field="x") == 12.0


def test_valid_fractional_float():
    assert parse_structured_timestamp(12.37, field="x") == 12.37


def test_valid_mm_ss():
    assert parse_structured_timestamp("00:12", field="x") == 12.0


def test_valid_hh_mm_ss():
    assert parse_structured_timestamp("01:02:03", field="x") == 3723.0


def test_none_allowed():
    assert parse_structured_timestamp(None, field="x") is None


def test_none_not_allowed():
    with pytest.raises(InvalidInputError):
        parse_structured_timestamp(None, field="x", allow_none=False)


@pytest.mark.parametrize("bad", [True, False])
def test_boolean_rejected(bad):
    with pytest.raises(InvalidInputError, match="boolean"):
        parse_structured_timestamp(bad, field="x")


@pytest.mark.parametrize("bad", [float("nan"), "NaN", float("inf"), float("-inf"), "Infinity", "-Infinity"])
def test_non_finite_rejected(bad):
    with pytest.raises(InvalidInputError, match="finite|not a valid timestamp|non-negative"):
        parse_structured_timestamp(bad, field="x")


@pytest.mark.parametrize("bad", [-5, -0.5, "-00:05"])
def test_negative_rejected(bad):
    with pytest.raises(InvalidInputError, match="non-negative"):
        parse_structured_timestamp(bad, field="x")


@pytest.mark.parametrize("bad", ["banana", "12:xx", [], {}])
def test_malformed_rejected(bad):
    with pytest.raises(InvalidInputError):
        parse_structured_timestamp(bad, field="x")


def test_blank_string_none_allowed():
    # Blank input returns None when allowed (treated as "no timestamp"),
    # matching the documented allow_none contract.
    assert parse_structured_timestamp("", field="x") is None


# --- cue / sentence path integration -------------------------------------------


def test_cue_end_before_start_rejected():
    with pytest.raises(InvalidInputError, match="precedes its start"):
        normalize_segment_provenance({"text": "x", "start": 15.0, "end": 5.0}, cue_index=0)


def test_sentence_end_before_start_rejected():
    with pytest.raises(InvalidInputError, match="precedes its start"):
        assemble_segments_to_sentences([{"text": "x", "start": 15.0, "end": 5.0}])


def test_equal_start_end_accepted():
    p = normalize_segment_provenance({"text": "x", "start": 5.0, "end": 5.0}, cue_index=0)
    assert p["span_start"] == 5.0 and p["span_end"] == 5.0


def test_missing_end_stays_none():
    p = normalize_segment_provenance({"text": "x", "start": 5.0}, cue_index=0)
    assert p["span_start"] == 5.0 and p["span_end"] is None


def test_structured_overrides_legacy_time_ref():
    p = normalize_segment_provenance({"text": "x", "start": 12.37, "time_ref": "00:12"}, cue_index=0)
    assert p["span_start"] == 12.37


def test_fractional_precision_preserved():
    p = normalize_segment_provenance({"text": "x", "start": 0.123456, "end": 1.5}, cue_index=0)
    assert p["span_start"] == 0.123456 and p["span_end"] == 1.5


def test_cue_boolean_start_rejected():
    with pytest.raises(InvalidInputError, match="boolean"):
        normalize_segment_provenance({"text": "x", "start": True}, cue_index=0)


def test_cue_nan_start_rejected():
    with pytest.raises(InvalidInputError, match="finite"):
        normalize_segment_provenance({"text": "x", "start": float("nan")}, cue_index=0)


# --- CLI structured failure ----------------------------------------------------


def test_package_cli_boolean_start_structured_failure(tmp_path) -> None:
    seg = tmp_path / "seg.json"
    seg.write_text(
        '{"video": {"video_id": "v", "title": "T", "language": "en"}, "segments": [{"text": "x", "start": true}]}',
        encoding="utf-8",
    )
    out = tmp_path / "out"
    r = _run_cli("package", "--segments", str(seg), "--out", str(out))
    assert r.returncode == 2
    assert "Traceback" not in r.stderr
    import json
    payload = json.loads(r.stdout)
    assert payload["ok"] is False and payload["error"] == "InvalidInputError"
    assert not (out / "residual_package.json").exists()


def test_package_cli_nan_start_structured_failure(tmp_path) -> None:
    seg = tmp_path / "seg.json"
    import json as _json
    seg.write_text(_json.dumps({"video": {"video_id": "v", "title": "T", "language": "en"}, "segments": [{"text": "x", "start": 1e999}]}), encoding="utf-8")
    out = tmp_path / "out"
    r = _run_cli("package", "--segments", str(seg), "--out", str(out))
    assert r.returncode == 2
    assert "Traceback" not in r.stderr
    payload = _json.loads(r.stdout)
    assert payload["ok"] is False and payload["error"] == "InvalidInputError"
    assert not (out / "residual_package.json").exists()
