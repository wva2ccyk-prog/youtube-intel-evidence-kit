from __future__ import annotations

import sys
from pathlib import Path

_src = str(Path(__file__).resolve().parents[1])
if _src not in sys.path:
    sys.path.insert(0, _src)

from youtube_mcp_handoff.overlay_service import load_operator_overlay, validate_overlay_for_public_demo
from youtube_mcp_handoff.server import (
    get_mcp_tool_manifest,
    mcp_overlay_group_detail,
    mcp_overlay_groups,
    mcp_overlay_limitations,
    mcp_overlay_summary,
)
from youtube_mcp_handoff.policy import FORBIDDEN_CAPABILITIES


def run_public_mcp_handoff_smoke_test(overlay_path: str | Path | None = None) -> dict:
    results: dict = {}
    errors: list[str] = []

    manifest = get_mcp_tool_manifest()
    results["manifest"] = {
        "schema_version": manifest["schema_version"],
        "status": manifest["status"],
        "tool_count": len(manifest["tools"]),
        "all_read_only": all(t.get("read_only") for t in manifest["tools"]),
    }

    if manifest["status"] != "PUBLIC_SYNTHETIC_DEMO_READY":
        errors.append(f"manifest_status:{manifest['status']}")
    if len(manifest["tools"]) != 4:
        errors.append(f"tool_count:{len(manifest['tools'])}")
    if not all(t.get("read_only") for t in manifest["tools"]):
        errors.append("not_all_tools_read_only")

    path = overlay_path or Path(__file__).resolve().parents[2] / "examples" / "synthetic_overlay_demo" / "operator_overlay.json"
    overlay = load_operator_overlay(path)
    validation_errors = validate_overlay_for_public_demo(overlay)
    results["overlay_validation"] = validation_errors

    summary = mcp_overlay_summary(overlay_path)
    results["mcp_overlay_summary"] = summary
    if summary.get("overlay_group_count") != 4:
        errors.append(f"summary_group_count:{summary.get('overlay_group_count')}")

    groups = mcp_overlay_groups(overlay_path)
    results["mcp_overlay_groups"] = groups
    if groups.get("overlay_group_count") != 4:
        errors.append(f"groups_count:{groups.get('overlay_group_count')}")

    limits = mcp_overlay_limitations(overlay_path)
    results["mcp_overlay_limitations"] = limits
    lims = limits.get("limitations", [])
    if "synthetic_fixture_only" not in lims:
        errors.append("missing_synthetic_fixture_only")
    if "caption_fragment_claim_risk" not in lims:
        errors.append("missing_caption_fragment_claim_risk")

    detail = mcp_overlay_group_detail("overlay_SYNTH_CG0001_access_and_scope", overlay_path)
    results["mcp_overlay_group_detail"] = detail

    not_found = mcp_overlay_group_detail("nonexistent_group", overlay_path)
    results["mcp_overlay_group_detail_not_found"] = not_found

    for cap in ("fact_check", "truth_judgment", "overlay_mutation"):
        if cap not in FORBIDDEN_CAPABILITIES:
            errors.append(f"forbidden_cap_missing:{cap}")

    results["errors"] = errors
    results["status"] = "PASSED" if not errors and not validation_errors else "FAILED"
    return results


if __name__ == "__main__":
    result = run_public_mcp_handoff_smoke_test()
    print(f"Status: {result['status']}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  ERROR: {e}")
    raise SystemExit(0 if result["status"] == "PASSED" else 1)
