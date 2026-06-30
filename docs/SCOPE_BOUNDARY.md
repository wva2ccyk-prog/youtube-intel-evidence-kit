# Scope Boundary

This public candidate does not claim originality over common video-analysis ideas.

## Not Claimed As Original

- transcript summarization;
- caption parsing;
- generic YouTube analysis;
- video monitoring;
- channel scraping;
- retrieval over transcript chunks;
- OCR, ASR, or vision adapters;
- source-verification services;
- prompt bundles copied from other tools.

These are common/public patterns and are not the foreground contribution here.

## Original Public Contribution

The foreground contribution is the operational synthesis flow:

- cross-video opinion terrain over selected videos;
- `VideoKnowledgeRecord` as a reusable single-video input artifact;
- `TopicCollection` as the topic-level product artifact;
- repeated-claim, disagreement, and outlier mapping;
- source video, speaker, timestamp, evidence, and modality coordinates;
- analysis-worth doctrine as a cost gate before expensive analysis;
- side-signal, residual-value, noisy-information, and uncertainty labeling;
- AI handoff bundle with explicit limitations;
- explicit escalation gates for ASR, OCR, vision, source verification, strong model review, and human field review.

## Release Boundary

The public package should stay small. Broad monitoring, model routing, external-provider bridges, viewer surfaces, stores, plugins, benchmark corpora, and copied prompt systems belong outside the public foreground unless they are separately justified, licensed, and reviewed.

The public alpha ships no media-acquisition path: no YouTube downloader, no scraper, and no media-processing tooling in default discovery. It accepts synthetic fixtures and operator-provided evidence records only. Lawful transcript/caption acquisition is the operator's responsibility.

Status: `alpha_cross_video_evidence_contract_pending_public_repo`.

License: `MIT`.

Scope: synthetic-only public alpha package; no real video artifacts; no personal runtime data; no shipped media-acquisition path.
