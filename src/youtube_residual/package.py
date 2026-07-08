"""Assembly into a normalized residual-claim package.

This produces a typed, timestamp-preserving claim packet for one selected video.
It does not decide truth, run source verification, or call external providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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


def assemble_segments_to_sentences(segments: list[dict]) -> list[dict]:
    """Merge consecutive segment dicts into sentence-like segment dicts.

    Treats each incoming segment as one transcript cue and applies the Korean
    sentence assembler. Speaker / source_hint / modality_source are inherited
    from the first cue of each merged unit; ``time_ref`` spans from the first
    cue. Traceability fields (``source_time_refs``) are attached so the merged
    text still resolves to the original cue timestamps. Pure and deterministic.
    """
    from youtube_intel.sentence_assembly import Cue, assemble_sentences, parse_timestamp

    cues: list[Cue] = []
    for i, seg in enumerate(segments):
        start = parse_timestamp(seg.get("time_ref"))
        cues.append(Cue(index=i, text=str(seg.get("text", "") or ""), start=start, end=start))
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
    for seg in segments:
        seg_candidates = build_claim_candidates(
            seg.get("text", ""),
            speaker=seg.get("speaker"),
            time_ref=seg.get("time_ref"),
            source_hint=seg.get("source_hint", "transcript"),
            modality_source=seg.get("modality_source", "transcript"),
            start_index=next_index,
            presplit=not sentence_mode,
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


