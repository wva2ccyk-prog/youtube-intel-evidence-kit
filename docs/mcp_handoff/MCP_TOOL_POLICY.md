# MCP Tool Policy

This document specifies the formal tool policy for the youtube-intel MCP handoff layer.

## Allowed Read-Only Tools

| Tool Name | Read-Only | Parameters |
|-----------|-----------|------------|
| `overlay.summary` | Yes | — |
| `overlay.groups` | Yes | — |
| `overlay.group_detail` | Yes | `overlay_group_id` |
| `overlay.limitations` | Yes | — |

## Forbidden Capabilities

The following capabilities are explicitly forbidden:

- `truth_judgment` — No truth/false determination
- `fact_check` — No fact verification
- `truth_ranking` — No ranking by truth value
- `conflict_relation_creation` — No conflict detection between claims
- `topic_collection_mutation` — No modification of topic collections
- `vkr_mutation` — No modification of VKR state
- `overlay_mutation` — No modification of overlays
- `canonical_pointer_change` — No modification of canonical pointers

## Required User-Facing Limitations

Every user-facing answer must include:

- "synthetic fixture only" — The data is synthetic, not from a real video
- "caption fragment claim risk" — Claims may be incomplete or misleading
- "not truth-ranked" — No comparison to ground truth
- "not fact-checked" — No verification of claim accuracy

## Validation

Tool requests are validated by `policy.validate_requested_tool()`. Capability requests are validated by `policy.validate_no_forbidden_capabilities()`. Answer text is validated by `answer_guard.validate_public_demo_answer()`.

## Source of Truth

The Python constants in `src/youtube_mcp_handoff/policy.py` are the source of truth for this policy. This document is a human-readable reference.
