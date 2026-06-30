# Purpose

youtube-intel is not a YouTube summarizer.

The final objective is cross-video opinion terrain synthesis: turning multiple YouTube videos on a topic into reusable VideoKnowledgeRecords and TopicCollections that show repeated claims, disagreement points, outliers, source videos, speakers, timestamps, evidence coordinates, and modality gaps.

Single-video residual packages and analysis-worth decisions are input layers. They decide whether a selected video deserves deeper processing and prepare evidence for reuse. They are not the final product.

## Why This Exists

A single YouTube video can often be handled by low-cost tools or built-in video chat. Building a CLI-connected analysis system is justified only when the valuable information is distributed across multiple videos and is not well represented in text.

The target use case is a topic where YouTube speech carries information that is hard to replace with ordinary web text: field reports, local development commentary, expert interviews, policy panels, academic discussions, and informal claims that have not been written up elsewhere.

## Core Product

The core product is a TopicCollection.

A TopicCollection should answer:

- What position groups appear across the videos?
- Which claims repeat across videos?
- Where do the videos disagree?
- Which claims are outliers or single-source claims?
- Which speaker, video, timestamp, and evidence coordinate supports each claim?
- Which evidence gaps justify source verification, ASR, OCR, vision, speaker checks, or human review?

The system does not decide truth. It structures video-internal claims so the operator can judge.

## Layering

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

## Side Signals

Asides, residual claims, hidden field notes, and unformed thoughts are preserved as a skim layer. They are useful because video often contains informal speech that is lost in normal summaries. They are not promoted to truth claims.

## Multimodal Policy

ASR, OCR, vision, scene detection, speaker checks, and tone cues are need-gated. They should run only when a specific claim or conflict requires them. Multimodal processing is an accuracy reinforcement path, not a blanket default.

## Evaluation Standard

Do not evaluate this package as a generic transcript summarizer. Evaluate whether it can move toward this outcome:

> Users can reduce source-video watching time while still seeing the opinion terrain, repeated claims, conflicts, outliers, and evidence coordinates for a YouTube-heavy topic.

## Public Demo Boundary

The public `topic-demo` is a deterministic synthetic contract demo. It demonstrates the desired artifact shape: `VideoKnowledgeRecord`, `TopicCollection`, repeated claim groups, disagreement candidates, outliers, evidence coordinates, and AI handoff files.

It is not yet the production semantic grouping engine. Real topic synthesis requires claim normalization, semantic grouping, stance clustering, contradiction-candidate detection, source/speaker diversity scoring, uncertainty scoring, cache, benchmark harness, and human review for low-confidence groups.

## Evidence Coordinate Contract

Every substantive claim should preserve enough coordinates for later query or handoff:

- `claim_uid`
- `source_video_id`
- `speaker`
- `time_ref`
- numeric `timestamp_start` when parseable
- `modality_sources`
- `evidence_ids`
- `evidence_coordinate`
- `verification_status`
- `need_gates`

Repeated claims remain terrain signals. They are not proof. Disagreement relations are candidates for review. They are not final truth judgments.
