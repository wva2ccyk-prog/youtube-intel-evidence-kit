# AI App / MCP-Ready Handoff

This document describes the read-only handoff layer that gives AI apps such as Codex or GPT Pro a bounded view of synthetic operator overlays.

## Naming Boundary

The public package should be described as an **MCP-ready read-only handoff facade** unless it is wired into a full client/server MCP deployment. For local smoke testing, `youtube-intel mcp-stdio` provides a minimal JSON-RPC stdio server for the synthetic overlay tools.

## What The Handoff Provides

The handoff layer exposes four read-only tools:

| Tool | Description |
|------|-------------|
| `overlay.summary` | Returns topic metadata, group count, limitations, and policy |
| `overlay.groups` | Returns all overlay groups with axes and claim counts |
| `overlay.group_detail` | Returns full detail for a single overlay group |
| `overlay.limitations` | Returns the limitations and policy block |

## Design Principles

- **Caption-first analysis**: The system starts from captions/transcripts, not from video frames or audio.
- **Need-gated ASR/audio/video/OCR escalation**: Expensive modalities are only invoked when the caption-first pass identifies a gap that justifies the cost.
- **Opinion terrain, not summary-only output**: The goal is to map the landscape of claims, confidence levels, and side signals, not to produce a single smooth summary.
- **Not an ASR summarizer**: This is not a transcript summarization tool.
- **Not a fact-checker**: No truth judgments, no fact verification, no truth ranking.
- **Not a truth-ranking system**: Claims are typed and labeled, not ranked by truth value.
- **Read-only by default**: The handoff layer cannot mutate overlays, topic collections, or VKR state.
- **Limitations must be shown in user-facing answers**: Every answer includes the limitations block.

## Demo Topic

The public demo uses `synthetic_opinion_terrain_demo_v1` — a synthetic fixture that does not correspond to any real YouTube video or analysis output.

## Local Stdio Smoke

```bash
youtube-intel mcp-stdio
```

Supported JSON-RPC methods:

- `initialize`
- `tools/list`
- `tools/call`

This server is intentionally small and read-only. It exists to make the handoff behavior testable without adding external dependencies.

## Overlay Structure

Each overlay contains:

- `schema_version`: pinned to `public_synthetic_operator_overlay.v1`
- `topic_id`: the topic this overlay covers
- `overlay_groups`: 4 groups, each with a split axis, claim count, and status flags
- `limitations`: what this overlay does not provide
- `policy`: what mutations were not performed

## Answer Guards

Every user-facing answer is validated by an answer guard that:

- blocks forbidden phrases such as `fact checked`, `verified true`, and `truth-ranked result`;
- requires limitation disclosures such as `synthetic fixture`, `not truth-ranked`, and `not fact-checked`;
- supports a structured payload check so limitations are carried as data, not only prose.

## Limitations

- Synthetic fixture only — no real video data.
- Caption fragment claim risk — claims derived from captions may be incomplete or misleading.
- Not truth-ranked — no comparison to ground truth.
- Not fact-checked — no verification of claim accuracy.
