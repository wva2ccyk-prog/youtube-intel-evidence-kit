# Concept To Artifact Map

This map keeps the broad thesis tied to the small public package.

| Concept | Public Artifact |
|---|---|
| Knowledgeable operator judgment | `analysis_worth.json` review packet and `operator_review` authority label |
| Side remarks and marginal signals | `aside_type`, `aside_score`, and residual-value labels on claim candidates |
| Sparse or field-work-heavy domains | genre and claim context plus `human_field_review` escalation gate |
| Weak public evidence | `evidence`, `confidence`, weak claim IDs, and source trace entries |
| Advertising, hype, copied claims, and noisy information | `information_risks.promotional_or_hype_noise` and low-quality marker lists |
| Claims unsafe to treat as truth | source-verification gate and high-risk claim types |
| Main transcript is not enough | preserved time references, side-signal labels, and unresolved gaps |
| Expensive AI/human work should be justified | ASR, OCR/vision, source verification, strong model review, and human field review gates |

## Minimal Implementation Boundary

The public package implements only the small artifacts needed to demonstrate the doctrine:

- residual claim package assembly;
- deterministic aside and claim typing;
- analysis-worth review packet generation;
- synthetic public-safe smoke tests.

It intentionally does not ship broad scraping, monitoring, autonomous truth verification, external API calls, provider orchestration, or large multimodal pipelines.
