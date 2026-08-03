from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import InvalidInputError
from .io_utils import read_json, write_json, write_text


PUBLIC_LIMITATIONS = [
    "caption-first packet only",
    "video-internal claims are not verified facts",
    "not fact-checked",
    "not truth-ranked",
    "use expensive ASR/OCR/vision/source verification only when a gate justifies it",
]


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, default: str = "") -> str:
    return str(value if value not in (None, "") else default)


RESERVED_FALLBACK_IDS = {"unknown-video", "unknown-evidence", "unknown-claim", "unknown-group"}
PACKAGE_SCHEMA_VERSION = "youtube_residual_v0.1"
ANALYSIS_WORTH_SCHEMA_VERSION = "youtube_analysis_worth_v0.1"
VALID_ANALYSIS_WORTH_VALUES = {"yes", "no", "maybe"}


def validate_residual_package_dict(package: dict[str, Any]) -> list[str]:
    """Return structural issues for a residual package dictionary.

    A handoff bundle must not report success for an arbitrary object: the
    package must carry the expected schema version, a non-empty video identity,
    at least one claim candidate, and every claim must be an object with a
    non-empty claim id and text (duplicates rejected).
    """
    issues: list[str] = []
    if not isinstance(package, dict):
        return ["package_not_object"]
    if package.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        issues.append(
            f"package schema_version mismatch: expected {PACKAGE_SCHEMA_VERSION!r}, "
            f"got {_text(package.get('schema_version'), '<missing>')!r}"
        )
    video = package.get("video")
    if not isinstance(video, dict) or not video:
        issues.append("package.video is missing or empty")
    else:
        video_id = _text(video.get("video_id"))
        title = _text(video.get("title"))
        if not video_id:
            issues.append("package.video.video_id is empty")
        elif video_id in RESERVED_FALLBACK_IDS:
            issues.append(f"package.video.video_id uses reserved fallback id: {video_id!r}")
        if not title:
            issues.append("package.video.title is empty")
    claims = package.get("claim_candidates")
    if not isinstance(claims, list) or not claims:
        issues.append("package.claim_candidates is empty or not a list")
        return issues
    seen_ids: set[str] = set()
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            issues.append(f"package.claim_candidates[{i}] is not an object")
            continue
        cid = _text(claim.get("claim_id"))
        text = _text(claim.get("text"))
        if not cid:
            issues.append(f"package.claim_candidates[{i}] has empty claim_id")
        elif cid in seen_ids:
            issues.append(f"duplicate claim_id in package: {cid!r}")
        else:
            seen_ids.add(cid)
        if not text:
            issues.append(f"package.claim_candidates[{i}] has empty text")
    return issues


def validate_analysis_worth_dict(worth: dict[str, Any]) -> list[str]:
    """Return structural issues for an analysis-worth dictionary."""
    issues: list[str] = []
    if not isinstance(worth, dict):
        return ["analysis_worth_not_object"]
    if worth.get("schema_version") != ANALYSIS_WORTH_SCHEMA_VERSION:
        issues.append(
            f"analysis_worth schema_version mismatch: expected {ANALYSIS_WORTH_SCHEMA_VERSION!r}, "
            f"got {_text(worth.get('schema_version'), '<missing>')!r}"
        )
    video = worth.get("video")
    if not isinstance(video, dict) or not video:
        issues.append("analysis_worth.video is missing or empty")
    elif not _text(video.get("video_id")):
        issues.append("analysis_worth.video.video_id is empty")
    decision = worth.get("decision")
    if not isinstance(decision, dict) or not decision:
        issues.append("analysis_worth.decision is missing or empty")
    else:
        analysis_worth = decision.get("analysis_worth")
        if analysis_worth not in VALID_ANALYSIS_WORTH_VALUES:
            issues.append(f"analysis_worth.decision.analysis_worth invalid: {analysis_worth!r}")
        if not _text(decision.get("recommended_route")) and not _text(decision.get("max_cost_tier")):
            issues.append("analysis_worth.decision has neither recommended_route nor max_cost_tier")
    if not _as_list(worth.get("source_trace")):
        issues.append("analysis_worth.source_trace is empty (the contract requires a source trace)")
    return issues


