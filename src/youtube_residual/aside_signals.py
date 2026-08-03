"""Aside-signal detection — the novel core of the residual-value thesis.

Per the thesis: video's residual value in the LLM era is NOT the main content
(LLMs do that better) but the *aside* — what survives only in unpolished,
real-time speech. Two types:

- Type 1 (hidden info): off-the-record / field / insider remarks. Value = facts
  not written down anywhere. Markers: "officially X but actually...", "from what
  I've seen on the ground...".
- Type 2 (unformed thought): a half-baked idea that just sparked in one brain;
  often wrong, but a seed that can trigger the listener's own thinking. Markers:
  hesitation/self-correction, hypothesis framing, topic-departure-and-return.

This detector is deterministic and text-only. Tone/voice signals (a strong Type 2
cue) are NOT available here; the AsideSignal carries a `needs_audio_check` flag so
a later multimodal stage can confirm. The detector SURFACES candidates; it does
not judge whether the aside is correct or valuable (value lives in the receiver).

The default Type 1 detector uses portable linguistic evidence. Corpus- or
fixture-specific phrases can be supplied explicitly through a profile, but they
never influence default classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ASIDE_NONE = "none"
ASIDE_TYPE1_HIDDEN = "type1_hidden_info"
ASIDE_TYPE2_UNFORMED = "type2_unformed_thought"


@dataclass(slots=True)
class AsideSignal:
    """Result of scanning one text unit for aside signal."""

    aside_type: str
    score: int
    markers: list[str] = field(default_factory=list)
    needs_audio_check: bool = False

    @property
    def is_aside(self) -> bool:
        return self.aside_type != ASIDE_NONE

    def to_dict(self) -> dict:
        return {
            "aside_type": self.aside_type,
            "score": self.score,
            "markers": list(self.markers),
            "needs_audio_check": self.needs_audio_check,
        }


# Type 1 — hidden info. A single marker is sufficient only when it is an
# explicit private/disclosure signal or a direct field-observation phrase.
# Broader words such as "officially", "in reality", and "to be honest" must
# participate in a cross-category combination.
_TYPE1_EXPLICIT_PRIVATE = (
    "비공식", "여기서만", "오프더레코드", "기사엔 안 나오", "알려지진 않았",
    "off the record", "off-the-record", "what they don't tell you", "between us",
    "not in the news", "insider", "privately", "i'll let you in on",
    "between you and me", "you didn't hear it from me", "the public doesn't know",
    "on the inside",
)
_TYPE1_DIRECT_OBSERVATION = (
    "직접 가보니", "직접 보니",
    "from what i've seen on the ground", "from what i've seen in the field",
)
_TYPE1_PUBLIC_POSITION = (
    "공식적으론", "공식적으로는", "공식적인", "겉으론", "표면적으론",
    "officially", "official position", "publicly",
)
_TYPE1_REALITY_CONTEXT = (
    "현장에서", "현장에서는", "현장에선", "실제로는",
    "behind the scenes", "in reality", "on the ground", "in practice",
    "what actually happens", "the real story", "in the trenches", "in the field",
    "from what i've seen",
)
_TYPE1_DISCLOSURE_GAP = (
    "공개되지", "보고되지", "언급하지 않", "알리지 않", "기사에 없",
    "did not mention", "was not mentioned", "not reported", "not disclosed",
    "left out of", "omitted from",
)
_TYPE1_WEAK_HONESTY = (
    "사실은", "실은", "솔직히",
    "the truth is", "to be honest", "frankly", "candidly",
)

# Type 2 — unformed thought: hesitation, hypothesis, sudden tangent.
# Split hesitation into short single-token fillers (token-equality match only,
# to avoid matching inside ordinary words) and multi-word phrases (substring).
_TYPE2_HESITATION_TOKENS = (
    "음", "어", "이게", "저기",
    "uh", "um", "well", "erm",
)
_TYPE2_HESITATION_PHRASES = (
    "뭐랄까", "아 근데", "말하자면", "그러니까 뭐",
    "i mean", "sort of", "kind of", "how do i put it",
)
_TYPE2_HYPOTHESIS = (
    "문득", "갑자기 드는 생각", "생각해보니", "이런 거 아닐까",
    "그냥 생각인데", "개인적인 생각",
    "what if", "maybe", "just a thought", "it occurs to me", "i wonder",
    "off the top of my head", "hypothetically",
    "thinking out loud", "half-formed", "this might be wrong but",
    "could it be that", "i'm just spitballing", "spitballing",
    "playing devil's advocate", "loosely speaking", "rough idea",
    "i'm not sure but", "stab in the dark", "shot in the dark",
)
_TYPE2_TANGENT = (
    "딴 얘기지만", "여담이지만", "갑자기 생각났는데", "말 나온 김에",
    "본론으로", "이건 좀 다른 얘긴데",
    "by the way", "tangent", "off topic", "anyway", "back to",
    "this is unrelated but", "speaking of which",
    "side note", "while we're on the subject", "as an aside",
    "incidentally", "that reminds me", "before i forget",
    "to digress", "but i digress", "rambling",
)


def _scan(text: str, markers: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [m for m in markers if (m in text or m in lowered)]


def _scan_tokens(text: str, markers: tuple[str, ...]) -> list[str]:
    """Token-equality scan for short/ambiguous fillers."""
    import re as _re

    tokens = [_re.sub(r"^[\W_]+|[\W_]+$", "", tok).lower() for tok in text.split()]
    tokens = [t for t in tokens if t]
    token_set = set(tokens)
    return [m for m in markers if m.lower() in token_set]


def _scan_token_hits(text: str, markers: tuple[str, ...]) -> int:
    import re as _re

    tokens = [_re.sub(r"^[\W_]+|[\W_]+$", "", tok).lower() for tok in text.split()]
    tokens = [t for t in tokens if t]
    marker_set = {m.lower() for m in markers}
    return sum(1 for token in tokens if token in marker_set)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def detect_aside_signal(
    text: str,
    *,
    type1_profile_markers: tuple[str, ...] = (),
) -> AsideSignal:
    """Classify aside signal for one text unit.

    Type 1 outranks Type 2 when both are present. Default Type 1 decisions need
    one explicit/private or direct-observation marker, or a combination across
    public-position, field/reality, disclosure-gap, and honesty categories.
    Topic-specific profiles are opt-in and never affect the default detector.
    """
    explicit = _scan(text, _TYPE1_EXPLICIT_PRIVATE)
    direct = _scan(text, _TYPE1_DIRECT_OBSERVATION)
    public = _scan(text, _TYPE1_PUBLIC_POSITION)
    reality = _scan(text, _TYPE1_REALITY_CONTEXT)
    gap = _scan(text, _TYPE1_DISCLOSURE_GAP)
    weak = _scan(text, _TYPE1_WEAK_HONESTY)
    if "사실은" in weak and "실은" in weak:
        weak.remove("실은")
    profile = _scan(text, type1_profile_markers)

    hes = _scan_tokens(text, _TYPE2_HESITATION_TOKENS) + _scan(text, _TYPE2_HESITATION_PHRASES)
    hesitation_hits = _scan_token_hits(text, _TYPE2_HESITATION_TOKENS)
    hyp = _scan(text, _TYPE2_HYPOTHESIS)
    tan = _scan(text, _TYPE2_TANGENT)
    t2 = hyp + tan

    hesitation_counts = (hesitation_hits >= 3 and len(text) <= 90) or (hes and (hyp or tan))
    structural = bool(
        (public and reality)
        or (reality and gap)
        or (reality and weak)
        or len(reality) >= 2
    )

    if explicit or direct or profile or structural:
        markers = _dedupe(explicit + direct + profile + public + reality + gap + weak + t2)
        score = (
            len(explicit) * 3
            + len(direct) * 3
            + len(profile) * 2
            + len(public) * 2
            + len(reality) * 2
            + len(gap) * 2
            + len(weak)
            + (1 if t2 else 0)
        )
        return AsideSignal(
            ASIDE_TYPE1_HIDDEN,
            max(score, 1),
            markers,
            needs_audio_check=True,
        )

    if hyp or tan or hesitation_counts:
        markers = _dedupe(hyp + tan + (hes if hesitation_counts else []))
        score = len(hyp) * 2 + len(tan) * 2 + (len(hes) if hesitation_counts else 0)
        return AsideSignal(ASIDE_TYPE2_UNFORMED, score, markers, needs_audio_check=True)

    return AsideSignal(ASIDE_NONE, 0, [], needs_audio_check=False)
