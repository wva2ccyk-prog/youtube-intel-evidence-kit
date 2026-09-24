# Roadmap

This is the public-facing roadmap for youtube-intel-evidence-kit. The package is
an alpha cross-video evidence contract, and the roadmap keeps that boundary: it
structures video-internal claims for operator judgment and never decides truth.
The deeper engine plan lives in `docs/REAL_ENGINE_ROADMAP.md`; this file is the
short, public summary.

Status legend: `planned`, `exploring`, `done`.

## Milestone 1: terrain quality outside the demo domain (active)

v0.1.0 ships a sound artifact contract, but the grouping and stance rules are
tuned to the synthetic orchard fixture. On inputs it was not tuned for, the
terrain is empty or misleading: a Korean three-video topic yields nine
singleton groups with no repeated claims and no disagreements, an English topic
yields no disagreements, and greetings or subscribe requests become repeated
claims. The orchard demo also misses its own labeled threshold (0.625 against
0.75) while reporting `ok: true`.

Milestone 1 is complete when every target below passes. Each target is pinned
as an `xfail(strict=True)` test in `tests/test_milestone1_quality_targets.py`;
remove the marker in the change that makes it pass. Evaluation inputs live in
`tests/fixtures/eval_topics/`.

| Target | Test | Baseline (v0.1.0) |
|---|---|---|
| Orchard demo meets its labeled threshold (0.75) | `test_orchard_demo_meets_its_own_grouping_threshold` | 0.625 |
| Korean EV topic meets pair-agreement threshold (0.75) | `test_out_of_domain_grouping_meets_threshold[ko_ev_battery]` | 0.3 |
| English EV topic meets pair-agreement threshold (0.75) | `test_out_of_domain_grouping_meets_threshold[en_ev_battery]` | 0.5 |
| Labeled cross-video contradictions are flagged (Korean) | `test_cross_video_contradictions_are_flagged[ko_ev_battery]` | 0 of 3 |
| Labeled cross-video contradictions are flagged (English) | `test_cross_video_contradictions_are_flagged[en_ev_battery]` | 0 of 3 |
| Greetings and subscribe requests are never repeated claims | `test_filler_lines_are_not_repeated_claims` | fails |
| Grouping, stance, and need-gate rules carry no orchard vocabulary | `test_grouping_rules_carry_no_orchard_demo_vocabulary` | fails |
| A failed grouping evaluation appears in manifest `warnings` | `test_failed_grouping_evaluation_is_surfaced_in_manifest` | silent |

Work items, in order:

1. Surface a failed `grouping_evaluation` as a manifest warning instead of a
   silent `ok: true`.
2. Remove the orchard-specific synonym table, token boosts, group labels, and
   stance keywords from `topic_collection.py`.
3. Add language-aware claim normalization for the no-network path (Korean
   morpheme or stem matching so particles do not block matches).
4. Add an optional embedding-assisted clusterer (multilingual model, installed
   as an extra) behind the existing `--clusterer` switch, with no schema change.
5. Filter non-claim lines (greetings, calls to subscribe, filler) before
   grouping, and record what was filtered.
6. Replace keyword stance heuristics with pairwise cross-video comparison inside
   each group, so disagreements are found between videos rather than inferred
   from words like "but".

Ground rules: the contract tests keep passing, `cannot_link`-only
gains do not count (all-singleton output passes every `cannot_link` pair), and
label files are not edited to match engine output.

## Milestone 2: real input path (planned)

- `youtube-intel topic build` over VTT/SRT caption files or existing residual
  packages, instead of only `topic-demo` over hand-written segment JSON.
- Run the analysis-worth gate inside the topic flow.
- Expose `--claim-assembly sentence` in the topic flow.

## Milestone 3: output a reader can use (planned)

- Rank repeated claims and disagreements and show the top N with one or two
  representative claims per group; a 1,200-segment run currently writes a
  239 KB `topic_terrain.md`.
- Remove process notes from the public tree and plugin entries that point at
  modules the public package does not ship.

## Near term

- `done` Modernize packaging license metadata to SPDX.
- `planned` Add a worked end-to-end example that takes several synthetic
  single-video packets into one `TopicCollection` so the cross-video value is
  obvious from the README alone.
- `planned` Document the `VideoKnowledgeRecord` and `TopicCollection` field
  contracts in one schema reference page.
- `planned` Tighten the analysis-worth gate messaging so operators understand
  why a topic was or was not flagged as worth deeper analysis.

## Medium term (real engine)

These replace the deterministic demo grouping layer. Full detail is in
`docs/REAL_ENGINE_ROADMAP.md`.

- `exploring` Claim normalization (`normalize_claim`) with deterministic rules
  before any embeddings.
- `exploring` Staged semantic grouping with recorded `why_grouped` and
  `grouping_confidence`.
- `exploring` Stance clustering across videos (supports, qualifies, rejects,
  alternative explanation, context only, unclear).

## Explicitly out of scope

- Single-video summarization, chapter generation, or one-off Q&A as the product.
- Bundling downloaders or transcoders (`yt_dlp`, `ffmpeg`).
- Deciding which claim is true or which speaker is correct.
- Acquiring video or transcript content the operator has not lawfully admitted.

## How to influence the roadmap

Open a feature request issue describing the cross-video research question you
are trying to answer. Use cases that show scattered, multi-video evidence are
the best fit.
