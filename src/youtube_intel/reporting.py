from __future__ import annotations

from pathlib import Path
from typing import Any

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
    paths: dict[str, str] = {}

    if package:
        paths["residual_package_json"] = str(write_json(out / "residual_package.json", package))
    if worth:
        paths["analysis_worth_json"] = str(write_json(out / "analysis_worth.json", worth))
        paths["analysis_worth_md"] = str(write_text(out / "analysis_worth.md", render_analysis_worth_markdown(worth)))
        paths["operator_summary_md"] = str(write_text(out / "operator_summary.md", render_operator_summary(package, worth)))
        paths["ai_handoff_prompt_md"] = str(write_text(out / "ai_handoff_prompt.md", render_ai_handoff_prompt(package, worth)))
    if overlay:
        paths["operator_overlay_json"] = str(write_json(out / "operator_overlay.json", overlay))

    manifest = {
        "ok": True,
        "schema_version": "youtube_ai_handoff_bundle.v0.1",
        "limitations": PUBLIC_LIMITATIONS,
        "paths": paths,
    }
    paths["manifest_json"] = str(write_json(out / "handoff_manifest.json", manifest))
    manifest["paths"] = paths
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
