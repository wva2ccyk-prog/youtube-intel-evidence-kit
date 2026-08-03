# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). For low-level
implementation notes, see `IMPLEMENTATION_CHANGELOG.md`.

## [Unreleased]

No unreleased changes.

## [0.1.0] - 2026-08-03

First public alpha release.

### Added

- Cross-video `VideoKnowledgeRecord` and `TopicCollection` evidence contracts.
- Deterministic opinion-terrain grouping, disagreement candidates, outliers,
  opinion groups, and evidence-coordinate preservation.
- Caption-first residual packaging, analysis-worth cost gates, and validated
  AI/MCP-ready handoff bundles.
- Source-checkout and installed-wheel runtime modes with packaged synthetic
  fixtures.
- Dependency-free runtime validation aligned with the published JSON Schema.
- Strict timestamp parsing and source/trace semantic-coherence checks.
- Fail-closed CLI errors with no partial output artifacts on invalid input.
- Optional Korean-aware sentence assembly and hesitation-marker surfacing.
- Python 3.10 and 3.12 CI plus clean-wheel installation and demo verification.

### Corrected before release

- Installed-package fixture discovery and doctor behavior.
- Empty-input success paths and malformed-input traceback leakage.
- Korean tokenization and ambiguous medical `용량` marker collisions.
- Fixture-specific aside-detector overfitting and broad single-marker Type 1
  classifications.
- TopicCollection relation, outlier, terrain, coordinate, and nullable
  schema/runtime parity.

### Boundaries

- Alpha heuristic tooling; not truth verification.
- Synthetic fixtures only; no media acquisition, scraping, or bundled real
  transcripts.
- No medical, financial, legal, investment, or political advice.

[Unreleased]: https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit/releases/tag/v0.1.0
