"""Assembly into a normalized residual-claim package.

This produces a typed, timestamp-preserving claim packet for one selected video.
It does not decide truth, run source verification, or call external providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from youtube_intel.errors import InvalidInputError

from .extractor import ClaimCandidate, build_claim_candidates
from .genres import GenreDetection, detect_genre
from .summary import MainSummary, build_main_summary


@dataclass(slots=True)
class ResidualClaimPackage:
    video_id: str
    title: str
    language: str
    claim_candidates: list[ClaimCandidate] = field(default_factory=list)
    genre: GenreDetection | None = None
    main_summary: MainSummary | None = None
    duration_seconds: int | None = None
    schema_version: str = "youtube_residual_v0.1"
    claim_assembly: str = "cue"

    @property
    def aside_candidates(self) -> list[ClaimCandidate]:
        """Aside candidates, ranked by aside score (desc), then time order."""
        asides = [c for c in self.claim_candidates if c.aside.is_aside]
        return sorted(asides, key=lambda c: (-c.aside.score, c.claim_id))

    @property
    def main_candidates(self) -> list[ClaimCandidate]:
        """Non-aside (main-content) claims in time order."""
        return [c for c in self.claim_candidates if not c.aside.is_aside]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "claim_assembly": self.claim_assembly,
            "video": {
                "video_id": self.video_id,
                "title": self.title,
                "language": self.language,
                "duration_seconds": self.duration_seconds,
            },
            "genre": self.genre.to_dict() if self.genre else None,
            "main_summary": self.main_summary.to_dict() if self.main_summary else None,
            "claim_candidates": [c.to_dict() for c in self.claim_candidates],
            "aside_candidates": [c.claim_id for c in self.aside_candidates],
            "main_candidates": [c.claim_id for c in self.main_candidates],
            "counts": {
                "total_claims": len(self.claim_candidates),
                "main_total": len(self.main_candidates),
                "aside_total": len(self.aside_candidates),
            },
        }


# --- language / encoding contract (Tier-1 hard checks live in validate.py) ----

def _looks_mojibake(text: str) -> bool:
    """Heuristic: presence of the replacement char or a run of '?' where text
    is expected indicates a decode failure (the '??? ??' class of bug)."""
    if "\ufffd" in text:
        return True
    stripped = text.strip()
    if stripped and set(stripped) <= {"?", " "}:
        return True
    return False


def normalize_segment_provenance(
    segment: dict,
    *,
    cue_index: int,
) -> dict:
    """Normalize a raw segment's timing into a complete single-cue provenance.

    Uses the same timestamp parser and conventions as sentence assembly so the
    default ``cue`` path and the opt-in ``sentence`` path produce compatible
    coordinate formats. Structured ``start``/``end`` take precedence over the
    display-oriented ``time_ref``; ``time_ref`` is only a legacy fallback for
    start; ``end`` stays ``None`` when no real end exists (never fabricated).
    Fractional precision is preserved (never rounded).

    A present-but-unparseable structured timestamp is rejected with
    ``InvalidInputError``: obviously invalid values are never silently coerced
    into plausible coordinates (e.g. a bad ``start`` cannot silently fall back
    to ``time_ref``).
    """
    from youtube_intel.sentence_assembly import parse_timestamp

    start_raw = segment.get("start")
    if start_raw not in (None, ""):
        start = parse_timestamp(start_raw)
        if start is None:
            raise InvalidInputError(
                f"segment {cue_index} has an invalid structured start timestamp: {start_raw!r}"
            )
    else:
        start = parse_timestamp(segment.get("time_ref"))
    end_raw = segment.get("end")
    if end_raw not in (None, ""):
        end = parse_timestamp(end_raw)
        if end is None:
            raise InvalidInputError(
                f"segment {cue_index} has an invalid structured end timestamp: {end_raw!r}"
            )
    else:
        end = None
    return {
        "cue_indices": [cue_index],
        "source_time_refs": [segment.get("time_ref")],
        "source_cue_coordinates": [
            {
                "cue_index": cue_index,
                "time_ref": segment.get("time_ref"),
                "start": start,
                "end": end,
                "speaker": segment.get("speaker"),
                "modality_source": segment.get("modality_source"),
                "source_hint": segment.get("source_hint"),
            }
        ],
        "span_start": start,
        "span_end": end,
    }
def assemble_segments_to_sentences(segments: list[dict]) -> list[dict]:
    """Merge consecutive segment dicts into sentence-like segment dicts.

    Treats each incoming segment as one transcript cue and applies the Korean
    sentence assembler. Speaker / source_hint / modality_source changes FORCE an
    assembly boundary, so a merged unit never spans two speakers, two
    modalities, or two evidence sources. Traceability fields
    (``source_time_refs``, ``source_cue_coordinates``, ``cue_indices``,
    ``span_start``, ``span_end``) are attached so the merged text still resolves
    to the original cue timestamps and source cue indices. Pure and deterministic.

    Timing forms supported:

    * structured ``{"start": 12.0, "end": 15.2, "time_ref": "00:12"}``
    * string timestamps ``{"start": "00:12.000", "end": "00:15.200"}``
    * legacy ``{"time_ref": "00:12"}`` (end stays None)

    ``span_start`` is the first valid cue start; ``span_end`` is the final valid
    cue end. No end timestamp is invented: when a cue has no ``end`` it is
    ``None`` in ``source_cue_coordinates``.
    """
    from youtube_intel.sentence_assembly import Cue, assemble_sentences, parse_timestamp

    cues: list[Cue] = []
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            raise ValueError(f"segment {i} is not an object")
        # Structured start/end win over the legacy time_ref fallback. A
        # present-but-unparseable structured timestamp is rejected (never
        # silently coerced), matching the default cue path policy.
        start_raw = seg.get("start")
        if start_raw not in (None, ""):
            start = parse_timestamp(start_raw)
            if start is None:
                raise InvalidInputError(f"segment {i} has an invalid structured start timestamp: {start_raw!r}")
        else:
            start = parse_timestamp(seg.get("time_ref"))
        end_raw = seg.get("end")
        if end_raw not in (None, ""):
            end = parse_timestamp(end_raw)
            if end is None:
                raise InvalidInputError(f"segment {i} has an invalid structured end timestamp: {end_raw!r}")
        else:
            end = None
        cues.append(
            Cue(
                index=i,
                text=str(seg.get("text", "") or ""),
                start=start,
                end=end,
                time_ref=seg.get("time_ref"),
                speaker=seg.get("speaker"),
                modality_source=seg.get("modality_source"),
                source_hint=seg.get("source_hint"),
            )
        )
    units = assemble_sentences(cues)

    out: list[dict] = []
    for unit in units:
        first = segments[unit.cue_indices[0]]
        out.append(
            {
                "text": unit.text,
                "speaker": first.get("speaker"),
                "time_ref": first.get("time_ref"),
                "source_hint": first.get("source_hint", "transcript"),
                "modality_source": first.get("modality_source", "transcript"),
                "source_time_refs": [segments[i].get("time_ref") for i in unit.cue_indices],
                "source_cue_coordinates": [dict(c) for c in unit.source_cue_coordinates],
                "cue_indices": list(unit.cue_indices),
                "span_start": unit.start,
                "span_end": unit.end,
            }
        )
    return out


def build_residual_package(
    *,
    video_id: str,
    title: str,
    language: str,
    segments: list[dict],
    duration_seconds: int | None = None,
    genre_override: str | None = None,
    claim_assembly: str = "cue",
) -> ResidualClaimPackage:
    """Build a package from segment dicts.

    Each segment dict: {text, speaker?, time_ref?, modality_source?}.
    Claim ids are globally sequential across segments.

    ``claim_assembly`` = ``"cue"`` (default) keeps the current per-segment
    behavior byte-identical. ``"sentence"`` first merges consecutive segments
    into sentence-like units (Korean-aware) before extracting candidates, so a
    caption-fragment stream becomes fuller claim sentences (see
    docs/CLAIM_ASSEMBLY.md).

    The package now also carries:
    - detected genre (or override) -> drives required output sections
    - main_summary scaffold -> preserves central content alongside asides
    - duration_seconds -> enables coverage / ultra_long_handling rubric checks
    """
    if claim_assembly not in ("cue", "sentence"):
        raise ValueError(f"claim_assembly must be 'cue' or 'sentence', got {claim_assembly!r}")
    sentence_mode = claim_assembly == "sentence"
    if sentence_mode:
        segments = assemble_segments_to_sentences(segments)

    candidates: list[ClaimCandidate] = []
    next_index = 1
    for i, seg in enumerate(segments):
        if sentence_mode:
            # Assembled units already carry complete provenance.
            cue_indices = seg.get("cue_indices")
            source_time_refs = seg.get("source_time_refs")
            source_cue_coordinates = seg.get("source_cue_coordinates")
            span_start = seg.get("span_start")
            span_end = seg.get("span_end")
        else:
            # Default cue mode: normalize the raw segment into a single-cue
            # provenance structure so real structured start/end timestamps are
            # preserved (time_ref is only a legacy fallback for start).
            provenance = normalize_segment_provenance(seg, cue_index=i)
            cue_indices = provenance["cue_indices"]
            source_time_refs = provenance["source_time_refs"]
            source_cue_coordinates = provenance["source_cue_coordinates"]
            span_start = provenance["span_start"]
            span_end = provenance["span_end"]
        seg_candidates = build_claim_candidates(
            seg.get("text", ""),
            speaker=seg.get("speaker"),
            time_ref=seg.get("time_ref"),
            source_hint=seg.get("source_hint", "transcript"),
            modality_source=seg.get("modality_source", "transcript"),
            start_index=next_index,
            presplit=not sentence_mode,
            cue_indices=cue_indices,
            source_time_refs=source_time_refs,
            source_cue_coordinates=source_cue_coordinates,
            span_start=span_start,
            span_end=span_end,
        )
        candidates.extend(seg_candidates)
        next_index += len(seg_candidates)

    # Genre detection from concatenated title + segment text (simple, deterministic).
    detection_text = title + "\n" + "\n".join(s.get("text", "") for s in segments)
    genre = detect_genre(detection_text, override=genre_override)

    # Main summary scaffold (preserves central content; cheap-model upgrade fills).
    main_summary = build_main_summary(candidates, genre=genre)

    return ResidualClaimPackage(
        video_id=video_id,
        title=title,
        language=language,
        claim_candidates=candidates,
        genre=genre,
        main_summary=main_summary,
        duration_seconds=duration_seconds,
        claim_assembly=claim_assembly,
    )