def validate_handoff_inputs(
    package: dict[str, Any] | None = None,
    worth: dict[str, Any] | None = None,
    overlay: dict[str, Any] | None = None,
) -> list[str]:
    """Validate handoff artifacts and their mutual coherence.

    The complete handoff mode requires BOTH a structurally valid residual
    package and a structurally valid analysis-worth artifact whose video
    identity matches the package and whose source-trace claim ids resolve to
    package claims. Returns a list of issues (empty when coherent).
    """
    issues: list[str] = []
    package = package or {}
    worth = worth or {}
    if not package and not worth:
        return ["handoff requires a residual package and an analysis-worth artifact"]
    if not isinstance(package, dict):
        issues.append("package_not_object")
        package = {}
    if not isinstance(worth, dict):
        issues.append("analysis_worth_not_object")
        worth = {}
    if not package:
        issues.append("handoff requires a residual package (package-only/worth-only modes are not supported in the complete handoff contract)")
    else:
        package_issues = validate_residual_package_dict(package)
        if package_issues:
            issues.append("residual package is not structurally valid")
            issues.extend(f"package: {issue}" for issue in package_issues[:6])
    if not worth:
        issues.append("handoff requires an analysis-worth artifact (package-only/worth-only modes are not supported in the complete handoff contract)")
    else:
        worth_issues = validate_analysis_worth_dict(worth)
        if worth_issues:
            issues.append("analysis-worth artifact is not structurally valid")
            issues.extend(f"worth: {issue}" for issue in worth_issues[:6])
    # Coherence checks only when both dicts are present.
    if isinstance(package, dict) and isinstance(worth, dict) and package and worth:
        package_video = package.get("video") or {}
        worth_video = worth.get("video") or {}
        package_vid = _text(package_video.get("video_id"))
        worth_vid = _text(worth_video.get("video_id"))
        if package_vid and worth_vid and package_vid != worth_vid:
            issues.append(f"video_id mismatch between package ({package_vid!r}) and analysis-worth ({worth_vid!r})")
        package_title = _text(package_video.get("title"))
        worth_title = _text(worth_video.get("title"))
        if package_title and worth_title and package_title != worth_title:
            issues.append(
                f"title mismatch between package ({package_title!r}) and analysis-worth ({worth_title!r})"
            )
        package_ids = {
            _text(c.get("claim_id"))
            for c in _as_list(package.get("claim_candidates"))
            if isinstance(c, dict)
        }
        source_trace = _as_list(worth.get("source_trace"))
        for i, trace_item in enumerate(source_trace):
            if not isinstance(trace_item, dict):
                issues.append(
                    f"analysis_worth source_trace row {i} is not an object; "
                    f"malformed source-trace rows cannot bypass claim resolution"
                )
                continue
            cid = _text(trace_item.get("claim_id"))
            if not cid:
                issues.append(f"analysis_worth source_trace row {i} has an empty claim_id")
            elif cid not in package_ids:
                issues.append(f"analysis_worth source_trace claim_id does not resolve: {cid!r}")
    return issues


def _decision_label(worth: dict[str, Any]) -> str:
    decision = worth.get("decision") or {}
    return _text(decision.get("analysis_worth"), "unknown")


def _route_label(worth: dict[str, Any]) -> str:
    decision = worth.get("decision") or {}
    return _text(decision.get("recommended_route") or decision.get("max_cost_tier"), "unknown")


