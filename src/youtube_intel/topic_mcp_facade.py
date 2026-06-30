from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_topic_collection(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def topic_summary(collection: dict[str, Any]) -> dict[str, Any]:
    terrain = collection.get("terrain") or {}
    return {
        "ok": True,
        "facade_type": "mcp_ready_read_only_topic_handoff_facade",
        "not_full_mcp_server": True,
        "topic": collection.get("topic") or {},
        "analysis_layer": collection.get("analysis_layer"),
        "video_record_count": collection.get("video_record_count", 0),
        "claim_total": collection.get("claim_total", 0),
        "claim_group_count": len(collection.get("claim_groups") or []),
        "terrain_counts": {
            "repeated_claim_groups": len(terrain.get("repeated_claim_group_ids") or []),
            "disagreement_groups": len(terrain.get("disagreement_group_ids") or []),
            "outlier_groups": len(terrain.get("outlier_group_ids") or []),
        },
        "truth_status": terrain.get("truth_status", "not_evaluated"),
        "fact_check_status": terrain.get("fact_check_status", "not_performed"),
        "limitations": collection.get("limitations") or [],
    }


def topic_claim_groups(collection: dict[str, Any]) -> dict[str, Any]:
    groups = []
    for group in collection.get("claim_groups") or []:
        if not isinstance(group, dict):
            continue
        groups.append({
            "group_id": group.get("group_id"),
            "label": group.get("label"),
            "claim_count": group.get("claim_count", 0),
            "video_ids": group.get("video_ids") or [],
            "status": group.get("status") or {},
            "source_diversity": group.get("source_diversity") or {},
            "grouping_confidence": group.get("grouping_confidence"),
            "human_review_required": group.get("human_review_required"),
        })
    return {"ok": True, "claim_group_count": len(groups), "groups": groups}


def topic_claim_group_detail(collection: dict[str, Any], group_id: str) -> dict[str, Any]:
    claim_index = collection.get("claim_index") or {}
    evidence_index = collection.get("evidence_index") or {}
    for group in collection.get("claim_groups") or []:
        if isinstance(group, dict) and group.get("group_id") == group_id:
            claims = []
            for uid in group.get("claim_uids") or []:
                claim = claim_index.get(uid)
                if isinstance(claim, dict):
                    claims.append({
                        "claim_uid": claim.get("claim_uid"),
                        "video_id": claim.get("source_video_id"),
                        "time_ref": claim.get("time_ref"),
                        "timestamp_start": claim.get("timestamp_start"),
                        "speaker": claim.get("speaker"),
                        "confidence": claim.get("confidence"),
                        "modality_sources": claim.get("modality_sources") or [],
                        "evidence_ids": claim.get("evidence_ids") or [],
                        "evidence_coordinate": claim.get("evidence_coordinate") or {},
                        "need_gates": claim.get("need_gates") or {},
                        "text": claim.get("text"),
                    })
            evidence = [evidence_index[eid] for eid in group.get("evidence_ids") or [] if eid in evidence_index]
            return {"ok": True, "group": group, "claims": claims, "evidence_records": evidence}
    return {"ok": False, "error": "claim_group_not_found", "group_id": group_id}


def topic_limitations(collection: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "limitations": collection.get("limitations") or [],
        "truth_status": (collection.get("terrain") or {}).get("truth_status", "not_evaluated"),
        "fact_check_status": (collection.get("terrain") or {}).get("fact_check_status", "not_performed"),
        "facade_wording": "MCP-ready handoff facade / MCP-style JSON-RPC stdio smoke, not a full MCP server",
    }


def tool_schemas() -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for name in ("topic.summary", "topic.claim_groups", "topic.claim_group_detail", "topic.limitations"):
        schema: dict[str, Any] = {
            "name": name,
            "description": f"Read-only TopicCollection handoff facade tool: {name}",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        }
        if name == "topic.claim_group_detail":
            schema["inputSchema"] = {
                "type": "object",
                "properties": {"group_id": {"type": "string"}},
                "required": ["group_id"],
                "additionalProperties": False,
            }
        schemas.append(schema)
    return schemas


def _content(data: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}


def _call_tool(collection: dict[str, Any], name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "topic.summary":
        return _content(topic_summary(collection))
    if name == "topic.claim_groups":
        return _content(topic_claim_groups(collection))
    if name == "topic.claim_group_detail":
        return _content(topic_claim_group_detail(collection, str(arguments.get("group_id") or "")))
    if name == "topic.limitations":
        return _content(topic_limitations(collection))
    raise ValueError(f"unknown tool: {name}")


def handle_jsonrpc_request(request: dict[str, Any], topic_collection_path: str | Path) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "youtube-intel-topic-handoff-facade", "version": "0.1.0"},
                "capabilities": {"tools": {}},
                "note": "MCP-ready handoff facade; not asserted as a full MCP-compliant server.",
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            result = {"tools": tool_schemas()}
        elif method == "tools/call":
            collection = load_topic_collection(topic_collection_path)
            params = request.get("params") or {}
            result = _call_tool(collection, str(params.get("name") or ""), params.get("arguments") or {})
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:  # pragma: no cover - stdio defensive boundary
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def run_stdio_server(topic_collection_path: str | Path) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        else:
            response = handle_jsonrpc_request(request, topic_collection_path=topic_collection_path)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
