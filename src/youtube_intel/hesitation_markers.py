"""Hesitation markers — PURE deterministic paralinguistic analysis core (Tier 1).

The project thesis values paralinguistic residue in expert speech — hesitation,
pauses, and restarts — as evidence that captions erase. The caption-first pipeline
cannot capture this. This module derives *speech-flow markers* deterministically
from ASR word-level timestamps for an already-selected (need-gated) claim span.

This module is PURE and fully offline-testable:
- It never touches audio, never imports faster-whisper, never downloads anything.
- Its input is a list of word entries ``[{word, start, end}]`` (seconds floats)
  for an audio span, plus the claim id / expected text and time span.

WHAT THIS IS NOT (by design):
- It is NOT a confidence, truth, or uncertainty score. ``hesitation_score`` is
  deliberately ``None``. Markers are listen-and-judge cues for the operator, not
  a verdict on the claim. See ``HESITATION_MARKER_DISCLAIMER``.
- Tier 1 is deterministic rule detection only. No prosody (pitch/energy), no
  learned calibration, no scoring. Promotion to a Tier 2 (scored/calibrated)
  signal requires an explicit calibration experiment, like the clusterer gate.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "hesitation_markers.v1"

# --- Deterministic rule constants (documented; tuned for Korean expert speech) ---

# Inter-word silence (seconds) that counts as a mid-span pause. 0.7s is long
# enough to exclude ordinary articulation gaps while catching deliberate
# hesitation / word-search pauses in continuous Korean speech.
MIN_PAUSE_SECONDS = 0.7

# Standalone Korean filler tokens. Only counted when a word equals one of these
# after stripping surrounding punctuation (isolated filler), never as a
# substring of a content word. Consecutive fillers are counted individually.
KOREAN_FILLERS: frozenset[str] = frozenset(
    {"어", "음", "그", "저기", "뭐랄까", "그러니까", "뭐지", "아니"}
)

# For the strict-prefix restart rule, the shorter (prefix) word must be at least
# this many characters. This avoids treating a single-syllable word that merely
# begins the next word as a restart.
MIN_RESTART_PREFIX_LEN = 2

# A claim must have at least this many words before a positive marker is emitted;
# below this we cannot meaningfully judge speech flow.
MIN_WORDS_FOR_MARKER = 4

# Marker labels.
MARKER_CANDIDATE = "hesitation_candidate"
MARKER_NONE = "no_hesitation_detected"
MARKER_INSUFFICIENT = "insufficient_words"

# Characters stripped from word edges before filler / restart comparison.
_PUNCT_CHARS = " \t\r\n.,!?;:\"'`~()[]{}<>…·‥。、，？！；：「」『』“”‘’《》〈〉．"

# Mandatory disclaimer reused verbatim in EVERY artifact this feature produces.
HESITATION_MARKER_DISCLAIMER = (
    "These hesitation markers indicate speech-flow phenomena only (pauses, "
    "fillers, restarts). They are NOT evidence that a claim is uncertain, "
    "false, or true, and they are NOT a confidence score. The operator must "
    "listen to the referenced span before drawing any conclusion. Markers are "
    "listen-and-judge cues, not a verdict."
)


def strip_word_punctuation(word: Any) -> str:
    """Return ``word`` stripped of surrounding whitespace/punctuation.

    Korean content is preserved intact; only edge punctuation is removed.
    """
    if word is None:
        return ""
    return str(word).strip(_PUNCT_CHARS)


def _normalized_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coerce and sort word entries by start time. Skips entries without times."""
    out: list[dict[str, Any]] = []
    for w in words or []:
        start = w.get("start")
        end = w.get("end")
        if start is None or end is None:
            continue
        try:
            fs = float(start)
            fe = float(end)
        except (TypeError, ValueError):
            continue
        out.append({"word": str(w.get("word", "")), "start": fs, "end": fe})
    out.sort(key=lambda x: (x["start"], x["end"]))
    return out


