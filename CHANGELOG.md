# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it
leaves alpha. For low-level implementation notes see
`IMPLEMENTATION_CHANGELOG.md`.

## [Unreleased]

### Added
- Added stance-derived cross-video opinion groups to `TopicCollection` output.
  Opinion groups roll claim groups up into supporting, challenging,
  alternative, and reported position buckets without ranking truth.
- Added the deterministic `token_jaccard` clusterer option for `topic-demo` and
  the library API. It is local-only and requires no network, embeddings, or
  model downloads.

### Changed
- Modernized packaging license metadata to the SPDX `license = "MIT"` string
  plus `license-files`, removing the deprecated setuptools license table and
  the redundant license classifier.
- `topic-demo` now writes opinion-group ids and warnings into the terrain
  section and renders an `Opinion Groups` section in `topic_terrain.md`.

### Documentation
- Added this changelog, a public `ROADMAP.md` pointing at the cross-video engine
  plan, and GitHub issue/pull-request templates to make maintenance and
  contribution expectations explicit.
- Documented the `topic-demo --clusterer token_jaccard` path in `README.md`.

## [0.1.0] - 2026-06-30

### Added
- Initial public alpha release of the cross-video opinion-terrain evidence kit:
  `VideoKnowledgeRecord` and `TopicCollection` contracts, the deterministic
  `topic-demo`, the analysis-worth gate, and the read-only MCP handoff path.
- Installable CLI (`youtube-intel doctor`, `demo`, `package`, `worth`,
  `handoff`, `mcp-stdio`).
- GitHub Actions CI running the test suite on each push.

### Notes
- This is an alpha evidence contract, not a production YouTube intelligence
  engine or single-video summarizer. It does not bundle `yt_dlp` or `ffmpeg`
  and does not decide truth. See `docs/SCOPE_BOUNDARY.md`.

[Unreleased]: https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit/releases/tag/v0.1.0
