# Codex For OSS Application Draft

> Status: future-only draft. This package is a pre-publication alpha. It has no
> public repository, usage history, or maintenance evidence yet. Do not submit
> to Codex for OSS until a public repo exists with real commit/issue/PR/release
> evidence. License is MIT; package identity is `youtube-intel-evidence-kit`.

## Role Description

YouTube Intel Evidence Kit is a local-first, alpha open source candidate for cross-video opinion-terrain inspection: turning multiple operator-admitted, lawfully acquired video evidence records into reusable VideoKnowledgeRecord and TopicCollection artifacts that map repeated claims, disagreements, outliers, and evidence coordinates before expensive human or AI analysis. Single-video caption-first evidence packaging is only the input layer.

## Why This Repo Is Suitable

The project is a good fit for Codex because it has clear deterministic boundaries: cross-video grouping, claim typing, deterministic similarity grouping with a labeled fixture evaluation, validation, synthetic smoke tests, leakage checks, and doctrine documentation. Codex can help improve public documentation, tighten tests, review privacy boundaries, and keep the package scoped to the cross-video opinion-terrain thesis without requiring paid provider calls by default.

The repo is also safety-sensitive in a useful way. It explicitly separates video-internal claims from external truth verification and avoids public-readiness or advice claims unless a separate source-verification process has been run.

Key strengths for Codex collaboration:

- **Public-safe synthetic fixtures**: All demo data is synthetic. No real video IDs, transcripts, or analysis outputs are included.
- **Deterministic quality gates**: Quality gate, answer guard, and overlay validation are all deterministic — no paid APIs required.
- **Read-only MCP handoff**: The MCP layer exposes four read-only tools with a formal tool policy that forbids truth judgment, fact checking, and mutation.
- **Answer guards**: Every user-facing answer is validated for forbidden phrases and required limitation disclosures.
- **Leak-scan-first release workflow**: A dedicated leak scan script checks for private paths, credentials, and pilot artifacts before release.

## How API Credits Would Be Used

- Add and review deterministic tests for package validation, side-signal labeling, analysis-worth review packets, and high-risk claim labeling.
- Improve public documentation and examples while preserving the privacy boundary.
- Keep expensive-analysis escalation gates clear without foregrounding broad OCR, ASR, provider, monitor, or source-search tooling.
- Generate small synthetic fixtures and review them for leakage and overclaim risk.
- Run focused code review on public-release blockers.
- Review PRs for privacy boundary violations and safety regressions.
- Triage issues related to claim typing, aside signals, and escalation gates.
- Review release workflow and security/privacy boundary before each public release.

## 500-character repository fit answer

YouTube Intel Evidence Kit is an alpha, caption-first, evidence-first package for cross-video opinion-terrain inspection from operator-admitted video evidence. It has clear deterministic boundaries: claim typing, deterministic similarity grouping, quality gates, answer guards, and synthetic smoke tests. Codex can review PRs, tighten tests, triage issues, and verify privacy boundaries. The repo uses read-only MCP handoff with synthetic fixtures and a leak-scan-first release workflow.

## 500-character API credit usage answer

API credits would be used for: (1) PR review on public-release safety boundaries, (2) deterministic test additions for claim typing and quality gates, (3) issue triage on aside signals and escalation logic, (4) leak scan verification before each release, (5) documentation review for privacy and overclaim risk, (6) synthetic fixture generation and validation.

## Additional Note

The current staged package is not a public release yet. License (MIT) and package identity (`youtube-intel-evidence-kit`) are already selected. Before publication, the owner should run a strict leak scan on the final staged set and create the public repository. Codex-for-OSS submission remains future-only, pending public repository evidence (commits, issues, PRs, releases, and active maintenance).
