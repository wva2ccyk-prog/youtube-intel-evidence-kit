"""Deterministic Korean-aware sentence assembly for transcript cues.

Korean YouTube auto-captions carry no punctuation and cut every ~4-8 words, so a
single caption cue is almost always a mid-sentence fragment (e.g. "묻습니다 국민연금
과연 개인 저축보다"). When one cue becomes one claim candidate, the resulting
``claim_text`` is a fragment: it hurts operator review, claim matching, and
cross-video terrain clustering.

This module merges *consecutive* cues into sentence-like units using deterministic
heuristics. It is pure (no I/O, no network, stdlib only) so it is fully testable.

Traceability contract
---------------------
An assembled unit NEVER invents text: its ``text`` is exactly the whitespace-joined
cue texts, and it records the span (``start``/``end``) plus the ``cue_indices`` it
was built from. Every assembled unit therefore resolves back to the real cues (and
thus their evidence ids / timestamps) it merged.

Heuristics (see docs/CLAIM_ASSEMBLY.md)
---------------------------------------
- A cue whose final token ends in a Korean sentence-final ending (…다, …요, …죠,
  …니다, …습니까, …네요, …거든요, …잖아요, …입니다, …) or terminal punctuation
  (``. ? ! 。 ！ ？ …``) CLOSES the current sentence.
- Hard caps force a close: ``max_chars`` (~200) or ``max_span_seconds`` (~15s).
- Otherwise the cue "ends mid-word" and joins forward into the next cue.
- A cue that is already sentence-final passes through as its own single-cue unit.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from .errors import InvalidInputError

__all__ = [
    "Cue",
    "AssembledUnit",
    "assemble_sentences",
    "assemble_from_dicts",
    "is_sentence_final",
    "parse_timestamp",
    "parse_structured_timestamp",
    "format_timestamp",
    "DEFAULT_MAX_CHARS",
    "DEFAULT_MAX_SPAN_SECONDS",
]

DEFAULT_MAX_CHARS = 200
DEFAULT_MAX_SPAN_SECONDS = 15.0

# High-precision multi-character sentence-final surface forms. Longer forms are
# checked first so the most specific ending wins.
_STRONG_ENDINGS: tuple[str, ...] = (
    "습니다", "습니까", "ㅂ니다", "입니다", "합니다", "됩니다", "겠습니다",
    "거든요", "잖아요", "는데요", "군요", "네요", "지요", "세요",
    "라고요", "다고요", "라구요", "다구요", "라니까요", "다니까요",
    "겠죠", "겠지요", "게요", "래요", "래죠",
    "에요", "예요", "어요", "아요", "해요", "여요", "이요", "워요",
)
# Short/single-syllable polite endings. Safe: postpositions rarely end this way.
_POLITE_ENDINGS: tuple[str, ...] = ("요", "죠", "됨")
# Plain declarative "다" is genuinely sentence-final in most cases, but a handful
# of postpositions/connectives also end in "다" mid-sentence. Guard against those.
_NON_FINAL_DA_SUFFIXES: tuple[str, ...] = ("보다", "부터", "다가", "라다", "으로다")

_TERMINAL_PUNCT = set(".?!。！？…")


def is_sentence_final(text: str) -> bool:
    """Return True if ``text`` looks like a completed Korean sentence.

    Deterministic surface-form check: terminal punctuation, a strong honorific
    ending, a polite ending, or a plain declarative "-다" that is not a known
    non-final "-다" postposition.
    """
    stripped = text.rstrip()
    if not stripped:
        return False
    if stripped[-1] in _TERMINAL_PUNCT:
        return True
    tokens = stripped.split()
    if not tokens:
        return False
    last = tokens[-1]
    # Strip trailing quotes/brackets that sometimes cling to caption tokens.
    last = last.rstrip("\"'”’)]》』」")
    if not last:
        return False
    for ending in _STRONG_ENDINGS:
        if last.endswith(ending):
            return True
    for ending in _POLITE_ENDINGS:
        if last.endswith(ending):
            return True
    if last.endswith("다") and not any(last.endswith(s) for s in _NON_FINAL_DA_SUFFIXES):
        return True
    return False


@dataclass(slots=True, frozen=True)
class Cue:
    """One raw transcript cue (a single caption line).

    ``index`` is the cue's position in the source cue stream; it is preserved on
    the assembled unit so traceability back to evidence records is exact.
    ``start``/``end`` are seconds (float) or None when timing is unavailable.
    ``time_ref`` is the original display timestamp string (``mm:ss``), retained
    for provenance even when structured start/end seconds are also present.

    ``speaker`` / ``modality_source`` / ``source_hint`` carry per-cue provenance.
    When any of these change between two consecutive cues, assembly FORCES a
    boundary: a merged sentence must never attribute another speaker's words,
    another modality's text, or a different evidence source to the first cue.
    """

    index: int
    text: str
    start: float | None = None
    end: float | None = None
    time_ref: Any = None
    speaker: Any = None
    modality_source: Any = None
    source_hint: Any = None


@dataclass(slots=True)
class AssembledUnit:
    """A sentence-like unit merged from one or more consecutive cues.

    ``speaker`` / ``modality_source`` / ``source_hint`` are the provenance of the
    unit's cues (identical for every cue in the unit, because provenance changes
    force boundaries). ``source_time_refs`` keeps the legacy scalar per-cue
    timing list (start seconds only) and ``source_cue_coordinates`` keeps the
    complete structured per-cue timing records so the merged text resolves to
    every original timestamp.
    """

    text: str
    start: float | None
    end: float | None
    cue_indices: list[int] = field(default_factory=list)
    speaker: Any = None
    modality_source: Any = None
    source_hint: Any = None
    source_time_refs: list[float | None] = field(default_factory=list)
    source_cue_coordinates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def span_seconds(self) -> float | None:
        if self.start is None or self.end is None:
            return None
        return max(0.0, self.end - self.start)

    @property
    def is_merged(self) -> bool:
        return len(self.cue_indices) > 1

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "cue_indices": list(self.cue_indices),
            "cue_count": len(self.cue_indices),
            "speaker": self.speaker,
            "modality_source": self.modality_source,
            "source_hint": self.source_hint,
            "source_time_refs": list(self.source_time_refs),
            "source_cue_coordinates": [dict(c) for c in self.source_cue_coordinates],
        }


def _norm(text: str) -> str:
    return " ".join(text.split())


def _norm_provenance(value: Any) -> Any:
    """Normalize a provenance value for change detection.

    Missing/blank/``unknown`` values all collapse to ``None`` so that absent
    metadata never fabricates a boundary. Two distinct non-blank values are a
    real provenance change and force a boundary.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "n/a", "na", "none"}:
        return None
    return text


