from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PUBLIC_DISALLOWED_MARKERS = ["pilot_" + "runs", "C:\\Users\\", "@gmail." + "com"]
_REQUIRED_TOP_LEVEL_FIELDS = {
    "ok",
    "schema_version",
    "topic_id",
    "overlay_status",
    "overlay_group_count",
    "overlay_groups",
    "limitations",
    "policy",
}
_REQUIRED_GROUP_FIELDS = {
    "overlay_group_id",
    "source_group_id",
    "split_axis",
    "claim_count",
    "truth_status",
    "fact_check_status",
    "allowed_for_model_answer",
}
_REQUIRED_POLICY_FLAGS = {
    "truth_ranking_performed": False,
    "fact_check_performed": False,
    "source_artifact_mutated": False,
    "topic_collection_mutated": False,
    "vkr_mutated": False,
    "canonical_pointer_changed": False,
}


def load_operator_overlay(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def overlay_summary(overlay: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": overlay.get("ok", False),
        "schema_version": overlay.get("schema_version", ""),
        "topic_id": overlay.get("topic_id", ""),
        "overlay_status": overlay.get("overlay_status", ""),
        "overlay_group_count": overlay.get("overlay_group_count", 0),
        "limitations": overlay.get("limitations", []),
        "policy": overlay.get("policy", {}),
    }


def overlay_groups(overlay: dict[str, Any]) -> dict[str, Any]:
    groups = overlay.get("overlay_groups", [])
    if not isinstance(groups, list):
        groups = []
    normalized_groups: list[dict[str, Any]] = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        normalized_groups.append(
            {
                "overlay_group_id": g.get("overlay_group_id", ""),
                "source_group_id": g.get("source_group_id", ""),
                "split_axis": g.get("split_axis", ""),
                "claim_count": g.get("claim_count", 0),
                "truth_status": g.get("truth_status", ""),
                "fact_check_status": g.get("fact_check_status", ""),
                "allowed_for_model_answer": g.get("allowed_for_model_answer", False),
            }
        )
    return {"overlay_group_count": len(normalized_groups), "groups": normalized_groups}


def overlay_group_detail(overlay: dict[str, Any], overlay_group_id: str) -> dict[str, Any]:
    for g in overlay.get("overlay_groups", []):
        if isinstance(g, dict) and g.get("overlay_group_id") == overlay_group_id:
            return {"ok": True, "group": g}
    return {"ok": False, "error": "overlay_group_not_found", "overlay_group_id": overlay_group_id}


def overlay_limitations(overlay: dict[str, Any]) -> dict[str, Any]:
    return {"limitations": overlay.get("limitations", []), "policy": overlay.get("policy", {})}


def _append_missing_fields(errors: list[str], *, prefix: str, item: dict[str, Any], required: set[str]) -> None:
    for key in sorted(required):
        if key not in item:
            errors.append(f"missing_{prefix}_field:{key}")


def validate_overlay_for_public_demo(overlay: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(overlay, dict):
        return ["overlay_not_object"]

    _append_missing_fields(errors, prefix="top_level", item=overlay, required=_REQUIRED_TOP_LEVEL_FIELDS)

    groups = overlay.get("overlay_groups", [])
    if not isinstance(groups, list):
        errors.append("overlay_groups_not_list")
        groups = []
    group_count = overlay.get("overlay_group_count", 0)

    if group_count != len(groups):
        errors.append(f"overlay_group_count_mismatch: declared={group_count} actual={len(groups)}")
    if group_count != 4:
        errors.append(f"overlay_group_count_not_4: got {group_count}")

    seen_ids: set[str] = set()
    for idx, g in enumerate(groups):
        if not isinstance(g, dict):
            errors.append(f"overlay_group_not_object:{idx}")
            continue
        _append_missing_fields(errors, prefix="group", item=g, required=_REQUIRED_GROUP_FIELDS)
        gid = str(g.get("overlay_group_id", ""))
        if not gid:
            errors.append(f"empty_overlay_group_id:{idx}")
        elif gid in seen_ids:
            errors.append(f"duplicate_overlay_group_id:{gid}")
        else:
            seen_ids.add(gid)
        if g.get("truth_status") != "not_evaluated":
            errors.append(f"unexpected_truth_status:{gid}={g.get('truth_status')}")
        if g.get("fact_check_status") != "not_performed":
            errors.append(f"unexpected_fact_check_status:{gid}={g.get('fact_check_status')}")
        if "residual" in gid.lower() and g.get("allowed_for_model_answer") is True:
            errors.append(f"residual_group_allowed_for_model_answer:{gid}")

    limitations = overlay.get("limitations", [])
    if not isinstance(limitations, list):
        errors.append("limitations_not_list")
        limitations = []
    if "synthetic_fixture_only" not in limitations:
        errors.append("missing_limitation:synthetic_fixture_only")
    if "caption_fragment_claim_risk" not in limitations:
        errors.append("missing_limitation:caption_fragment_claim_risk")
    if "not fact-checked" not in limitations:
        errors.append("missing_limitation:not fact-checked")
    if "not truth-ranked" not in limitations:
        errors.append("missing_limitation:not truth-ranked")

    policy = overlay.get("policy", {})
    if not isinstance(policy, dict):
        errors.append("policy_not_object")
        policy = {}
    for key, expected in _REQUIRED_POLICY_FLAGS.items():
        if policy.get(key) is not expected:
            errors.append(f"unexpected_policy_flag:{key}={policy.get(key)}")

    overlay_json = json.dumps(overlay, ensure_ascii=False)
    for marker in _PUBLIC_DISALLOWED_MARKERS:
        if marker in overlay_json:
            errors.append(f"private_marker_in_overlay:{marker}")

    return errors
