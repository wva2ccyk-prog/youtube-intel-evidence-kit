"""Tests for the deterministic Tier-1 hesitation-marker rules (public contract).

All synthetic. No audio, no ASR, no network. Verifies the rules, the
null-score policy, the disclaimer, and the demo command.
"""

from __future__ import annotations

import json
from pathlib import Path

from youtube_intel.hesitation_markers import (
    HESITATION_MARKER_DISCLAIMER,
    MARKER_CANDIDATE,
    MARKER_INSUFFICIENT,
    MARKER_NONE,
    analyze_claim_words,
    build_markers_artifact,
    count_fillers,
    count_restarts,
    detect_pause_events,
    render_markers_markdown,
)


def _w(word, start, end):
    return {"word": word, "start": start, "end": end}


class TestPauses:
    def test_mid_span_pause_detected(self):
        words = [_w("a", 0.0, 0.3), _w("b", 0.3, 0.6), _w("c", 1.6, 1.9)]
        events = detect_pause_events(words)
        assert len(events) == 1
        assert round(events[0]["gap_seconds"], 1) == 1.0

    def test_short_gap_not_a_pause(self):
        words = [_w("a", 0.0, 0.3), _w("b", 0.5, 0.8)]
        assert detect_pause_events(words) == []

    def test_edge_silence_excluded(self):
        # A large gap only exists between the two words (mid-span), never at
        # the outer edges of the span, so exactly one event is reported.
        words = [_w("a", 5.0, 5.3), _w("b", 7.0, 7.3)]
        events = detect_pause_events(words)
        assert len(events) == 1


class TestFillers:
    def test_isolated_korean_filler(self):
        words = [_w("저기", 0.0, 0.3), _w("수치는", 0.4, 0.8)]
        assert count_fillers(words) == 1

    def test_consecutive_fillers_counted_individually(self):
        words = [_w("어", 0.0, 0.2), _w("음", 0.3, 0.5), _w("그", 0.6, 0.8)]
        assert count_fillers(words) == 3

    def test_content_word_containing_filler_not_counted(self):
        # "그것" contains "그" but is not the isolated filler token.
        words = [_w("그것은", 0.0, 0.4), _w("사실", 0.5, 0.9)]
        assert count_fillers(words) == 0


class TestRestarts:
    def test_identical_adjacent_restart(self):
        words = [_w("we", 0.0, 0.2), _w("we", 0.2, 0.4), _w("measured", 0.4, 0.9)]
        assert count_restarts(words) == 1

    def test_strict_prefix_restart(self):
        words = [_w("mea", 0.0, 0.2), _w("measured", 0.2, 0.7)]
        assert count_restarts(words) == 1

    def test_single_char_prefix_not_restart(self):
        words = [_w("a", 0.0, 0.1), _w("apple", 0.1, 0.5)]
        assert count_restarts(words) == 0


class TestMarkerAndScorePolicy:
    def test_insufficient_words(self):
        row = analyze_claim_words("c1", [_w("a", 0.0, 0.2), _w("b", 0.2, 0.4)])
        assert row["marker"] == MARKER_INSUFFICIENT

    def test_candidate_on_pause(self):
        words = [_w("a", 0.0, 0.3), _w("b", 0.3, 0.6), _w("c", 1.9, 2.2), _w("d", 2.2, 2.5)]
        row = analyze_claim_words("c1", words)
        assert row["marker"] == MARKER_CANDIDATE

    def test_no_hesitation(self):
        words = [_w("the", 0.0, 0.2), _w("sensor", 0.2, 0.6), _w("was", 0.6, 0.8), _w("fine", 0.8, 1.1)]
        row = analyze_claim_words("c1", words)
        assert row["marker"] == MARKER_NONE

    def test_hesitation_score_is_always_none(self):
        words = [_w("어", 0.0, 0.2), _w("음", 0.3, 0.5), _w("그", 0.6, 0.8), _w("수치", 0.9, 1.2)]
        row = analyze_claim_words("c1", words)
        # Null by design: markers are never converted to a confidence/truth score.
        assert row["hesitation_score"] is None


class TestArtifact:
    def test_disclaimer_and_typing_present(self):
        rows = [analyze_claim_words("c1", [_w("the", 0.0, 0.2), _w("field", 0.2, 0.6), _w("was", 0.6, 0.8), _w("dry", 0.8, 1.1)])]
        art = build_markers_artifact(rows)
        assert art["disclaimer"] == HESITATION_MARKER_DISCLAIMER
        assert art["modality_source"] == "audio"
        assert art["evidence_state"] == "operator_review_required"
        assert art["is_confidence_signal"] is False

    def test_markdown_carries_disclaimer(self):
        rows = [analyze_claim_words("c1", [_w("a", 0.0, 0.2)])]
        md = render_markers_markdown(build_markers_artifact(rows))
        assert HESITATION_MARKER_DISCLAIMER in md