def _provenance_changed(previous: Cue, current: Cue) -> bool:
    """True when speaker, modality, or source hint changed between cues."""
    if _norm_provenance(previous.speaker) != _norm_provenance(current.speaker):
        return True
    if _norm_provenance(previous.modality_source) != _norm_provenance(current.modality_source):
        return True
    if _norm_provenance(previous.source_hint) != _norm_provenance(current.source_hint):
        return True
    return False


def _flush(buffer: list[Cue]) -> AssembledUnit | None:
    if not buffer:
        return None
    text = _norm(" ".join(c.text for c in buffer))
    starts = [c.start for c in buffer if c.start is not None]
    start = starts[0] if starts else None
    # span_end is the END of the final cue only. When the final cue has no end
    # timestamp, span_end stays None: we never claim a duration through a cue
    # whose end is unknown (no fabricated timestamps).
    final_cue = buffer[-1]
    end = final_cue.end
    first = buffer[0]
    source_cue_coordinates = [
        {
            "cue_index": c.index,
            "time_ref": c.time_ref,
            "start": c.start,
            "end": c.end,
        }
        for c in buffer
    ]
    return AssembledUnit(
        text=text,
        start=start,
        end=end,
        cue_indices=[c.index for c in buffer],
        speaker=first.speaker,
        modality_source=first.modality_source,
        source_hint=first.source_hint,
        source_time_refs=[c.start for c in buffer],
        source_cue_coordinates=source_cue_coordinates,
    )


def assemble_sentences(
    cues,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    max_span_seconds: float = DEFAULT_MAX_SPAN_SECONDS,
) -> list[AssembledUnit]:
    """Merge consecutive ``Cue`` objects into sentence-like ``AssembledUnit``s.

    Empty/whitespace-only cues are skipped (they carry no text and no boundary
    signal). The order of the input is preserved. Pure and deterministic.
    """
    units: list[AssembledUnit] = []
    buffer: list[Cue] = []
    running_chars = 0

    for cue in cues:
        piece = _norm(cue.text)
        if not piece:
            continue
        # Provenance change: flush the previous buffer BEFORE the new cue is
        # appended, so the new speaker/modality/source starts its own unit.
        if buffer and _provenance_changed(buffer[-1], cue):
            unit = _flush(buffer)
            if unit is not None:
                units.append(unit)
            buffer = []
            running_chars = 0
        buffer.append(cue)
        running_chars += len(piece) + (1 if len(buffer) > 1 else 0)

        # Determine whether to close the current sentence.
        close = False
        if is_sentence_final(piece):
            close = True
        elif running_chars >= max_chars:
            close = True
        else:
            span_start = next((c.start for c in buffer if c.start is not None), None)
            if span_start is not None and cue.end is not None:
                if (cue.end - span_start) >= max_span_seconds:
                    close = True

        if close:
            unit = _flush(buffer)
            if unit is not None:
                units.append(unit)
            buffer = []
            running_chars = 0

    tail = _flush(buffer)
    if tail is not None:
        units.append(tail)
    return units