def render_analysis_worth_markdown(worth: dict[str, Any]) -> str:
    video = worth.get("video") or {}
    decision = worth.get("decision") or {}
    info_risks = decision.get("information_risks") or {}
    gates = worth.get("escalation_gates") or {}
    source_trace = _as_list(worth.get("source_trace"))

    lines: list[str] = []
    lines.append("# Analysis Worth")
    lines.append("")
    lines.append(f"Video: {_text(video.get('title'), 'unknown title')}")
    lines.append(f"Video ID: {_text(video.get('video_id'), 'unknown')}")
    lines.append(f"Decision: {_decision_label(worth)}")
    lines.append(f"Recommended route: {_route_label(worth)}")
    lines.append(f"Estimated next cost: {_text(decision.get('estimated_next_cost'), 'unknown')}")
    lines.append("")
    lines.append("## Why")
    why = _as_list(decision.get("why_analyze"))
    if why:
        lines.extend(f"- {item}" for item in why)
    else:
        lines.append("- no strong analysis-worth reason detected")
    lines.append("")
    lines.append("## Stop or Skip Reasons")
    stops = _as_list(decision.get("skip_or_stop_reasons"))
    if stops:
        lines.extend(f"- {item}" for item in stops)
    else:
        lines.append("- no hard stop reason detected")
    lines.append("")
    lines.append("## Information Risks")
    lines.append(f"- promotional_or_hype_noise: {bool(info_risks.get('promotional_or_hype_noise'))}")
    markers = _as_list(info_risks.get("promotional_markers"))
    if markers:
        lines.append(f"- promotional_markers: {', '.join(map(str, markers))}")
    lines.append(f"- low_quality_or_uncertain_web_claims: {bool(info_risks.get('low_quality_or_uncertain_web_claims'))}")
    low_markers = _as_list(info_risks.get("low_quality_markers"))
    if low_markers:
        lines.append(f"- low_quality_markers: {', '.join(map(str, low_markers))}")
    weak_claims = _as_list(info_risks.get("weak_claim_ids"))
    if weak_claims:
        lines.append(f"- weak_claim_ids: {', '.join(map(str, weak_claims))}")
    lines.append("")
    lines.append("## Escalation Gates")
    for name, rule in gates.items():
        lines.append(f"- {name}: {rule}")
    lines.append("")
    lines.append("## Source Trace")
    if source_trace:
        for item in source_trace:
            lines.append(
                f"- {_text(item.get('claim_id'), 'claim')}: "
                f"{_text(item.get('time_ref'), 'no time')} | "
                f"{_text(item.get('claim_type'), 'other')} | "
                f"{_text(item.get('evidence'), 'unclear')} | "
                f"{_text(item.get('confidence'), 'low')} | "
                f"{_text(item.get('excerpt'), '')}"
            )
    else:
        lines.append("- no source trace available")
    lines.append("")
    lines.append("## Required Limitations")
    for limitation in PUBLIC_LIMITATIONS:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def render_operator_summary(package: dict[str, Any], worth: dict[str, Any]) -> str:
    video = worth.get("video") or package.get("video") or {}
    decision = worth.get("decision") or {}
    lines = [
        "# Operator Summary",
        "",
        f"Video: {_text(video.get('title'), 'unknown title')}",
        f"Decision: {_decision_label(worth)}",
        f"Recommended route: {_route_label(worth)}",
        f"Estimated next cost: {_text(decision.get('estimated_next_cost'), 'unknown')}",
        "",
        "## What This Packet Is",
        "- Caption-first evidence and cost-gating packet.",
        "- It preserves claims, timestamps, uncertainty, residual side signals, and noisy-information markers.",
        "- It is not a generic YouTube summary and not a truth-verification result.",
        "",
        "## Recommended Next Actions",
    ]
    next_actions = _as_list(decision.get("recommended_next_actions"))
    if next_actions:
        lines.extend(f"- {item}" for item in next_actions)
    else:
        lines.append("- keep this as caption-first only unless the operator approves a bounded escalation")
    lines.extend([
        "",
        "## Stop Conditions",
        "- Stop if captions are missing or identity/title mismatch is detected.",
        "- Stop if high-risk claims lack caution labels or evidence anchors.",
        "- Stop if external verification is required but not approved.",
        "- Stop if the answer presents video-internal claims as verified facts.",
        "",
        "## Limitations",
    ])
    lines.extend(f"- {item}" for item in PUBLIC_LIMITATIONS)
    lines.append("")
    return "\n".join(lines)


