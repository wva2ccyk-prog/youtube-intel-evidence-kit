# Roadmap

This is the public-facing roadmap for youtube-intel-evidence-kit. The package is
an alpha cross-video evidence contract, and the roadmap keeps that boundary: it
structures video-internal claims for operator judgment and never decides truth.
The deeper engine plan lives in `docs/REAL_ENGINE_ROADMAP.md`; this file is the
short, public summary.

Status legend: `planned`, `exploring`, `done`.

An independent audit of this repository (run-verified, not doc-derived) is in
`docs/REVIEW_FINDINGS_2026_08.md`. The correctness items below come from it and
take priority over feature work.
Step-by-step remediation with verified diffs is in
`docs/REVIEW_FIX_GUIDE_2026_08.md`.

## Correctness first (blocking)

These are verified defects, not enhancements. See the audit for reproduction
steps.

- `planned` **Make demo fixtures install-safe.** `cli._repo_root()` assumes a
  source tree, so a wheel install resolves `examples/` to a path that does not
  exist. `topic-demo` then reports `ok: true` with zero claim groups, and
  `single-video-demo` exits with an unhandled traceback. Ship the fixtures as
  package data (or fail loudly when they are absent), and never return `ok: true`
  for an empty record set.
- `planned` **Fix the `doctor` posture report for installed packages.** In a
  wheel install `doctor` reports missing fixtures and missing `.gitignore`
  patterns as safety failures. Distinguish "repo checks not applicable" from
  "posture broken".
- `planned` **Reconcile the documented validation sequence with CI.** Running the
  README order (`pytest`, then `public_release_leak_scan.py`) fails with 43
  bytecode-cache violations, because only CI runs
  `scripts/clean_generated_artifacts.py` first. Document the clean step
  everywhere the scan is listed, or make the scan ignore bytecode caches.
- `planned` **Disclose the Korean grouping limitation.** Claim assembly is
  Korean-aware, but the grouping layer is not: particles are never separated and
  the `len(token) < 3` filter empties two-syllable Korean words, so Korean claim
  pairs score `0.0`–`0.19` and fall below the grouping threshold. Add this to
  `TOPIC_LIMITATIONS` so it appears in every handoff bundle, then make the length
  filter language-aware.
- `planned` **Stop short Korean markers from matching inside compounds.**
  `claim_axes._scan` matches the `medical_advice` marker `용량` inside `사용량`,
  so an irrigation or battery claim classifies as medical advice. Because
  `content_type` feeds `HIGH_VALUE_TYPES`, this changes analysis-worth cost-gate
  output, and it leaks into operator-visible group labels. The durable fix is to
  require two independent markers before assigning a high-risk `content_type`.

## Near term

- `done` Modernize packaging license metadata to SPDX.
- `planned` Add a worked end-to-end example that takes several synthetic
  single-video packets into one `TopicCollection` so the cross-video value is
  obvious from the README alone.
- `planned` Document the `VideoKnowledgeRecord` and `TopicCollection` field
  contracts in one schema reference page.
- `planned` Tighten the analysis-worth gate messaging so operators understand
  why a topic was or was not flagged as worth deeper analysis.
- `planned` Add an out-of-domain fixture (a topic unrelated to orchard sensors)
  plus a Korean fixture. The current `pair_agreement 0.875` score is measured on
  the same domain the hardcoded synonym table was written for, so it is a
  regression guard rather than evidence of generalization.
- `planned` Move the orchard synonym/expansion vocabulary out of module scope
  into a loadable per-topic resource, and label the current table in code as
  fixture scaffolding.
- `planned` Settle on one canonical project status string. Four documents
  currently state three different statuses for the same commit, and one of them
  ("pending public repo") is stale.
- `planned` Cut a `v0.1.0` tag or remove the dead compare/release links from
  `CHANGELOG.md`; neither the tag nor a GitHub release currently exists.
- `planned` Prune dead surfaces: the duplicated `youtube_ops_cli.py` (unreferenced
  by any entry point) and the plugin-registry entries pointing at private modules
  that do not exist in this repository.

## Medium term (real engine)

These replace the deterministic demo grouping layer. Full detail is in
`docs/REAL_ENGINE_ROADMAP.md`.

- `exploring` Claim normalization (`normalize_claim`) with deterministic rules
  before any embeddings. This must include particle-aware Korean tokenization;
  the current English-only suffix stripping is the root cause of the Korean
  grouping gap above.
- `exploring` Staged semantic grouping with recorded `why_grouped` and
  `grouping_confidence`.
- `exploring` Stance clustering across videos (supports, qualifies, rejects,
  alternative explanation, context only, unclear).
- `planned` Decide whether the quality gate (`youtube_quality.gate`) is a public
  surface. `docs/BOOTSTRAP_PROMPT.md` instructs agents to run it, but no CLI
  command exposes it and only tests import it.

## Explicitly out of scope

- Single-video summarization, chapter generation, or one-off Q&A as the product.
- Bundling downloaders or transcoders (`yt_dlp`, `ffmpeg`).
- Deciding which claim is true or which speaker is correct.
- Acquiring video or transcript content the operator has not lawfully admitted.

## How to influence the roadmap

Open a feature request issue describing the cross-video research question you
are trying to answer. Use cases that show scattered, multi-video evidence are
the best fit.
