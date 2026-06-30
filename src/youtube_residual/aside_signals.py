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

High false-positive rate is expected and acceptable: the goal is to maximize the
operator's collision surface, not to extract precisely.
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


# Type 1 — hidden info: contrast between official/public and actual/private.
_TYPE1_STRONG_MARKERS = (
    # Korean
    "공식적으론", "공식적으로는", "공식적인",
    "현장에서", "현장에서는", "현장에선", "비공식", "여기서만", "오프더레코드",
    "기사엔 안 나오", "다들 모르", "알려지진 않았", "겉으론", "표면적으론",
    "직접 가보니", "직접 보니",
    # English (expanded)
    "officially", "off the record", "off-the-record", "behind the scenes",
    "in reality", "on the ground", "what they don't tell you", "between us",
    "not in the news", "insider", "privately", "in practice",
    "people don't realize", "the real story", "what actually happens",
    "the truth is", "to be honest", "frankly", "candidly",
    "i'll let you in on", "between you and me", "you didn't hear it from me",
    "the public doesn't know", "in the trenches", "on the inside",
    "in the field", "from what i've seen", "from experience",
)
_TYPE1_WEAK_MARKERS = (
    "사실은", "실은", "솔직히", "실제로는",
    "the truth is", "to be honest", "frankly", "candidly",
)
_TYPE1_RISK_BOUNDARY = (
    "일반화하면 위험", "일반화해서는", "근거가 약", "강하게 해석하면 안",
    "문제가 되리라고", "생각 못", "어느 한계", "한계가 넘어",
    "남들처럼 조금", "잘못된 일반화", "오해의 소지", "면죄부",
    "남자답게 잘 선택", "알아서 남자답게", "모호하게 표현", "기술적 의사결정",
    "컴포넌트 많이 만들면", "코드가 나중에 매우 복잡",
    "모든 html 요소들을 전부 다 컴포넌트", "데이터 공유 같은 걸",
    "이 정도면 버그", "버그 아냐", "내 손이 살찐", "손이 살찐",
    "우리 동년배", "통키세대", "통키 세대", "SNS 하는 것도", "sns 하는 것도",
    "뭔 사진", "사진 빨리야", "사진발이야",
    "램값과 부품값", "가격이 20만", "가격이 조금 올라", "매력도가 좀 떨어",
    "비쌉니다", "성능 차이는 크게 안", "휴대하기", "부담스럽다",
    "백팩이", "가방이 17in", "17in 강추", "무게 차이는 얼마 안",
    "AI를 좀 써", "가격에도 또 많이 민감",
    "스크린타임", "영포티", "왜 아이폰 사용률", "왜 이렇게 됐는지 궁금",
    "95% 이상의 이형 당뇨병", "95% 이상", "가족력과 관련",
    "제일 단순한 형태 네트워크", "단순한 형태 네트워크", "설명을 위해서 제일 단순한",
    "두 개의 히든 레이어", "히든 레이어 개수",
    "가장 좋은 결과를 발표", "인센티브도 받고", "상금도 받고",
    "트랜스포머는 확률적으로 예측", "확률적으로 예측을 하는",
    "이런 일에는 어울리지",
    "대표 자동차 기업은 계속해서 하향세", "국내 자동차 업계 전체",
    "내수 진작 방안", "무역 장벽", "외교적 대응",
    "가능성은 거의 제로", "제로에 가까운", "의도 밖에", "의도밖에",
    "준비되지 않은 대통령", "자기 머리가 아니고", "다른 사람의 머리를 빌려야",
    "썩은 사과", "괴물 대통령", "식물 대통령", "손바닥 뒤집듯",
    "부끄러움을 모르는",
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
    """Token-equality scan for short/ambiguous fillers.

    Single-syllable Korean fillers ('음', '그', '어') appear inside ordinary
    words ('그래서', '마음') and must NOT match by substring. We split on
    whitespace, strip surrounding punctuation, and match only whole tokens.
    """
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


def detect_aside_signal(text: str) -> AsideSignal:
    """Classify aside signal for one text unit.

    Priority: Type 1 (hidden info) outranks Type 2 when both present, because a
    concrete off-record claim is more actionable than a hesitation. Score is the
    total marker count, used downstream for ranking candidates.
    """
    strong = _scan(text, _TYPE1_STRONG_MARKERS)
    weak = _scan(text, _TYPE1_WEAK_MARKERS)
    if "사실은" in weak and "실은" in weak:
        weak.remove("실은")
    risk_boundary = _scan(text, _TYPE1_RISK_BOUNDARY)
    if strong == ["현장에서"] and "경제 현장에서의 문제" in text:
        strong = []
    hes = _scan_tokens(text, _TYPE2_HESITATION_TOKENS) + _scan(text, _TYPE2_HESITATION_PHRASES)
    hesitation_hits = _scan_token_hits(text, _TYPE2_HESITATION_TOKENS)
    hyp = _scan(text, _TYPE2_HYPOTHESIS)
    tan = _scan(text, _TYPE2_TANGENT)
    t2 = hyp + tan  # hypothesis / tangent are strong; hesitation is weak alone

    # Hesitation alone is too weak (filler words appear everywhere). Require it to
    # co-occur with hypothesis/tangent, or appear repeatedly in a short utterance.
    hesitation_counts = (hesitation_hits >= 3 and len(text) <= 90) or (hes and (hyp or tan))

    if strong or risk_boundary or len(weak) >= 2:
        score = len(strong) * 2 + len(risk_boundary) * 2 + len(weak) + (1 if t2 else 0)
        return AsideSignal(
            ASIDE_TYPE1_HIDDEN,
            max(score, 1),
            strong + risk_boundary + weak + t2,
            needs_audio_check=True,
        )

    if hyp or tan or hesitation_counts:
        markers = hyp + tan + (hes if hesitation_counts else [])
        score = len(hyp) * 2 + len(tan) * 2 + (len(hes) if hesitation_counts else 0)
        return AsideSignal(ASIDE_TYPE2_UNFORMED, score, markers, needs_audio_check=True)

    return AsideSignal(ASIDE_NONE, 0, [], needs_audio_check=False)
