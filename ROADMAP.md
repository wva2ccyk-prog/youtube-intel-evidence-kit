# Roadmap

This is the public-facing roadmap for youtube-intel-evidence-kit. The package is
an alpha cross-video evidence contract, and the roadmap keeps that boundary: it
structures video-internal claims for operator judgment and never decides truth.
The deeper engine plan lives in `docs/REAL_ENGINE_ROADMAP.md`; this file is the
short, public summary.

Status legend: `planned`, `exploring`, `done`.

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
