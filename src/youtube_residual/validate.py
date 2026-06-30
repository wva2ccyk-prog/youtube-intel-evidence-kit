"""Tier-1 deterministic validation (hard-fail gate).

These are the machine-checkable hard checks from the proposal's validator
section. They run BEFORE any rendering/synthesis. The most important one is the
encoding/language contract: the current youtube-intel gate passed a mojibake
title ('??? ??') with issue_count 0, which makes every downstream judgment
untrustworthy. This module fails closed on that class of bug.

This is intentionally small and deterministic. Tier-2 heuristic checks and
Tier-3 model-scored rubric are out of scope for this dependency-free core.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .claim_axes import CONFIDENCE_LEVELS, CONTENT_CLAIM_TYPES, EPISTEMIC_EVIDENCE
from .package import ResidualClaimPackage, _looks_mojibake


@dataclass(slots=True)
class ValidationResult:
    status: str  # "pass" | "fail"
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict:
        return {"status": self.status, "issue_count": len(self.issues), "issues": list(self.issues)}


def validate_package(package: ResidualClaimPackage) -> ValidationResult:
    issues: list[str] = []

    # --- encoding / language contract (the '??? ??' class) ---
    if not package.language or not package.language.strip():
        issues.append("video.language is empty (language contract requires a value)")
    if _looks_mojibake(package.title):
        issues.append(f"video.title looks mojibake/undecoded: {package.title!r}")
    if not package.title or not package.title.strip():
        issues.append("video.title is empty")

    # --- schema_version pin ---
    if not package.schema_version:
        issues.append("schema_version is not pinned")

    # --- per-claim required fields + enum membership ---
    seen_ids: set[str] = set()
    for c in package.claim_candidates:
        if not c.claim_id:
            issues.append("a claim candidate has no claim_id")
        elif c.claim_id in seen_ids:
            issues.append(f"duplicate claim_id: {c.claim_id}")
        else:
            seen_ids.add(c.claim_id)
        if _looks_mojibake(c.text):
            issues.append(f"{c.claim_id}: claim text looks mojibake/undecoded")
        if c.axes.content_type not in CONTENT_CLAIM_TYPES:
            issues.append(f"{c.claim_id}: invalid content_type {c.axes.content_type!r}")
        if c.axes.evidence not in EPISTEMIC_EVIDENCE:
            issues.append(f"{c.claim_id}: invalid evidence {c.axes.evidence!r}")
        if c.axes.confidence not in CONFIDENCE_LEVELS:
            issues.append(f"{c.claim_id}: invalid confidence {c.axes.confidence!r}")

    status = "pass" if not issues else "fail"
    return ValidationResult(status=status, issues=issues)
