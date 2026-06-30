# Public Thesis

This project is not a normal YouTube summarizer.

The public thesis is that the remaining value of YouTube analysis is often not in single-video compression. It is in cross-video opinion terrain: preserving claims, disagreements, outliers, source coordinates, and weak field signals across several selected videos on a topic.

## Why This Is Not A Summarizer

A single video can often be handled by low-cost tools. The reason to build this system is that some topics are YouTube-heavy: local development, policy commentary, expert interviews, field reports, panels, and informal expert speech may not be written up elsewhere.

For those topics, the useful question is not only "what did this video say?" The useful question is:

> Across the videos, what claims repeat, where do speakers disagree, what is only said once, and what evidence coordinate supports each claim?

## Why The Operator Still Matters

AI can compress transcript text. It cannot reliably know which side remark matters to a specific operator, which field hint contradicts a glossy claim, or which local detail deserves a follow-up visit, source check, or expert review.

In sparse or field-work-heavy domains, the best evidence may not be written down. It may appear as:

- an aside from someone who has done the work;
- a hesitation that reveals uncertainty;
- a local condition that changes the interpretation;
- a quiet contradiction between a field report and a promotional claim;
- a weak signal that is not proof but is worth preserving.

## Artifact Contract

A public package should preserve:

- source video ID;
- timestamp or time reference;
- speaker;
- claim text;
- claim type;
- evidence state;
- confidence;
- modality source;
- side-signal or residual-value label;
- repeated/disagreement/outlier grouping;
- unresolved evidence gaps;
- explicit next escalation gate.

Model prose is not evidence by itself. The package is a way to structure operator judgment before paying for deeper ASR, OCR, vision, source verification, strong model review, or human field review.

## Escalation Doctrine

Deeper analysis is gated, not default:

- ASR only when captions are missing, suspect, or tone/audio evidence matters.
- OCR/vision only when the evidence gap is visual or screen-based.
- Source verification only for bounded high-value or high-risk claims.
- Human field review when the side signal depends on tacit experience or local context.
- Strong model review only after a compact evidence package exists.

The tool should help an operator decide what is worth checking, not pretend to replace the operator.

## Public Status

Status: `public_oss_candidate_with_synthetic_topic_collection_and_mcp_handoff`.

This is a synthetic-only public OSS candidate. It is not product-ready, not a production MCP deployment by itself, and not a truth-verification system.
