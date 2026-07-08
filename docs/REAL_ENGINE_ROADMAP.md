# Real Cross-Video Engine Roadmap

The public `topic-demo` is a deterministic synthetic contract demo. It is intentionally small and public-safe. The production engine should replace the demo grouping layer with the following minimal units.

## 1. Claim normalization

Implement `normalize_claim(text)` that returns canonical text, detected numbers/units, negation markers, domain keywords, and uncertainty markers. Start with deterministic rules and domain synonym tables before adding embeddings.

**Landed (input-quality prerequisite):** opt-in claim assembly merges
punctuation-free caption cues into sentence-like units before extraction, so
`normalize_claim` operates on whole thoughts rather than mid-sentence fragments.
See [CLAIM_ASSEMBLY.md](CLAIM_ASSEMBLY.md) (`youtube_intel.sentence_assembly`,
`--claim-assembly sentence`). Default stays `cue`; promotion is a data-driven
operator decision.

## 2. Semantic grouping

Implement `group_claims(claims)` in stages:

1. exact canonical text match
2. token overlap / Jaccard grouping
3. optional local embedding grouping
4. low-confidence groups marked `human_review_required`

Every group must keep `why_grouped`, `grouping_method`, and `grouping_confidence`.

## 3. Stance clustering

Use a small stance set first:

- `supports`
- `qualifies`
- `rejects`
- `alternative_explanation`
- `context_only`
- `unclear`

Stance should be toward a canonical proposition, not just sentiment.

## 4. Conflict-candidate detection

Do not overclaim contradictions. Emit candidate relation objects such as:

- `support_vs_caution`
- `numeric_mismatch`
- `alternative_explanation`
- `framing_conflict`

Each relation should include claim UIDs, confidence, why flagged, and `human_review_required`.

## 5. Outlier detection

Separate outlier types:

- `single_source_outlier`
- `low_source_diversity_outlier`
- `semantic_outlier`
- `high_stakes_single_source`

Outliers are follow-up cues, not falsehood labels.

## 6. Speaker/source diversity

Track video count, speaker count, channel count, source role, speaker role, and incentive markers. Use these for terrain interpretation, not truth ranking.

## 7. Topic-level cache

Cache `VideoKnowledgeRecord` by video id, transcript hash, schema version, and builder version. Cache `TopicCollection` by topic id, input record hashes, and builder version.

## 8. Benchmark harness

Maintain synthetic public fixtures plus private sanitized fixtures. Expected outputs should include repeated groups, disagreement relations, outlier types, and known false positives.

## 9. Uncertainty scoring

Score transcript quality, speaker certainty, modality gaps, grouping confidence, source diversity, and external-verification need. This score should drive escalation, not final truth judgment.