def parse_timestamp(value) -> float | None:
    """Parse seconds or a well-formed ``mm:ss`` / ``hh:mm:ss`` timestamp.

    Clock forms are strict: component signs are rejected, seconds must be less
    than 60, and the minute component in ``hh:mm:ss`` must be less than 60.
    ``mm:ss`` intentionally permits minutes above 59 for long-form media.
    Returns ``None`` on failure.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    seconds_pattern = r"\d+(?:\.\d+)?"
    try:
        if len(parts) == 3:
            hours, minutes, seconds_text = parts
            if not hours.isdigit() or not minutes.isdigit():
                return None
            if re.fullmatch(seconds_pattern, seconds_text) is None:
                return None
            minute_value = int(minutes)
            second_value = float(seconds_text)
            if minute_value >= 60 or second_value >= 60:
                return None
            return int(hours) * 3600 + minute_value * 60 + second_value
        if len(parts) == 2:
            minutes, seconds_text = parts
            if not minutes.isdigit():
                return None
            if re.fullmatch(seconds_pattern, seconds_text) is None:
                return None
            second_value = float(seconds_text)
            if second_value >= 60:
                return None
            return int(minutes) * 60 + second_value
        if len(parts) == 1:
            return float(parts[0])
        return None
    except (ValueError, IndexError):
        return None


def parse_structured_timestamp(
    value: Any,
    *,
    field: str,
    allow_none: bool = True,
) -> float | None:
    """Strictly parse a structured timestamp into finite non-negative seconds.

    Used by both cue and sentence assembly so the two modes share one strict
    rule. Rejects booleans, NaN, +/-Infinity, negative values, and unparseable
    strings. ``None``/blank input returns ``None`` only when ``allow_none`` is
    true. Fractional precision is preserved; nothing is rounded.
    """
    if value is None:
        if allow_none:
            return None
        raise InvalidInputError(f"{field} is required")
    if isinstance(value, bool):
        raise InvalidInputError(f"{field} must be a number or timestamp string, got a boolean")
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            if allow_none:
                return None
            raise InvalidInputError(f"{field} is required")
        if text.startswith("-"):
            raise InvalidInputError(f"{field} must be non-negative")
        parsed = parse_timestamp(text)
        if parsed is None:
            raise InvalidInputError(f"{field} is not a valid timestamp: {value!r}")
    else:
        raise InvalidInputError(f"{field} must be a number or timestamp string, got {type(value).__name__}")
    if not math.isfinite(parsed):
        raise InvalidInputError(f"{field} must be finite (NaN/Infinity rejected)")
    if parsed < 0:
        raise InvalidInputError(f"{field} must be non-negative")
    return parsed


def format_timestamp(seconds: float | None, *, hms: bool = False) -> str | None:
    """Format seconds as ``mm:ss`` (default) or ``hh:mm:ss``. Returns None for None."""
    if seconds is None:
        return None
    total = int(max(0.0, float(seconds)))
    if hms or total >= 3600:
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"


def assemble_from_dicts(
    cues,
    *,
    text_key: str = "text",
    start_key: str = "start",
    end_key: str = "end",
    time_ref_key: str = "time_ref",
    speaker_key: str = "speaker",
    modality_key: str = "modality_source",
    source_hint_key: str = "source_hint",
    max_chars: int = DEFAULT_MAX_CHARS,
    max_span_seconds: float = DEFAULT_MAX_SPAN_SECONDS,
) -> list[AssembledUnit]:
    """Convenience wrapper: build ``Cue``s from dict rows, then assemble.

    Timestamps under ``start_key``/``end_key`` may be seconds or ``mm:ss`` strings.
    The dict's original position becomes the cue index. Provenance fields
    (``speaker`` / ``modality_source`` / ``source_hint``) are propagated into the
    ``Cue`` so this entry point enforces the same speaker/modality/source
    boundaries as the rest of the assembler; key names are configurable.
    """
    cue_objs: list[Cue] = []
    for i, row in enumerate(cues):
        if not isinstance(row, dict):
            raise ValueError(f"cue row {i} is not an object")
        # Structured start wins; time_ref is the legacy fallback for start.
        start = parse_timestamp(row.get(start_key))
        if start is None:
            start = parse_timestamp(row.get(time_ref_key))
        cue_objs.append(
            Cue(
                index=i,
                text=str(row.get(text_key, "") or ""),
                start=start,
                end=parse_timestamp(row.get(end_key)),
                time_ref=row.get(time_ref_key),
                speaker=row.get(speaker_key),
                modality_source=row.get(modality_key),
                source_hint=row.get(source_hint_key),
            )
        )
    return assemble_sentences(
        cue_objs, max_chars=max_chars, max_span_seconds=max_span_seconds
    )
