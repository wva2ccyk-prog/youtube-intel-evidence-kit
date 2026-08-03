"""Second corrective pass, Section 6: `topic-demo` must be fully fail-closed
on user-provided topic directories.

Every source file is strictly read and validated before anything is written,
identity is never fabricated from filename stems, malformed expected groupings
fail closed with exit 2, and a malformed later source cannot leave a
half-written output directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from youtube_intel._fixtures import fixture_path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "youtube_intel", *args],
        cwd=REPO_ROOT, env=env, text=True, capture_output=True,
    )


def _src(video: dict, segments) -> dict:
    return {"video": video, "segments": segments}


def _seg() -> list:
    return [{"text": "The kit cuts water use by twenty percent in dry weeks.", "speaker": "A", "time_ref": "00:00"}]


def _write(tmp_path: Path, name: str, data) -> Path:
    p = tmp_path / name
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8")
    else:
        p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _topic_dir(tmp_path: Path, files: list[tuple[str, object]]) -> Path:
    d = tmp_path / "topic"
    d.mkdir()
    for name, data in files:
        _write(d, name, data)
    return d


def _valid_video(extra: dict | None = None) -> dict:
    v = {"video_id": "v1", "title": "T", "language": "en"}
    if extra:
        v.update(extra)
    return v


def _assert_failure(result: subprocess.CompletedProcess, out: Path) -> dict:
    assert result.returncode == 2, f"expected exit 2: {result.stdout}\n{result.stderr}"
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert not (out / "topic_handoff_manifest.json").exists()
    assert not (out / "topic_collection.json").exists()
    return payload


def test_malformed_video_json(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", "{ bad")])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "invalid JSON" in payload["message"]


def test_top_level_scalar_source(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", "42")])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_missing_segments_field(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video()})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_segments_is_string(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video(), "segments": "oops"})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_empty_segments(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video(), "segments": []})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_null_segment_row(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video(), "segments": [None]})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "segment 0 is not an object" in payload["message"]


def test_string_segment_row(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video(), "segments": ["text"]})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "segment 0 is not an object" in payload["message"]


def test_empty_segment_text(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video(), "segments": [{"text": "  "}]})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "segment 0 has empty text" in payload["message"]


def test_missing_video_object(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"segments": _seg()})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "video is missing" in payload["message"]


def test_blank_video_id_user_topic_dir(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video({"video_id": ""}), "segments": _seg()})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "video.video_id is empty" in payload["message"]


def test_blank_title_user_topic_dir(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video({"title": ""}), "segments": _seg()})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "video.title is empty" in payload["message"]


def test_blank_language_user_topic_dir(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", {"video": _valid_video({"language": ""}), "segments": _seg()})])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "video.language is empty" in payload["message"]


def test_malformed_expected_groupings_json(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", _src(_valid_video(), _seg()))])
    _write(d, "expected_groupings.json", "{ nope")
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "expected groupings" in payload["message"]


def test_invalid_expected_grouping_shape(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", _src(_valid_video(), _seg()))])
    _write(d, "expected_groupings.json", {"must_link": "not-a-list"})
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "must_link must be a list" in payload["message"]


def test_one_valid_then_one_invalid_source_writes_no_artifacts(tmp_path) -> None:
    d = _topic_dir(tmp_path, [
        ("video_a.json", _src(_valid_video({"video_id": "va"}), _seg())),
        ("video_b.json", _src(_valid_video({"video_id": "vb"}), [None])),
    ])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)
    assert not out.exists(), "no artifacts may be written when any source is invalid"


def test_valid_default_packaged_topic_demo_succeeds(tmp_path) -> None:
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert (out / "topic_handoff_manifest.json").is_file()
    assert (out / "topic_collection.json").is_file()


def test_valid_user_topic_directory_succeeds(tmp_path) -> None:
    d = _topic_dir(tmp_path, [("video_a.json", _src(_valid_video(), _seg()))])
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    assert r.returncode == 0, r.stderr
    manifest = json.loads((out / "topic_handoff_manifest.json").read_text(encoding="utf-8"))
    assert manifest["ok"] is True


# --- Third pass: strict expected_groupings.json validation --------------------


def _topic_with_expected(tmp_path: Path, expected) -> Path:
    d = _topic_dir(tmp_path, [
        ("video_a.json", _src(_valid_video(), _seg())),
        ("expected_groupings.json", expected),
    ])
    return d


def test_threshold_is_string(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": "not-a-number"})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "threshold" in payload["message"]


def test_threshold_is_null(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": None})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_threshold_is_bool(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": True})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_threshold_below_zero(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": -0.1})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_threshold_above_one(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": 1.1})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_threshold_nan(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": float("nan")})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_threshold_infinity(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": float("inf")})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_must_link_scalar(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": "nope"})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_must_link_row_not_list(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": ["a-b-c"]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_must_link_row_one_item(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [["only-one"]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_must_link_row_three_items(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [["a", "b", "c"]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_must_link_row_empty_string(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [["valid", "   "]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_must_link_row_non_string(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [["valid", 42]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_cannot_link_scalar(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"cannot_link": 7})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    _assert_failure(r, out)


def test_cannot_link_malformed_row(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"cannot_link": [["ok"]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "cannot_link" in payload["message"]


def test_valid_expected_groupings_succeed(tmp_path) -> None:
    d = _topic_with_expected(tmp_path, {"must_link": [], "threshold": 0.5})
    out = tmp_path / "out"
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert (out / "topic_collection.json").exists()
    assert (out / "topic_handoff_manifest.json").exists()
    assert (out / "grouping_evaluation.json").exists()


# --- Fourth pass: expected-groupings fail-closed additions -------------------


def test_expected_groupings_missing_must_link(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"threshold": 0.5})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "must_link is required" in payload["message"]


def test_expected_groupings_null_must_link(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": None})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "must_link" in payload["message"]


def test_expected_groupings_duplicate_pair(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [["a", "b"], ["a", "b"]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "duplicate pair" in payload["message"]


def test_expected_groupings_reversed_duplicate_pair(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [["a", "b"], ["b", "a"]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "duplicate pair" in payload["message"]


def test_expected_groupings_same_pair_in_must_and_cannot(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(
        tmp_path,
        {"must_link": [["a", "b"]], "cannot_link": [["a", "b"]]},
    )
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "contradictory pair" in payload["message"]


def test_expected_groupings_same_item_on_both_sides(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [["a", "a"]]})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "same item on both sides" in payload["message"]


def test_expected_groupings_unknown_field_rejected(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(tmp_path, {"must_link": [], "unknown_field": True})
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    payload = _assert_failure(r, out)
    assert "unknown field" in payload["message"]


def test_expected_groupings_valid_populated_document(tmp_path) -> None:
    out = tmp_path / "out"
    d = _topic_with_expected(
        tmp_path,
        {
            "must_link": [["a-claim-text", "b-claim-text"]],
            "cannot_link": [["c-claim-text", "d-claim-text"]],
            "threshold": 0.5,
        },
    )
    r = _run_cli("topic-demo", "--topic-dir", str(d), "--out", str(out))
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert (out / "topic_handoff_manifest.json").exists()
