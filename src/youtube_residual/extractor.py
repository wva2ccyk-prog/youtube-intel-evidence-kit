"""Deterministic claim-candidate extraction.

This is the fallback / first-pass extractor: it splits transcript text into
sentence-level claim candidates and attaches the two-axis classification +
aside signal. It is dependency-free and deterministic so it can be tested and
so the system has a working baseline even when no cheap model is wired.

A cheap model (Stage A real lane) can replace `split_into_claim_candidates`
with smarter extraction by implementing the same ClaimCandidate output shape.
That seam is intentional: cheap model PROPOSES candidates, this module's schema
+ the trust-os gate DISPOSE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .aside_signals import AsideSignal, detect_aside_signal
from .claim_axes import ClaimAxes, classify_axes

# Sentence boundary: Korean + English terminal punctuation. Keeps it simple and
# deterministic; not linguistically perfect, which is fine for candidate surfacing.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|(?<=[다요죠음])\s+(?=[가-힣A-Z])")
_MIN_CHARS = 6
_CONTINUATION_ENDINGS = ("주요", "바로", "또 다른", "이러한", "이런", "그")


@dataclass(slots=True)
class ClaimCandidate:
    """One extracted claim candidate with both axes and aside signal."""

    claim_id: str
    text: str
    speaker: str | None
    time_ref: str | None
    axes: ClaimAxes
    aside: AsideSignal
    modality_source: str = "transcript"  # transcript|audio|visual|ocr|mixed

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "speaker": self.speaker,
            "time_ref": self.time_ref,
            "modality_source": self.modality_source,
            "content_type": self.axes.content_type,
            "evidence": self.axes.evidence,
            "confidence": self.axes.confidence,
            "content_markers": list(self.axes.content_markers),
            "evidence_markers": list(self.axes.evidence_markers),
            "aside_type": self.aside.aside_type,
            "aside_score": self.aside.score,
            "aside_markers": list(self.aside.markers),
            "needs_audio_check": self.aside.needs_audio_check,
        }


def split_into_claim_candidates(text: str) -> list[str]:
    """Deterministic sentence-level split. Filters trivially short fragments."""
    if not text or not text.strip():
        return []
    parts = _SENTENCE_SPLIT.split(text.strip())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if len(p) >= _MIN_CHARS:
            if out and out[-1].endswith(_CONTINUATION_ENDINGS):
                out[-1] = f"{out[-1]} {p}"
            else:
                out.append(p)
    # If splitting produced nothing usable, keep the whole text as one candidate.
    if not out and text.strip():
        out = [text.strip()]
    return out


def build_claim_candidates(
    text: str,
    *,
    speaker: str | None = None,
    time_ref: str | None = None,
    source_hint: str | None = "transcript",
    modality_source: str = "transcript",
    id_prefix: str = "C",
    start_index: int = 1,
    presplit: bool = True,
) -> list[ClaimCandidate]:
    """Extract claim candidates from a text unit (e.g. one segment).

    Each sentence becomes a candidate carrying two-axis classification + aside
    signal. speaker/time_ref are passed through (a diarization/segment stage
    supplies them upstream).

    ``presplit`` (default True) runs the deterministic sentence splitter. Pass
    False when ``text`` is already one assembled sentence unit (opt-in
    claim_assembly="sentence") and must map to exactly one candidate.
    """
    candidates: list[ClaimCandidate] = []
    if presplit:
        sentences = split_into_claim_candidates(text)
    else:
        stripped = text.strip()
        sentences = [stripped] if stripped else []
    for i, sentence in enumerate(sentences, start=start_index):
        axes = classify_axes(sentence, source_hint=source_hint)
        aside = detect_aside_signal(sentence)
        candidates.append(
            ClaimCandidate(
                claim_id=f"{id_prefix}{i:04d}",
                text=sentence,
                speaker=speaker,
                time_ref=time_ref,
                axes=axes,
                aside=aside,
                modality_source=modality_source,
            )
        )
    return candidates