def test_hesitation_demo_command(tmp_path):
    from youtube_intel.cli import main

    out = tmp_path / "hz"
    rc = main(["hesitation-demo", "--out", str(out)])
    assert rc == 0
    artifact = json.loads((out / "hesitation_markers.json").read_text(encoding="utf-8"))
    assert artifact["schema_version"] == "hesitation_markers.v1"
    assert artifact["claim_count"] == 4
    # Korean filler content survives round-trip.
    md = (out / "hesitation_markers.md").read_text(encoding="utf-8")
    assert "audio" in md


# --- P1-E: timestamp validation hardening ------------------------------------


def _four_bad_rows() -> list[dict]:
    return [
        {"word": "w1", "start": "not-a-number", "end": 1.0},
        {"word": "w2", "start": 0.0, "end": None},
        {"word": "w3", "start": 0.4, "end": 0.2},  # reversed range
        {"word": "w4", "start": -1.0, "end": 0.5},  # negative start
    ]


def test_malformed_rows_do_not_satisfy_minimum_word_count() -> None:
    """Four malformed rows used to satisfy MIN_WORDS_FOR_MARKER while pause
    analysis saw zero valid rows; the claim must now be insufficient."""
    row = analyze_claim_words("c1", _four_bad_rows())
    assert row["word_count"] == 0
    assert row["malformed_word_count"] == 4
    assert row["marker"] == MARKER_INSUFFICIENT
    reasons = sorted(m["reason"] for m in row["malformed_words"])
    assert "missing_timestamp" in reasons
    assert "non_numeric_timestamp" in reasons
    assert "reversed_range" in reasons
    assert "negative_timestamp" in reasons


def test_mixed_valid_and_malformed_rows_count_only_valid() -> None:
    words = [_w("a", 0.0, 0.2), _w("b", 0.2, 0.4), _w("bad", 0.5, 0.1), _w("c", 0.4, 0.6), _w("d", 0.6, 0.8)]
    row = analyze_claim_words("c1", words)
    assert row["word_count"] == 4
    assert row["malformed_word_count"] == 1
    assert row["marker"] == MARKER_NONE  # exactly 4 valid words, no markers


def test_negative_duration_rejected() -> None:
    row = analyze_claim_words("c1", [_w("a", 0.0, -0.5), _w("b", 0.2, 0.4), _w("c", 0.4, 0.6), _w("d", 0.6, 0.8)])
    assert row["malformed_word_count"] == 1
    assert row["malformed_words"][0]["reason"] == "negative_timestamp"
    assert row["word_count"] == 3


def test_zero_duration_duplicate_timestamps_rejected() -> None:
    # start == end rows (duplicate/instant timestamps) are unusable timing data.
    words = [_w("a", 0.0, 0.0), _w("b", 0.0, 0.0), _w("c", 0.2, 0.5), _w("d", 0.5, 0.9)]
    row = analyze_claim_words("c1", words)
    assert row["word_count"] == 2
    assert row["malformed_word_count"] == 2
    assert all(m["reason"] == "zero_duration" for m in row["malformed_words"])


def test_overlapping_timestamps_reported() -> None:
    words = [_w("a", 0.0, 0.8), _w("b", 0.3, 0.6), _w("c", 0.9, 1.2)]
    row = analyze_claim_words("c1", words)
    assert len(row["overlapping_pairs"]) == 1
    pair = row["overlapping_pairs"][0]
    assert pair["left_word"] == "a"
    assert pair["right_word"] == "b"


def test_all_invalid_claim_is_insufficient_not_clean() -> None:
    row = analyze_claim_words("c1", _four_bad_rows())
    assert row["marker"] == MARKER_INSUFFICIENT


# --- P0-D: hesitation-demo fail-closed ---------------------------------------


def test_hesitation_demo_missing_fixture_fails_closed(tmp_path, capsys):
    from youtube_intel.cli import main

    rc = main(["hesitation-demo", "--fixture", str(tmp_path / "missing.json"), "--out", str(tmp_path / "out")])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert not (tmp_path / "out" / "hesitation_markers.json").exists()


def test_hesitation_demo_empty_fixture_fails_closed(tmp_path, capsys):
    from youtube_intel.cli import main

    fixture = tmp_path / "empty.json"
    fixture.write_text("{}", encoding="utf-8")
    rc = main(["hesitation-demo", "--fixture", str(fixture), "--out", str(tmp_path / "out")])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert not (tmp_path / "out" / "hesitation_markers.json").exists()


def test_hesitation_demo_all_invalid_claims_fails_closed(tmp_path, capsys):
    from youtube_intel.cli import main

    fixture = tmp_path / "all_bad.json"
    fixture.write_text(
        json.dumps({"claims": [{"claim_id": "c1", "words": _four_bad_rows()}]}),
        encoding="utf-8",
    )
    rc = main(["hesitation-demo", "--fixture", str(fixture), "--out", str(tmp_path / "out")])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "no valid word-timestamp rows" in payload["message"]
    assert not (tmp_path / "out" / "hesitation_markers.json").exists()
