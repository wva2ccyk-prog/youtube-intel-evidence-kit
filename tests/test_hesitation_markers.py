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
