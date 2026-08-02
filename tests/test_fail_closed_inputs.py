"""P0-D: empty-input and invalid-input paths must fail closed.

Commands that used to return successful artifacts (or ``ok: true``) for
missing, empty, malformed, or internally inconsistent inputs must now exit
with code 2, print structured ``{"ok": false, "error": "InvalidInputError",
...}``, and never write a successful final manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from youtube_intel.cli import main
from youtube_intel.errors import InvalidInputError
from youtube_intel.topic_mcp_facade import load_topic_collection

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(*argv: str, capsys) -> tuple[int, dict]:
    rc = main(list(argv))
    payload = json.loads(capsys.readouterr().out)
    return rc, payload


# --- topic-demo --------------------------------------------------------------


def test_topic_demo_missing_topic_dir_fails_closed(tmp_path, capsys) -> None:
    out = tmp_path / "out"
    rc, payload = _run(
        "topic-demo", "--topic-dir", str(tmp_path / "missing"), "--out", str(out), capsys=capsys
    )
    assert rc == 2
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert "does not exist" in payload["message"]
    assert not (out / "topic_handoff_manifest.json").exists()


def test_topic_demo_no_video_files_fails_closed(tmp_path, capsys) -> None:
    topic_dir = tmp_path / "topic"
    topic_dir.mkdir()
    out = tmp_path / "out"
    rc, payload = _run(
        "topic-demo", "--topic-dir", str(topic_dir), "--out", str(out), capsys=capsys
    )
    assert rc == 2
    assert payload["ok"] is False
    assert "no video_*.json files" in payload["message"]
    assert not (out / "topic_handoff_manifest.json").exists()


def test_topic_demo_malformed_file_fails_closed(tmp_path, capsys) -> None:
    topic_dir = tmp_path / "topic"
    topic_dir.mkdir()
    (topic_dir / "video_a.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "out"
    rc, payload = _run(
        "topic-demo", "--topic-dir", str(topic_dir), "--out", str(out), capsys=capsys
    )
    assert rc == 2
    assert payload["ok"] is False
    assert "empty or malformed" in payload["message"]
    assert not (out / "topic_handoff_manifest.json").exists()


def test_topic_demo_source_package_validation_failure_stops_build(tmp_path, capsys) -> None:
    # Mojibake title makes the source package validation fail; the topic build
    # must stop and must not write a final successful manifest.
    topic_dir = tmp_path / "topic"
    topic_dir.mkdir()
    (topic_dir / "video_a.json").write_text(
        json.dumps({
            "video": {"video_id": "v1", "title": "??? ??", "language": "en"},
            "segments": [{"text": "The kit cuts water use.", "speaker": "A"}],
        }),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    rc, payload = _run(
        "topic-demo", "--topic-dir", str(topic_dir), "--out", str(out), capsys=capsys
    )
    assert rc == 2
    assert payload["ok"] is False
    assert "source package validation failed" in payload["message"]
    assert not (out / "topic_handoff_manifest.json").exists()


def test_topic_demo_empty_segments_list_fails_closed(tmp_path, capsys) -> None:
    topic_dir = tmp_path / "topic"
    topic_dir.mkdir()
    (topic_dir / "video_a.json").write_text(
        json.dumps({"video": {"video_id": "v1", "title": "T", "language": "en"}, "segments": []}),
        encoding="utf-8",
    )
    rc, payload = _run(
        "topic-demo", "--topic-dir", str(topic_dir), "--out", str(tmp_path / "out"), capsys=capsys
    )
    assert rc == 2
    assert payload["ok"] is False
    assert not (tmp_path / "out" / "topic_handoff_manifest.json").exists()


# --- package -----------------------------------------------------------------


def test_package_empty_segments_fails_closed(tmp_path, capsys) -> None:
    segments = tmp_path / "segments.json"
    segments.write_text("[]", encoding="utf-8")
    rc, payload = _run(
        "package", "--segments", str(segments), "--out", str(tmp_path / "out"), capsys=capsys
    )
    assert rc == 2
    assert payload["ok"] is False
    assert "no segments" in payload["message"]


def test_package_blank_text_segments_fail_validation(tmp_path, capsys) -> None:
    segments = tmp_path / "segments.json"
    segments.write_text(
        json.dumps({"video": {"video_id": ""}, "segments": [{"text": "   "}]}),
        encoding="utf-8",
    )
    rc, payload = _run(
        "package", "--segments", str(segments), "--out", str(tmp_path / "out"), capsys=capsys
    )
    assert rc == 2
    assert payload["ok"] is False
    # Blank-only text yields no claim candidates, so validation must fail and
    # no successful package artifact contract may be claimed.
    assert payload["validation"]["status"] == "fail"
    assert any("no claim candidates" in issue for issue in payload["validation"]["issues"])


# --- worth -------------------------------------------------------------------


def test_worth_without_source_fails_closed(tmp_path, capsys) -> None:
    rc, payload = _run("worth", "--out", str(tmp_path / "out"), capsys=capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert "requires one valid source" in payload["message"]
    assert not (tmp_path / "out" / "analysis_worth.json").exists()


def test_worth_empty_package_fails_closed(tmp_path, capsys) -> None:
    package = tmp_path / "package.json"
    package.write_text("{}", encoding="utf-8")
    rc, payload = _run("worth", "--package", str(package), "--out", str(tmp_path / "out"), capsys=capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert "non-empty residual package" in payload["message"]
    assert not (tmp_path / "out" / "analysis_worth.json").exists()


def test_worth_missing_run_dir_package_fails_closed(tmp_path, capsys) -> None:
    rc, payload = _run("worth", "--run-dir", str(tmp_path / "run"), "--out", str(tmp_path / "out"), capsys=capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert not (tmp_path / "out" / "analysis_worth.json").exists()


# --- MCP facades --------------------------------------------------------------


def test_topic_mcp_facade_rejects_empty_object(tmp_path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    with pytest.raises(InvalidInputError, match="not a TopicCollection"):
        load_topic_collection(empty)


def test_topic_mcp_facade_rejects_missing_claims(tmp_path) -> None:
    doc = tmp_path / "doc.json"
    doc.write_text(
        json.dumps({"analysis_layer": "cross_video_topic_collection", "claim_groups": [], "claim_index": {}, "claim_total": 0}),
        encoding="utf-8",
    )
    with pytest.raises(InvalidInputError, match="no claim groups|empty claim_index|claim_total"):
        load_topic_collection(doc)


def test_topic_mcp_facade_accepts_valid_collection(tmp_path) -> None:
    # Reuse the real topic-demo output as the valid reference document.
    out = tmp_path / "demo"
    rc = main(["topic-demo", "--out", str(out)])
    assert rc == 0
    collection_path = out / "topic_collection.json"
    loaded = load_topic_collection(collection_path)
    assert loaded["analysis_layer"] == "cross_video_topic_collection"
    assert loaded["claim_total"] > 0

