# Limited Release Usage

This document describes how to use the youtube-intel MCP handoff layer in a limited release context.

## What's In Scope

- Synthetic overlay queries via the four MCP tools
- Answer guard validation for user-facing responses
- Opinion terrain inspection (not truth ranking)
- Caption-first analysis with need-gated escalation

## What's Out of Scope

- Real YouTube video analysis
- Truth ranking or fact checking
- Private pilot data or artifacts
- Raw transcript access
- Video/audio/OCR processing (unless explicitly escalated)

## Privacy and Safety

- No private data is included in the synthetic fixtures
- No real video IDs are referenced
- No credentials, tokens, or API keys are present
- All local paths are relative to the repository

## Running the Demo

```bash
# Run the smoke test
python -m youtube_mcp_handoff.smoke

# Run the leak scan
python scripts/public_release_leak_scan.py

# Run all tests
python -m pytest -q tests
```

## For AI Apps

AI apps such as Codex should:

1. Load the manifest to discover available tools
2. Call tools with read-only access only
3. Pass all answers through the answer guard
4. Include limitations in every user-facing response
5. Never claim truth-ranked or fact-checked status

See `docs/mcp_handoff/CODEX_USAGE.md` for detailed Codex integration guidance.
