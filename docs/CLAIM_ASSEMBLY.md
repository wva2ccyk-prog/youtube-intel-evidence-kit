# Claim Assembly (opt-in)

## Problem

Auto-generated captions for many languages — Korean especially — carry no
sentence punctuation and cut a line every few words. When the residual package
builder treats one caption cue as one claim candidate, the resulting
`claim_text` is a mid-sentence fragment. Fragment claims hurt three downstream
consumers:

- **operator review** — a reviewer cannot judge a claim they can only half-read;
- **claim grouping** — repeated-claim and disagreement detection compare
  fragments instead of propositions;
- **cross-video terrain** — clustering quality degrades on partial sentences.

This is the input-quality side of roadmap step 1 (Claim normalization) in
[REAL_ENGINE_ROADMAP.md](REAL_ENGINE_ROADMAP.md): before you can normalize or
group a claim, the claim text has to be a whole thought.

## Approach

`youtube_intel.sentence_assembly` merges *consecutive* transcript cues into
sentence-like units using deterministic, language-aware heuristics:

- a cue whose final token ends in a sentence-final ending (Korean `…다 / …요 /
  …죠 / …니다 / …습니까 / …네요 / …거든요 / …잖아요 / …입니다`) or in terminal
  punctuation (`. ? ! 。 ！ ？ …`) **closes** the current sentence;
- hard caps force a close so a unit never runs away: `max_chars` (~200) or
  `max_span_seconds` (~15s);
- otherwise the cue "ends mid-word" and joins forward into the next cue;
- a cue that is already sentence-final passes through as its own single unit.

**Traceability contract.** An assembled unit never invents text: its `text` is
exactly the whitespace-joined cue texts, and it records the cue indices / time
span it was built from. Every merged claim therefore still resolves to the real
cues (and thus their timestamps and evidence) it came from — the assembler adds
`source_time_refs` to each merged segment for exactly this reason. The module is
pure (stdlib only, no I/O) and deterministic.

## Usage (opt-in)

The default is unchanged. Assembly is off unless you ask for it.

```bash
# default: one claim candidate per caption cue (byte-identical to before)
youtube-intel package --segments examples/synthetic_segments.json --out outputs/pkg

# opt-in: merge cues into sentence units first
youtube-intel package --segments examples/synthetic_segments.json --out outputs/pkg \
  --claim-assembly sentence
```

Programmatically:

```python
from youtube_residual import build_residual_package

pkg = build_residual_package(
    video_id="v1", title="…", language="ko",
    segments=segments,
    claim_assembly="sentence",   # default is "cue"
)
```

The package records which mode built it: `to_dict()["claim_assembly"]` is
`"cue"` or `"sentence"`, so every artifact is self-describing.

## Illustration

A synthetic caption-fragment stream (no punctuation, mid-sentence cuts):

```
이 제도는 / 장기적으로 / 필요합니다 / 하지만 비용이 / 부담이죠
```

- `cue` mode → five fragment claims (`이 제도는`, `장기적으로`, …).
- `sentence` mode → two whole claims: `이 제도는 장기적으로 필요합니다` and
  `하지만 비용이 부담이죠`, each spanning the timestamps of the cues it merged.

## Promotion criteria

`cue` remains the default deliberately. Flipping the default to `sentence` is a
data-driven decision, not an aesthetic one, and should be made only after an
operator reviews a before/after comparison on representative material
(claim-count reduction, length distribution, fragment-flag ratio, and a
traceability spot-check that every assembled claim still resolves its evidence).
Because the package's processing/build version is a cache key, promoting the
default should also bump that version so previously cached packages are not
silently mixed with sentence-mode ones.
