# Operator Loop

The operator loop is centered on topic terrain, not single-video summaries.

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

## 1. Monitor / Shortlist

The public package does not do broad monitoring. A separate low-cost lane should select candidate videos or a small topic set.

## 2. Single-Video Input Layer

For each selected video, build a residual package from admitted transcript/caption evidence. This preserves claim candidates, timestamps, speaker labels when available, confidence, evidence state, modality source, and side-signal labels.

## 3. Analysis-Worth Gate

`analysis-worth` decides whether a selected video deserves deeper processing. It is a gate, not the final product.

Escalation should be bounded:

- ASR only when captions are missing, suspect, or audio nuance matters.
- OCR/vision only when screen evidence matters.
- Source verification only for bounded high-value or high-risk claims.
- Strong model review only after a compact evidence package exists.

## 4. VideoKnowledgeRecord

A `VideoKnowledgeRecord` is the reusable single-video artifact that can enter a topic collection. It carries source video ID, local claim ID, timestamp, speaker, claim text, evidence labels, modality source, stance, support role, and topic grouping key.

## 5. TopicCollection

A `TopicCollection` groups claims across videos. It should show:

- repeated claim groups;
- disagreement points;
- outlier or single-source claims;
- position/stance groups;
- source coordinates for each claim;
- modality gaps that justify additional evidence work.

## 6. Cross-Video Opinion Terrain

The final operator-facing output is `topic_terrain.md` plus the JSON collection. It is not a truth decision. It is a map that helps the operator decide what to trust, what to inspect, and what to verify.

## Stop Conditions

Stop or downgrade the run when:

- video identity or title is inconsistent;
- captions are missing and no approved ASR path exists;
- high-risk claims lack evidence coordinates;
- a generated answer presents video-internal claims as verified facts;
- source verification is required but not approved;
- multimodal evidence is required but no bounded evidence task exists.
