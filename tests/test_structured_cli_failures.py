"""Section 3 (corrective): every expected input failure must produce structured
exit-code-2 JSON - never a traceback.

For every expected failure the CLI must emit: exit code 2, stdout is valid
JSON, ok == false, error == InvalidInputError, no final success manifest, and
no traceback on stderr.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "youtube_intel", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def _assert_structured_failure(result: subprocess.CompletedProcess, *, out: Path) -> dict:
    assert result.returncode == 2, f"expected exit 2, got {result.returncode}: {result.stdout}\n{result.stderr}"
    assert "Traceback" not in result.stderr, f"traceback on stderr: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert not (out / "handoff_manifest.json").exists()
    return payload


def test_missing_json_file(tmp_path) -> None:
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(tmp_path / "missing.json"), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_invalid_json_syntax(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text("{ not valid json !!", encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    payload = _assert_structured_failure(result, out=out)
    assert "invalid JSON" in payload["message"]


def test_non_utf8_required_json(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_bytes(b"\xff\xfe\x00bad utf8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    payload = _assert_structured_failure(result, out=out)
    assert "not valid UTF-8" in payload["message"]


def test_top_level_scalar_json(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text("42", encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_segments_is_string(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": {"video_id": "v1", "title": "T", "language": "en"}, "segments": "oops"}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_segment_row_is_null(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": {"video_id": "v1", "title": "T", "language": "en"}, "segments": [None]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_segment_row_is_string(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": {"video_id": "v1", "title": "T", "language": "en"}, "segments": ["text"]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    _assert_structured_failure(result, out=out)

def test_hesitation_claim_row_is_null(tmp_path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"claims": [None]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("hesitation-demo", "--fixture", str(fixture), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_hesitation_claim_row_is_string(tmp_path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"claims": ["not-a-dict"]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("hesitation-demo", "--fixture", str(fixture), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_hesitation_words_not_list(tmp_path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"claims": [{"claim_id": "c1", "words": "oops"}]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("hesitation-demo", "--fixture", str(fixture), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_hesitation_word_row_is_null(tmp_path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"claims": [{"claim_id": "c1", "words": [None]}]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("hesitation-demo", "--fixture", str(fixture), "--out", str(out))
    _assert_structured_failure(result, out=out)


def test_hesitation_word_row_is_string(tmp_path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"claims": [{"claim_id": "c1", "words": ["word"]}]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("hesitation-demo", "--fixture", str(fixture), "--out", str(out))
    _assert_structured_failure(result, out=out)
