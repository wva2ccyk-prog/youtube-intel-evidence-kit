"""Minimal residual-value core for cost-gated video evidence analysis.

The public API intentionally foregrounds the original thesis: selected videos
should first become timestamped, typed, uncertainty-preserving evidence packets
before anyone spends on ASR, OCR, vision, model review, or source verification.

This module is not a generic YouTube summarizer, scraper, monitor, transcript
cleaner, retrieval system, or truth-verification engine.
"""

from .claim_axes import (
    CONTENT_CLAIM_TYPES,
    EPISTEMIC_EVIDENCE,
    CONFIDENCE_LEVELS,
    ClaimAxes,
    classify_axes,
    classify_content_axis,
    classify_epistemic_axis,
    normalize_content_type,
    normalize_evidence,
)
from .aside_signals import (
    AsideSignal,
    detect_aside_signal,
    ASIDE_NONE,
    ASIDE_TYPE1_HIDDEN,
    ASIDE_TYPE2_UNFORMED,
)
from .extractor import (
    ClaimCandidate,
    split_into_claim_candidates,
    build_claim_candidates,
)
from .genres import (
    GENRES,
    RISK_DOMAIN,
    GENRE_REQUIRED_SECTIONS,
    GenreDetection,
    canonical_genre,
    detect_genre,
)
from .summary import (
    MainSummary,
    TimelineEntry,
    KeyInformationRow,
    coerce_one_line_override,
    build_main_summary,
)
from .package import (
    ResidualClaimPackage,
    build_residual_package,
)
from .validate import ValidationResult, validate_package

__all__ = [
    # axes
    "CONTENT_CLAIM_TYPES", "EPISTEMIC_EVIDENCE", "CONFIDENCE_LEVELS",
    "ClaimAxes", "classify_axes", "classify_content_axis", "classify_epistemic_axis",
    "normalize_content_type", "normalize_evidence",
    # asides
    "AsideSignal", "detect_aside_signal",
    "ASIDE_NONE", "ASIDE_TYPE1_HIDDEN", "ASIDE_TYPE2_UNFORMED",
    # extraction
    "ClaimCandidate", "split_into_claim_candidates", "build_claim_candidates",
    # genres
    "GENRES", "RISK_DOMAIN", "GENRE_REQUIRED_SECTIONS",
    "GenreDetection", "canonical_genre", "detect_genre",
    # summary (main content preservation)
    "MainSummary", "TimelineEntry", "KeyInformationRow", "coerce_one_line_override", "build_main_summary",
    # package
    "ResidualClaimPackage", "build_residual_package",
    # validation (Tier 1)
    "ValidationResult", "validate_package",
]

__version__ = "0.1.0"
