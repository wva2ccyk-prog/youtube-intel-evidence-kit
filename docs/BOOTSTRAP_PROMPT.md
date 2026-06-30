# YouTube Intel Bootstrap Prompt

You are working in the public YouTube Intel Evidence Kit. This is not a generic YouTube summarizer. Treat it as a cross-video opinion-terrain workflow for selected videos. Single-video residual packages are input layers; TopicCollection is the target artifact.

## Runtime Rules

- Model output is not evidence.
- Keep evidence separated as transcript/caption, audio, visual/OCR, metadata, external source, inference, or unsupported.
- Start with caption-first analysis when captions or a transcript exist.
- Do not summarize from the title or description as if it were video content.
- Important claims must cite a timestamp, `segment_id`, or explicit evidence reference.
- High-risk genres such as health, finance, politics, law, investment, and local real estate require caution labels and cannot be written as direct advice.
- Keep video-internal claims, inference, and external knowledge separate.
- Run the quality gate before final report creation.
- Run analysis-worth or routing gate before expensive multimodal work, strong model review, ASR, OCR, or deep review.
- Do not stop at a single-video summary when the task is topic analysis. Build or inspect VideoKnowledgeRecord and TopicCollection artifacts.
- Optional plugins must never be required for the core path. Missing optional plugins should be reported as skipped or unavailable.
- Preserve uncertainty. Do not hide weak evidence behind polished prose.

## Minimal Output Contract

Return or save a structured result with:

- `one_line_summary`
- `timeline`
- `claim_map`
- `evidence_refs`
- `risk_and_uncertainty`
- `genre_specific_notes`
- `next_actions_or_codex_tasks`
- `quality_gate_status`
- `topic_collection_status` when the task spans multiple videos

Stop rather than improvise when captions are missing, evidence is unavailable, or a claim cannot be tied back to video-internal evidence.
