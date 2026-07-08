# Hesitation Markers (Tier 1)

## Why this exists

The thesis ([PUBLIC_THESIS.md](PUBLIC_THESIS.md)) names paralinguistic residue
as real value: *"a hesitation that reveals uncertainty"* is listed alongside
asides and weak field signals as the kind of thing that matters to an operator
but is lost by ordinary summaries. Captions erase it — a transcript keeps the
words and drops the pauses, fillers, and restarts.

This module makes that signal a concrete, deterministic artifact: given
word-level timestamps for a claim's spoken span, it emits typed markers an
operator can act on.

## What Tier 1 does

`youtube_intel.hesitation_markers` is a pure, deterministic, stdlib-only core
(no audio, no ASR, no network in the module itself). It applies three rules to
a claim's word list:

- **mid-span pause** — an inter-word silence of at least `0.7 s` that is not at
  the span edges;
- **isolated filler** — a standalone Korean filler word (`어, 음, 그, 저기,
  뭐랄까, 그러니까, 뭐지, 아니`), counted only when the word equals the filler
  after stripping punctuation (never as a substring of a content word);
- **restart** — an identical adjacent word, or a strict prefix of the next word.

A claim with at least 4 words is labelled `hesitation_candidate` when it has any
pause, ≥2 fillers, or any restart; otherwise `no_hesitation_detected` (or
`insufficient_words`).

## What Tier 1 deliberately does NOT do

- **No confidence or truth score.** `hesitation_score` is `null` by design. A
  hesitation is a *listen-and-judge cue*, not a verdict — the operator must
  hear the span before drawing any conclusion. Every artifact carries this
  disclaimer verbatim, and is typed `modality_source: audio`,
  `evidence_state: operator_review_required`, `is_confidence_signal: false`.
- **No prosody.** Pitch and energy analysis (a possible Tier 2) is out of scope
  here; it would need an added dependency and, like the clusterer, a calibration
  experiment before it could be trusted or promoted.
- **No voice-based certainty judgement.** Inferring a speaker's confidence from
  their voice is deliberately refused — it is unreliable and would violate the
  project's "preserve uncertainty, do not manufacture it" stance.

## Where the word timestamps come from

Tier 1 analyses word timestamps; it does not produce them. In a real run those
come from a **need-gated local ASR pass** over an operator-selected claim span —
an escalation gate, exactly as [PUBLIC_THESIS.md](PUBLIC_THESIS.md) describes
(*"ASR only when captions are missing, suspect, or tone/audio evidence
matters"*). ASR is intentionally **not bundled** into this public package; it is
an operator-side gate you run only when a specific claim's tone/audio evidence
is worth the cost.

## Demo (synthetic, no audio required)

```bash
youtube-intel hesitation-demo --out outputs/hesitation
```

This runs the rules over `examples/synthetic_hesitation.json` (hand-authored
word timings that exercise each rule) and writes `hesitation_markers.json` and
`hesitation_markers.md`. It is a contract demo of the artifact shape, in the
same spirit as `topic-demo` and `single-video-demo`.

## Promotion criteria

Any move beyond Tier 1 (prosodic scoring, a real `hesitation_score`) must be
justified by a calibration experiment against operator-labelled examples, the
same discipline the clusterer options follow. Until then, markers stay
unscored, audio-typed, and operator-reviewed.
