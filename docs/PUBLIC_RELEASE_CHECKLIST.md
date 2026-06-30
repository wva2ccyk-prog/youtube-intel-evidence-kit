# Public Release Checklist

Complete all items before making the repository public.

## Repository Setup

- [x] License chosen and LICENSE file present
- [ ] GitHub repo is public
- [ ] GitHub profile is public

## Code Quality

- [x] README updated with current status
- [x] pyproject.toml is valid
- [x] `python -m pytest -q tests` passes (all tests green)

## Safety and Privacy

- [x] Synthetic fixtures only — no real video data
- [x] No raw transcripts in the repo
- [x] No videos or screenshots
- [x] No private pilot outputs
- [x] No local paths (e.g., user home directories)
- [x] No credentials or API keys
- [x] No browser/session/cache artifacts
- [x] No generated analysis output from private runs

## MCP Handoff

- [x] MCP handoff docs included in `docs/mcp_handoff/`
- [x] `python -m youtube_mcp_handoff.smoke` passes
- [x] `python scripts/public_release_leak_scan.py` exits 0

## Application

- [x] Codex for OSS application draft updated
- [x] All synthetic demo topics use `synthetic_opinion_terrain_demo_v1`
