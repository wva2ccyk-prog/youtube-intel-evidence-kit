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


def build_residual_package(
    *,
    video_id: str,
    title: str,
    language: str,
    segments: list[dict],
    duration_seconds: int | None = None,
    genre_override: str | None = None,
) -> ResidualClaimPackage:
    """Build a package from segment dicts.

    Each segment dict: {text, speaker?, time_ref?, modality_source?}.
    Claim ids are globally sequential across segments.

    The package now also carries:
    - detected genre (or override) -> drives required output sections
    - main_summary scaffold -> preserves central content alongside asides
    - duration_seconds -> enables coverage / ultra_long_handling rubric checks
    """
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
    )


