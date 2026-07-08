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

from dataclasses import dataclass, field

__all__ = [
    "Cue",
    "AssembledUnit",
    "assemble_sentences",
    "assemble_from_dicts",
    "is_sentence_final",
    "parse_timestamp",
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
    """

    index: int
    text: str
    start: float | None = None
    end: float | None = None


@dataclass(slots=True)
class AssembledUnit:
    """A sentence-like unit merged from one or more consecutive cues."""

    text: str
    start: float | None
    end: float | None
    cue_indices: list[int] = field(default_factory=list)

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
        }


def _norm(text: str) -> str:
    return " ".join(text.split())


def _flush(buffer: list[Cue]) -> AssembledUnit | None:
    if not buffer:
        return None
    text = _norm(" ".join(c.text for c in buffer))
    starts = [c.start for c in buffer if c.start is not None]
    ends = [c.end for c in buffer if c.end is not None]
    start = starts[0] if starts else None
    end = ends[-1] if ends else None
    return AssembledUnit(
        text=text,
        start=start,
        end=end,
        cue_indices=[c.index for c in buffer],
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
    """Parse a timestamp into seconds. Accepts float/int seconds or ``mm:ss`` /
    ``hh:mm:ss`` strings. Returns None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(parts[0])
    except (ValueError, IndexError):
        return None


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
    max_chars: int = DEFAULT_MAX_CHARS,
    max_span_seconds: float = DEFAULT_MAX_SPAN_SECONDS,
) -> list[AssembledUnit]:
    """Convenience wrapper: build ``Cue``s from dict rows, then assemble.

    Timestamps under ``start_key``/``end_key`` may be seconds or ``mm:ss`` strings.
    The dict's original position becomes the cue index.
    """
    cue_objs: list[Cue] = []
    for i, row in enumerate(cues):
        cue_objs.append(
            Cue(
                index=i,
                text=str(row.get(text_key, "") or ""),
                start=parse_timestamp(row.get(start_key)),
                end=parse_timestamp(row.get(end_key)),
            )
        )
    return assemble_sentences(
        cue_objs, max_chars=max_chars, max_span_seconds=max_span_seconds
    )
