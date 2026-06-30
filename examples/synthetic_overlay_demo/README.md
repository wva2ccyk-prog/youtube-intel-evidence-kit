# Synthetic Overlay Demo

This directory contains a **synthetic** operator overlay for the `synthetic_opinion_terrain_demo_v1` topic.

It is not a real YouTube analysis output. It exists to demonstrate the MCP handoff layer with deterministic, public-safe fixtures.

## Files

- `operator_overlay.json` — Synthetic overlay with 4 groups across opinion terrain axes
- `release_readiness_report.json` — Smoke test output proving the MCP handoff layer works

## Usage

```python
from youtube_mcp_handoff.server import mcp_overlay_summary, mcp_overlay_groups

summary = mcp_overlay_summary("examples/synthetic_overlay_demo/operator_overlay.json")
groups = mcp_overlay_groups("examples/synthetic_overlay_demo/operator_overlay.json")
```

## Regenerating the report

```bash
python -m youtube_mcp_handoff.smoke
```
