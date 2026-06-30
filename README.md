# YouTube Intel: Cross-Video Opinion Terrain Kit

youtube-intel is an alpha cross-video evidence contract for YouTube-heavy topics. It is not a production YouTube intelligence engine, YouTube summarizer, transcript summarizer, chapter generator, or single-video Q&A tool.

The final objective is cross-video opinion terrain synthesis: turning multiple lawfully acquired, operator-admitted video evidence records into reusable `VideoKnowledgeRecord` and `TopicCollection` artifacts that show repeated claims, disagreement points, outliers, source videos, speakers, timestamps, evidence coordinates, and modality gaps.

Single-video evidence packets are only the input layer. The system does not decide truth. It structures video-internal claims so the operator can judge whether source verification, ASR, OCR, vision, strong model review, or human field review is justified.

## Why This Exists

Generic single-video summaries are cheap. Built-in YouTube chat and general LLMs can often answer one-off questions. This package exists for the harder case: a topic where important information is scattered across multiple YouTube videos and is not well represented in text.

The intended pattern is closer to opinion-terrain mapping than summarization. The system should help an operator see which claims repeat, where speakers diverge, what is only said once, and which claims need better evidence before any expensive analysis is approved.

## Target User

- Researchers and analysts reviewing selected videos on a YouTube-heavy topic.
- Builders who want deterministic evidence packaging before using expensive AI or multimodal processing.
- Operators who know a domain well enough to decide which weak signals deserve follow-up.

This is not meant for broad scraping, channel-wide monitoring, public truth certification, legal compliance review, or medical/financial/investment/political advice.

## 5-Minute Quickstart

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
youtube-intel doctor
youtube-intel topic-demo --out outputs/topic_demo
youtube-intel topic-demo --out outputs/topic_demo_jaccard --clusterer token_jaccard --token-jaccard-threshold 0.45
```

Inspect the generated cross-video terrain files:

```text
outputs/topic_demo/
  packages/
  videos/
    synthetic-orchard-vendor-a_knowledge_record.json
    synthetic-orchard-field-b_knowledge_record.json
    synthetic-orchard-policy-c_knowledge_record.json
  topic_collection.json
  topic_terrain.md
  repeated_claims.md
  disagreements.md
  outliers.md
  topic_handoff_prompt.md
  topic_handoff_manifest.json