def render_ai_handoff_prompt(package: dict[str, Any], worth: dict[str, Any]) -> str:
    video = worth.get("video") or package.get("video") or {}
    decision = worth.get("decision") or {}
    lines = [
        "# AI Handoff Prompt",
        "",
        "You are reviewing a caption-first YouTube evidence packet.",
        "Do not treat this packet as fact-checked, truth-ranked, or externally verified.",
        "Do not add outside facts unless the operator explicitly asks for a bounded source-verification step.",
        "First inspect the analysis-worth decision and source trace. Then decide whether ASR, OCR, vision, source verification, strong model review, or human field review is justified.",
        "",
        "## Packet Summary",
        f"- video_title: {_text(video.get('title'), 'unknown title')}",
        f"- video_id: {_text(video.get('video_id'), 'unknown')}",
        f"- analysis_worth: {_decision_label(worth)}",
        f"- recommended_route: {_route_label(worth)}",
        f"- estimated_next_cost: {_text(decision.get('estimated_next_cost'), 'unknown')}",
        "",
        "## Required Behavior",
        "- Preserve uncertainty and evidence labels.",
        "- Keep video-internal claims separate from external knowledge.",
        "- Show limitations in user-facing answers.",
        "- Escalate only when a specific evidence gap justifies cost.",
        "- Never call this fact-checked or truth-ranked.",
        "",
        "## Required Limitations To Display",
        "- synthetic fixture when using demo overlay",
        "- caption fragment claim risk",
        "- not truth-ranked",
        "- not fact-checked",
        "",
        "## Files To Inspect",
        "1. residual_package.json",
        "2. analysis_worth.json",
        "3. analysis_worth.md",
        "4. operator_summary.md",
        "",
        "## Suggested First Response Shape",
        "1. Decision summary",
        "2. Evidence worth preserving",
        "3. Risks and limitations",
        "4. Recommended next step",
        "5. What not to do",
        "",
    ]
    return "\n".join(lines)


def write_handoff_bundle(
    output_dir: str | Path,
    *,
    package: dict[str, Any] | None = None,
    worth: dict[str, Any] | None = None,
    overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = Path(output_dir)
    package = package or {}
    worth = worth or {}
    # Structural + coherence validation BEFORE anything is written.
    issues = validate_handoff_inputs(package=package, worth=worth, overlay=overlay)
    if issues:
        raise InvalidInputError(
            "handoff input validation failed: " + "; ".join(issues[:8])
            + (f" (+{len(issues) - 8} more)" if len(issues) > 8 else "")
        )
    paths: dict[str, str] = {}

    if package:
        paths["residual_package_json"] = str(write_json(out / "residual_package.json", package))
        paths["analysis_worth_json"] = str(write_json(out / "analysis_worth.json", worth))
    if worth:
        paths["analysis_worth_md"] = str(write_text(out / "analysis_worth.md", render_analysis_worth_markdown(worth)))
        paths["operator_summary_md"] = str(write_text(out / "operator_summary.md", render_operator_summary(package, worth)))
        paths["ai_handoff_prompt_md"] = str(write_text(out / "ai_handoff_prompt.md", render_ai_handoff_prompt(package, worth)))
    if overlay:
        paths["operator_overlay_json"] = str(write_json(out / "operator_overlay.json", overlay))

    # Build the complete manifest (including its own path) BEFORE writing it,
    # so the returned manifest and the on-disk manifest are identical.
    manifest_path = out / "handoff_manifest.json"
    paths["manifest_json"] = str(manifest_path)
    manifest = {
        "ok": True,
        "schema_version": "youtube_ai_handoff_bundle.v0.1",
        "bundle_completeness": "complete",
        "limitations": PUBLIC_LIMITATIONS,
        "paths": paths,
    }
    write_json(manifest_path, manifest)
    return manifest


def load_bundle_inputs(
    *,
    package_path: str | Path | None = None,
    analysis_worth_path: str | Path | None = None,
    overlay_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    package = read_json(Path(package_path), {}) if package_path else {}
    worth = read_json(Path(analysis_worth_path), {}) if analysis_worth_path else {}
    overlay = read_json(Path(overlay_path), {}) if overlay_path else {}
    return package or {}, worth or {}, overlay or {}
