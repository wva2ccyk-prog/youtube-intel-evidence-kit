# Why This Exists

## Repeated Pain

Video analysis usually fails in one of two directions. A fast transcript summary is cheap but loses the signal that a knowledgeable operator might care about, while a deep multimodal or source-verified review is expensive enough that it should not run on every video.

The recurring operational need is a middle layer:

- keep exact time references;
- separate what the video says from what an outside source says;
- mark uncertainty instead of smoothing it away;
- preserve side remarks, field hints, and marginal signals;
- identify advertising, hype, copied claims, and weak evidence;
- decide when deeper human or AI analysis is worth the cost;
- preserve reusable claims and review tasks.

## Why Existing Tools Are Not Enough

General transcript summarizers are useful for quick reading, and this project does not claim that idea as original. The gap is operational: fluent prose does not reliably preserve side signals, field context, evidence type, confidence, claim genre, noisy-information risk, or follow-up verification needs.

Retrieval over transcript chunks can help find snippets, and this project does not claim generic retrieval as original. Retrieval alone does not decide whether a video has residual value or whether a claim is high-risk enough to require source verification.

Full multimodal analysis can improve accuracy, but it is often the wrong first step. Many videos should be screened with compact evidence packets and deterministic gates before spending on ASR, OCR, vision, source search, stronger model review, or human field review.

## Design Choice

This kit starts with a selected-video residual-signal packet and treats every later capability as a gate:

- transcript or caption first;
- residual claim package second;
- side-signal and noisy-information labels third;
- analysis-worth review fourth;
- ASR, OCR, vision, source verification, strong model review, or human field review only when the package shows a real evidence gap.

The goal is not a prettier summary or a broader YouTube tool. The goal is an auditable package that helps an operator decide what is worth checking, escalating, saving, or ignoring when public written evidence is sparse or noisy.