def detect_pause_events(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect mid-span pauses: inter-word gaps >= ``MIN_PAUSE_SECONDS``.

    Gaps are measured strictly *between consecutive words*, so silence at the
    span edges (before the first word or after the last word) is excluded by
    design — a late start or early finish relative to the claim span is not a
    pause. Consecutive words are ``words[i]`` and ``words[i+1]``.
    """
    events: list[dict[str, Any]] = []
    nrm = _normalized_words(words)
    for i in range(len(nrm) - 1):
        gap = nrm[i + 1]["start"] - nrm[i]["end"]
        if gap >= MIN_PAUSE_SECONDS:
            events.append(
                {
                    "after_word_index": i,
                    "gap_seconds": round(gap, 3),
                    "at_seconds": round(nrm[i]["end"], 3),
                    "next_word": nrm[i + 1]["word"],
                }
            )
    return events


def count_fillers(words: list[dict[str, Any]]) -> int:
    """Count isolated Korean filler tokens (each occurrence counts individually)."""
    count = 0
    for w in words or []:
        token = strip_word_punctuation(w.get("word"))
        if token in KOREAN_FILLERS:
            count += 1
    return count


def _is_restart_pair(a: str, b: str) -> bool:
    """True when adjacent tokens ``a``, ``b`` form a restart.

    Restart when the tokens are identical, OR one is a strict prefix of the
    other and the shorter (prefix) token is at least ``MIN_RESTART_PREFIX_LEN``
    characters long.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= MIN_RESTART_PREFIX_LEN and longer.startswith(shorter):
        return True
    return False


def count_restarts(words: list[dict[str, Any]]) -> int:
    """Count adjacent restart pairs (prefix or identical)."""
    tokens = [strip_word_punctuation(w.get("word")) for w in (words or [])]
    count = 0
    for i in range(len(tokens) - 1):
        if _is_restart_pair(tokens[i], tokens[i + 1]):
            count += 1
    return count


def speech_span_seconds(words: list[dict[str, Any]]) -> float | None:
    """Total speech span from first word start to last word end, or None."""
    nrm = _normalized_words(words)
    if not nrm:
        return None
    return round(nrm[-1]["end"] - nrm[0]["start"], 3)


def analyze_claim_words(
    claim_id: str,
    words: list[dict[str, Any]],
    *,
    expected_text: str | None = None,
    span_start: float | None = None,
    span_end: float | None = None,
) -> dict[str, Any]:
    """Analyze one claim's word list into a deterministic marker row.

    ``hesitation_score`` is ALWAYS ``None`` by design: this system does not
    convert markers into a confidence/truth score. Markers are listen-and-judge
    cues for the operator only.
    """
    word_count = len(words or [])
    pause_events = detect_pause_events(words)
    filler_count = count_fillers(words)
    restart_count = count_restarts(words)

    if word_count < MIN_WORDS_FOR_MARKER:
        marker = MARKER_INSUFFICIENT
    elif len(pause_events) >= 1 or filler_count >= 2 or restart_count >= 1:
        marker = MARKER_CANDIDATE
    else:
        marker = MARKER_NONE

    return {
        "claim_id": claim_id,
        "expected_text": expected_text,
        "span_start_s": round(float(span_start), 3) if span_start is not None else None,
        "span_end_s": round(float(span_end), 3) if span_end is not None else None,
        "word_count": word_count,
        "speech_span_s": speech_span_seconds(words),
        "pause_events": pause_events,
        "pause_count": len(pause_events),
        "filler_count": filler_count,
        "restart_count": restart_count,
        # hesitation_score stays None BY DESIGN. Markers are NOT a confidence or
        # truth score; the operator must listen before judging. Do not fill this.
        "hesitation_score": None,
        "marker": marker,
    }


def build_markers_artifact(
    rows: list[dict[str, Any]],
    *,
    provenance: dict[str, Any] | None = None,
    skipped: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap per-claim marker rows into a typed, disclaimed artifact.

    Marks modality as ``audio`` and evidence_state as
    ``operator_review_required`` consistent with the repo's evidence typing.
    """
    candidates = [r for r in rows if r.get("marker") == MARKER_CANDIDATE]
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "modality_source": "audio",
        "evidence_state": "operator_review_required",
        "is_confidence_signal": False,
        "hesitation_score_policy": "null_by_design_tier1_no_scoring",
        "disclaimer": HESITATION_MARKER_DISCLAIMER,
        "rules": {
            "min_pause_seconds": MIN_PAUSE_SECONDS,
            "korean_fillers": sorted(KOREAN_FILLERS),
            "min_restart_prefix_len": MIN_RESTART_PREFIX_LEN,
            "min_words_for_marker": MIN_WORDS_FOR_MARKER,
        },
        "claim_count": len(rows),
        "hesitation_candidate_count": len(candidates),
        "markers": rows,
        "skipped_claims": skipped or [],
        "provenance": provenance or {},
    }


def render_markers_markdown(artifact: dict[str, Any]) -> str:
    """Render a marker artifact as operator-readable markdown."""
    lines = [
        "# Hesitation Markers (Tier 1, audio modality)",
        "",
        "> " + HESITATION_MARKER_DISCLAIMER,
        "",
        "## Summary",
        f"- schema_version: {artifact.get('schema_version', '-')}",
        f"- modality_source: {artifact.get('modality_source', '-')}",
        f"- evidence_state: {artifact.get('evidence_state', '-')}",
        f"- is_confidence_signal: {artifact.get('is_confidence_signal', False)}",
        f"- claim_count: {artifact.get('claim_count', 0)}",
        f"- hesitation_candidate_count: {artifact.get('hesitation_candidate_count', 0)}",
        "",
    ]

    prov = artifact.get("provenance", {})
    if prov:
        lines.extend(["## Provenance"])
        for key in ("audio_file", "model", "language", "windows_analyzed", "backend"):
            if key in prov:
                lines.append(f"- {key}: {prov.get(key)}")
        lines.append("")

    lines.extend(
        [
            "## Markers",
            "",
            "| claim_id | time | text | words | pauses | fillers | restarts | score | marker |",
            "|----------|------|------|-------|--------|---------|----------|-------|--------|",
        ]
    )
    for row in artifact.get("markers", []):
        span = row.get("span_start_s")
        text = str(row.get("expected_text") or "")[:60].replace("|", "\\|")
        lines.append(
            f"| {row.get('claim_id', '-')} "
            f"| {span if span is not None else '-'} "
            f"| {text} "
            f"| {row.get('word_count', 0)} "
            f"| {row.get('pause_count', 0)} "
            f"| {row.get('filler_count', 0)} "
            f"| {row.get('restart_count', 0)} "
            f"| {row.get('hesitation_score')} "
            f"| {row.get('marker', '-')} |"
        )
    lines.append("")

    skipped = artifact.get("skipped_claims", [])
    if skipped:
        lines.extend(["## Skipped Claims", ""])
        for s in skipped:
            lines.append(f"- `{s.get('claim_id', '-')}`: {s.get('reason', '-')}")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "**hesitation_score is null by design. These markers are not a "
            "confidence or truth signal. Listen to the span before judging.**",
            "",
        ]
    )
    return "\n".join(lines)