```

The older single-video demo is still available because it is the input layer:

```bash
youtube-intel single-video-demo --out outputs/demo
```

Run tests and public smoke checks:

```bash
python -m pytest -q tests
python -m youtube_mcp_handoff.smoke
python scripts/public_release_leak_scan.py
```

## Main Commands

| Command | Purpose |
|---|---|
| `youtube-intel doctor` | Check package posture, optional plugins, topic demo availability, and public-safety ignore rules |
| `youtube-intel topic-demo --out outputs/topic_demo` | Run synthetic cross-video `VideoKnowledgeRecord -> TopicCollection -> topic terrain` flow |
| `youtube-intel topic-demo --out outputs/topic_demo_jaccard --clusterer token_jaccard` | Run the same flow with the stricter deterministic token-overlap clusterer |
| `youtube-intel single-video-demo --out outputs/demo` | Run synthetic single-video residual package -> analysis-worth -> AI handoff flow |
| `youtube-intel package --segments examples/synthetic_segments.json --out outputs/pkg` | Build a residual package from admitted segment JSON |
| `youtube-intel worth --package outputs/pkg/residual_package.json --out outputs/worth` | Generate analysis-worth JSON and Markdown |
| `youtube-intel single-video-handoff --package ... --analysis-worth ... --out outputs/handoff` | Build AI CLI handoff files for a single-video input-layer evidence packet |
| `youtube-intel mcp-stdio` | Run the legacy read-only synthetic overlay MCP-style JSON-RPC stdio smoke server |
| `youtube-intel topic-mcp-stdio --topic-collection outputs/topic_demo/topic_collection.json` | Run the read-only TopicCollection MCP-ready JSON-RPC stdio handoff facade |
| `youtube-intel clean outputs/demo outputs/topic_demo` | Remove generated artifacts |

## Operator Loop

```text
monitor / shortlist
-> selected videos
-> single-video residual package
-> analysis-worth gate
-> VideoKnowledgeRecord
-> TopicCollection
-> cross-video opinion terrain
-> cache / query / MCP-ready handoff
```

`analysis-worth` is a gate, not the product. The product is a reusable cross-video `TopicCollection`.

See `docs/PURPOSE.md`, `docs/OPERATOR_LOOP.md`, and `docs/COST_ROUTING_MATRIX.md` for details.

## What It Does

- Builds residual claim packages from admitted, synthetic or operator-provided segment evidence.
- Converts single-video packages into reusable `VideoKnowledgeRecord` artifacts.
- Builds a public-safe `TopicCollection` with deterministic normalized-similarity grouping, optional token-Jaccard grouping, stance separation, opinion groups, contradiction candidates, and a small labeled fixture score.
- Preserves timestamps, speakers, evidence labels, modality labels, uncertainty, and residual side signals.
- Uses analysis-worth as a cost gate before expensive ASR, OCR, vision, source verification, strong model review, or human review.
- Generates Markdown handoff files that are easier for humans and AI CLI tools to inspect than raw JSON alone.
- Includes deterministic validation and synthetic smoke tests that do not require paid APIs.

## What It Does Not Do

- It does not replace the monitor/shortlist lane that selects candidate videos.
- It does not claim that a video statement is true.
- It does not turn side remarks into verified conclusions.
- It does not run blanket ASR, OCR, vision, scene, or speaker processing.
- It does not claim originality over transcript parsing, generic retrieval, or ordinary YouTube summarization.
- It does not make YouTube platform, copyright, legal, medical, financial, investment, or political decisions.

## Privacy And Safety Boundary

The public package should contain source code, synthetic examples, tests, schemas, and reduced documentation only. Do not commit raw transcripts, copyrighted transcripts, downloaded media, screenshots, private conversation exports, local databases, worker execution artifacts, or generated analysis output. Users are responsible for lawful transcript/caption acquisition and for respecting YouTube/platform terms, copyright, and local law. Synthetic fixtures are the public demo input.

High-risk claims should be treated as video-internal claims until a separate source-verification process is approved and run.


## YouTube / Transcript Boundary

This package does not ship real YouTube transcripts, copyrighted captions, downloaded video/audio, or media-derived artifacts. It also does not bundle any media-acquisition tooling: there is no downloader, scraper, or media-processing path in the public package. The public demo uses synthetic fixtures only, and the package otherwise accepts operator-provided evidence records as admitted input.

If an operator uses this package with real videos, the operator alone is responsible for lawful acquisition and use. Specifically, this package does not authorize and must not be used to:

- scrape YouTube or any platform;
- download YouTube video, audio, or other media;
- redistribute or republish transcripts, captions, or media;
- bypass, circumvent, or defeat any platform access control, rate limit, or technical protection measure.

Transcript or caption availability is not license clearance. The fact that text can be obtained does not grant any right to copy, store, redistribute, or analyze it. Operators must comply with YouTube/platform terms, copyright law, and local law, and obtain any required permissions before supplying real evidence to this package.


## AI App / MCP Handoff

This repository includes a public-safe, read-only AI app handoff layer with an MCP-ready shape. The default public package is a synthetic demo and should be described as a handoff facade unless you wire it into a full MCP client/server deployment.

The legacy synthetic overlay handoff layer exposes four read-only overlay tools:

- `overlay.summary`
- `overlay.groups`
- `overlay.group_detail`
- `overlay.limitations`

The TopicCollection handoff facade exposes read-only topic tools after `topic-demo` has generated a bundle:

- `topic.summary`
- `topic.claim_groups`
- `topic.claim_group_detail`
- `topic.limitations`

For local smoke testing, `youtube-intel mcp-stdio` runs a minimal overlay JSON-RPC stdio server. `youtube-intel topic-mcp-stdio --topic-collection outputs/topic_demo/topic_collection.json` runs a minimal TopicCollection JSON-RPC stdio facade. Both are intentionally read-only. They should be described as MCP-ready / MCP-style handoff facades, not full MCP-compliant servers.

## Current Status

Status: `alpha_cross_video_evidence_contract_with_deterministic_grouping_demo`.

License: `MIT`.

Scope: alpha public package with synthetic fixtures only; no real video artifacts, no shipped transcripts/media, and no private pilot data.

The deterministic core, CLI user flow, labeled synthetic topic demo, single-video handoff bundle, public leak scan, and smoke tests are present. This is still alpha positioning: real topic synthesis needs larger fixtures, semantic grouping upgrades, weighting, caching, benchmarks, and human review before stronger claims. Public release still requires owner review before publishing or submitting anywhere.

## License

MIT

## Public Demo Boundary

The public `topic-demo` is an alpha deterministic contract demo over synthetic fixtures. It now demonstrates local claim normalization, normalized lexical similarity grouping, optional token-Jaccard grouping, stance-derived opinion groups, contradiction candidates, pair-agreement evaluation, evidence coordinates, repeated claim groups, outliers, and AI/MCP-style handoff files. It is not a production semantic clustering engine. Real topic synthesis still needs optional embedding-based semantic grouping, stronger stance clustering, calibrated contradiction detection, source/speaker weighting, caching, broader benchmarks, and human review for uncertain groups.


