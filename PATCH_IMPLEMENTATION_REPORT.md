# Patch Implementation Report

Date: 2026-06-17

## Scope

This patch implements the review findings from the TopicCollection / opinion terrain pass. The public package is now framed and tested as a cross-video TopicCollection contract demo, not as a single-video summarizer or generic YouTube summary tool.

## Public-package changes

### Identity and documentation

- Renamed the README title to `YouTube Intel: Cross-Video Opinion Terrain Kit`.
- Strengthened the opening description: the project is a cross-video opinion terrain system, not a YouTube summarizer, transcript summarizer, chapter generator, or single-video Q&A tool.
- Reframed single-video residual packages as an input/cost-gate layer.
- Added public demo boundary language: `topic-demo` is a deterministic synthetic contract demo, not a production semantic clustering engine.
- Added `docs/REAL_ENGINE_ROADMAP.md` with minimum real-engine units: claim normalization, semantic grouping, stance clustering, conflict candidates, outlier typing, source diversity, cache, benchmark, and uncertainty.
- Downgraded MCP language to `MCP-ready handoff facade` / `MCP-style JSON-RPC stdio smoke`, not a full MCP-compliant server.

### TopicCollection implementation

Updated `src/youtube_intel/topic_collection.py` to add:

- structured evidence records;
- `evidence_coordinate` per claim;
- parsed numeric timestamps;
- speaker confidence;
- claim-level `verification_status`;
- claim-level `need_gates`;
- `evidence_index` in TopicCollection;
- explicit `grouping_method` metadata;
- group-level `member_claim_uids`, `representative_claim_uid`, `evidence_ids`, `evidence_coordinates`, `source_diversity`, `why_grouped`, `grouping_confidence`, and `human_review_required`;
- structured `disagreement_relations`;
- `outlier_details` and `outlier_type`;
- stronger Markdown terrain output with claim UID, video, timestamp, speaker, confidence, modality, and text;
- stronger AI handoff prompt rules.

### Manifest fix

Fixed the `topic_handoff_manifest.json` persistence bug. The manifest written to disk now includes the same topic, terrain, residual package paths, validation paths, and claim-group count returned by `topic-demo`.

### Schemas

Rewrote:

- `schemas/video_knowledge_record.schema.json`
- `schemas/topic_collection.schema.json`

The schemas now validate evidence records, evidence coordinates, need gates, verification status, grouping method, disagreement relations, and outlier details.

### CLI / MCP-style facade

- Added `topic-mcp-stdio --topic-collection` as a read-only TopicCollection handoff facade.
- Added `single-video-demo` and `single-video-handoff` aliases.
- Updated `doctor` to report the project identity and core demo command.

### Tests

Expanded `tests/test_topic_collection_contract.py` to cover:

- generated `TopicCollection` JSON Schema validation;
- generated `VideoKnowledgeRecord` JSON Schema validation;
- claim UID resolvability;
- evidence-coordinate completeness;
- manifest file/stdout equality;
- repeated/disagreement/outlier Markdown coordinate details;
- handoff prompt truth-collapse guards;
- TopicCollection MCP-style facade responses.

## Verification

Executed from the patched public package:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests -p no:cacheprovider
python scripts/public_release_leak_scan.py
python scripts/check_encoding.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m youtube_mcp_handoff.smoke
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m youtube_intel topic-demo --out /mnt/data/impl_out/public_topic_demo
```

Results:

```text
89 passed
LEAK SCAN PASSED: no violations found
Encoding check passed
Status: PASSED
manifest_file_equals_stdout: True
```

## Remaining boundary

This public package still intentionally uses a deterministic synthetic topic demo. It is now more honest about that boundary and provides a stricter contract for future real claim normalization, semantic grouping, stance clustering, conflict detection, OCR/ASR/diarization gates, storage, and MCP-compatible query layers.
