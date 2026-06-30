# Packaging Closeout

Candidate: `youtube-intel-evidence-kit`

Status: `alpha_cross_video_evidence_contract_pending_public_repo`

License: `MIT`

Scope: synthetic-only public alpha package; no real video artifacts; no personal runtime data; no shipped media-acquisition path.

## Files Changed In The Topic-Terrain Pass

- `README.md`
- `REVIEW_BRIEF_FOR_GPT_PRO.md`
- `docs/PURPOSE.md`
- `docs/OPERATOR_LOOP.md`
- `docs/COST_ROUTING_MATRIX.md`
- `docs/SCOPE_BOUNDARY.md`
- `docs/PUBLIC_THESIS.md`
- `examples/topic_demo/`
- `schemas/video_knowledge_record.schema.json`
- `schemas/topic_collection.schema.json`
- `src/youtube_intel/cli.py`
- `src/youtube_intel/topic_collection.py`
- `tests/test_cli_user_flow.py`
- `tests/test_topic_collection_contract.py`

## Thesis

The package foregrounds:

- cross-video opinion terrain, not generic summarization;
- `VideoKnowledgeRecord` as the reusable single-video input artifact;
- `TopicCollection` as the main product artifact;
- repeated-claim, disagreement, and outlier mapping across videos;
- source video, speaker, timestamp, evidence, and modality coordinates;
- caption-first evidence packaging as an input layer;
- analysis-worth as a cost gate, not the product;
- explicit cost routing before expensive ASR/OCR/vision/source verification/strong model review;
- AI CLI handoff files that make limitations visible.

## Concept To Artifact Mapping

- selected video evidence -> residual package;
- reusable single-video input -> `VideoKnowledgeRecord`;
- topic-level terrain -> `TopicCollection`;
- repeated claims -> `repeated_claims.md` and collection group status;
- disagreement points -> `disagreements.md` and collection group status;
- outliers -> `outliers.md` and collection group status;
- source coordinates -> claim UID, video ID, speaker, timestamp, modality source;
- expensive investigation -> gated ASR, OCR/vision, source verification, strong model review, or human field review;
- AI review -> `topic_handoff_prompt.md` and `topic_handoff_manifest.json`.

## Validation Commands

Run before any public push:

```bash
python -m pytest -q tests
python -m youtube_mcp_handoff.smoke
python scripts/public_release_leak_scan.py
python -m youtube_intel topic-demo --out outputs/topic_demo
python -m youtube_intel demo --out outputs/demo
```

## Remaining Boundary

This package is an alpha public OSS candidate, not a promise of production readiness. It ships synthetic fixtures and accepts operator-provided knowledge records only; it does not bundle a YouTube media download or media-processing acquisition path. Lawful transcript/caption acquisition is the operator's responsibility. Owner review and a public repository with maintenance evidence are still required before any Codex-for-OSS submission. Owner review is still required before publishing, submitting, or attaching real transcripts.
