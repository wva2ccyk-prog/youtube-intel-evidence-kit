from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from youtube_mcp_handoff.server import (
    get_mcp_tool_manifest,
    mcp_overlay_group_detail,
    mcp_overlay_groups,
    mcp_overlay_limitations,
    mcp_overlay_summary,
)


def _tool_schemas() -> list[dict[str, Any]]:
    manifest = get_mcp_tool_manifest()
    schemas: list[dict[str, Any]] = []
    for tool in manifest["tools"]:
        name = tool["name"]
        schema: dict[str, Any] = {
            "name": name,
            "description": f"Read-only synthetic overlay tool: {name}",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        }
        if name == "overlay.group_detail":
            schema["inputSchema"] = {
                "type": "object",
                "properties": {"overlay_group_id": {"type": "string"}},
                "required": ["overlay_group_id"],
                "additionalProperties": False,
            }
        schemas.append(schema)
    return schemas


def _content(data: Any) -> dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}
        ]
    }


def _call_tool(name: str, arguments: dict[str, Any], overlay_path: str | Path | None) -> dict[str, Any]:
    if name == "overlay.summary":
        return _content(mcp_overlay_summary(overlay_path))
    if name == "overlay.groups":
        return _content(mcp_overlay_groups(overlay_path))
    if name == "overlay.group_detail":
        group_id = str(arguments.get("overlay_group_id") or "")
        return _content(mcp_overlay_group_detail(group_id, overlay_path))
    if name == "overlay.limitations":
        return _content(mcp_overlay_limitations(overlay_path))
    raise ValueError(f"unknown tool: {name}")


def handle_jsonrpc_request(request: dict[str, Any], overlay_path: str | Path | None = None) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "youtube-intel-public-handoff", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            result = {"tools": _tool_schemas()}
        elif method == "tools/call":
            params = request.get("params") or {}
            result = _call_tool(str(params.get("name") or ""), params.get("arguments") or {}, overlay_path)
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:  # pragma: no cover - defensive boundary for stdio clients
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def run_stdio_server(overlay_path: str | Path | None = None) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        else:
            response = handle_jsonrpc_request(request, overlay_path=overlay_path)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
