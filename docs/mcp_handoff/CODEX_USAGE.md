# Codex Usage

This document describes how Codex or another CLI-connected AI can interact with the YouTube Intel handoff layer.

## Fast Path

```bash
youtube-intel demo --out outputs/demo
```

Then give the AI these files first:

```text
outputs/demo/handoff/operator_summary.md
outputs/demo/handoff/analysis_worth.md
outputs/demo/handoff/ai_handoff_prompt.md
outputs/demo/handoff/residual_package.json
outputs/demo/handoff/analysis_worth.json
```

## Python Tool Access

```python
from youtube_mcp_handoff.server import (
    mcp_overlay_summary,
    mcp_overlay_groups,
    mcp_overlay_group_detail,
    mcp_overlay_limitations,
    get_mcp_tool_manifest,
)

manifest = get_mcp_tool_manifest()
summary = mcp_overlay_summary()
groups = mcp_overlay_groups()
detail = mcp_overlay_group_detail("overlay_SYNTH_CG0001_access_and_scope")
limitations = mcp_overlay_limitations()
```

## JSON-RPC Stdio Smoke

```bash
youtube-intel mcp-stdio
```

Example request line:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

## Tool Policy

All tools are read-only. The following capabilities are forbidden:

- Truth judgment
- Fact checking
- Truth ranking
- Conflict relation creation
- Topic collection mutation
- VKR mutation
- Overlay mutation
- Canonical pointer change

See `docs/mcp_handoff/MCP_TOOL_POLICY.md` for the full policy.

## Answer Presentation

When presenting results to the operator:

1. Include the limitations block from the overlay.
2. State that the data is a synthetic fixture.
3. Note the caption fragment claim risk.
4. Do not claim truth-ranked or fact-checked status.
5. Keep video-internal claims separate from external knowledge.

## Caption-First Approach

The system is caption-first: it starts from transcript/caption data and only escalates to ASR, audio, video, or OCR when the caption-first pass identifies a specific gap. This keeps costs low and avoids unnecessary modality switching.

## Limitations

- This is a synthetic demo, not a real YouTube analysis.
- Claims are derived from captions, which may be incomplete.
- No truth ranking or fact checking has been performed.
- All outputs should be treated as opinion terrain, not verified facts.
