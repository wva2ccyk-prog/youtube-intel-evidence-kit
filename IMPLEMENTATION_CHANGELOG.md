# Implementation Changelog

## 2026-06-17 UX hardening pass

Implemented:

- Added installable CLI entry points in `pyproject.toml`.
- Added `youtube-intel doctor` for local posture checks.
- Added `youtube-intel demo` to generate a full synthetic package, analysis-worth output, and AI handoff bundle.
- Added `youtube-intel package`, `youtube-intel worth`, and `youtube-intel handoff` commands.
- Added `youtube-intel mcp-stdio` minimal read-only JSON-RPC stdio server for local handoff smoke testing.
- Added `analysis_worth.md`, `operator_summary.md`, and `ai_handoff_prompt.md` generation.
- Added Korean time-sensitive, promotional, and low-quality marker coverage to the public analysis-worth gate.
- Added explicit `recommended_route`, `estimated_next_cost`, and `recommended_next_actions` fields.
- Hardened optional plugin checks against missing parent modules.
- Hardened overlay validation and structured answer guard checks.
- Updated status/license/scope documents to one consistent public candidate state.
- Strengthened public `.gitignore` and release-scan posture.
- Added tests for CLI user flow, Korean markers, structured answer guard, overlay validation, and stdio tool listing.

Validated:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests -p no:cacheprovider
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m youtube_mcp_handoff.smoke
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python scripts/public_release_leak_scan.py
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python scripts/check_encoding.py
```

## 2026-06-17 Topic-terrain identity pass

Implemented:

- Recentered the public package around cross-video opinion terrain instead of single-video summarization.
- Added `docs/PURPOSE.md` with the final objective, layering, side-signal policy, and need-gated multimodal doctrine.
- Added synthetic `examples/topic_demo/` with three public-safe source-video fixtures.
- Added `schemas/video_knowledge_record.schema.json` and `schemas/topic_collection.schema.json` as public artifact contracts.
- Added `src/youtube_intel/topic_collection.py` with deterministic public-safe construction of:
  - `VideoKnowledgeRecord`
  - `TopicCollection`
  - repeated claim groups
  - disagreement groups
  - outlier groups
  - topic-level Markdown reports
- Added `youtube-intel topic-demo` to generate:
  - `videos/*_knowledge_record.json`
  - `topic_collection.json`
  - `topic_terrain.md`
  - `repeated_claims.md`
  - `disagreements.md`
  - `outliers.md`
  - `topic_handoff_prompt.md`
  - `topic_handoff_manifest.json`
- Updated `README.md`, `REVIEW_BRIEF_FOR_GPT_PRO.md`, `docs/PUBLIC_THESIS.md`, `docs/SCOPE_BOUNDARY.md`, `docs/OPERATOR_LOOP.md`, and `docs/COST_ROUTING_MATRIX.md` to state that analysis-worth is a gate, not the product.
- Updated `doctor` so the recommended next command is `youtube-intel topic-demo --out outputs/topic_demo`.
- Added topic-collection contract tests and CLI topic-demo tests.

Validated:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m youtube_mcp_handoff.smoke
python scripts/public_release_leak_scan.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m youtube_intel topic-demo --out /tmp/youtube_intel_topic_demo
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m youtube_intel demo --out /tmp/youtube_intel_single_demo
```
