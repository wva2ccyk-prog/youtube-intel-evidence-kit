"""Main summary preservation.

Operator's explicit requirement: "곁가지 한다고 중심요약을 날려버리면 안 된다."
The system surfaces asides as the residual value, but the main content still
needs to be summarized — both because the central content has its own value
and because the aside is only meaningful relative to it.

This module produces a deterministic "main summary scaffold" from the package:
- one_line_summary placeholder (filled by a cheap-model later; deterministic
  fallback uses the longest non-aside main claim)
- timeline (one entry per source segment, as currently grouped)
- key_information rows extracted from main (non-aside) claims
- genre-required sections as empty-but-named placeholders

The cheap-model upgrade replaces the deterministic fillers but keeps the
structure and the genre-required section list. This lets the system run
end-to-end before any model is wired and gives downstream stages a stable
contract.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .extractor import ClaimCandidate
from .genres import GenreDetection


_ONE_LINE_LIMIT = 180
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_NOISE_MARKERS = ("[음악]", "[music]", "[applause]", ">>", "...", "…")
_LOW_SIGNAL_PHRASES = (
    "소개해 주시죠",
    "자 그렇다면",
    "계속하겠습니다",
    "오늘의 분석 키워드",
    "어떻게 보셨습니까",
    "궁금하다면 끝까지",
)
_WEAK_STARTS = (
    "왜냐하면",
    "근데",
    "그런데",
    "하지만",
    "그래가지고",
    "자 ",
    "어 ",
    "음 ",
    "네 ",
    "이게 ",
    "그니까",
)
_WEAK_ENDINGS = ("때문에", "그리고", "그래서", "하지만", "하는데", "있고", "다")
_PREFERRED_TYPES_BY_GENRE = {
    "health_medical": {"medical_advice", "health_claim"},
    "finance_economy": {"economic_forecast", "investment_opinion", "political_claim", "technical_explanation"},
    "news_politics": {"political_claim", "economic_forecast"},
    "development_tutorial": {"tutorial_step", "technical_explanation", "concept_definition"},
    "it_ai_concept": {"technical_explanation", "concept_definition"},
    "product_review": {"product_recommendation", "personal_experience"},
}
_DEMOTED_TYPES_BY_GENRE = {
    "health_medical": {"personal_experience"},
    "finance_economy": {"personal_experience"},
    "news_politics": {"personal_experience"},
    "development_tutorial": {"personal_experience"},
    "it_ai_concept": {"personal_experience", "product_recommendation"},
}
_GENRE_KEYWORDS = {
    "health_medical": ("혈압", "혈당", "당뇨", "복용", "생활습관", "고혈압", "건강"),
    "finance_economy": ("경제", "금리", "투자", "경기", "시장", "기업", "고용", "AI", "인공지능"),
    "news_politics": ("경제", "정책", "정부", "대통령", "후보", "토론", "특검", "법안", "선거", "자동차", "보호막"),
    "development_tutorial": ("코드", "설치", "파일", "컴포넌트", "next", "supabase", "라우팅"),
    "it_ai_concept": ("AI", "인공지능", "챗", "채피", "딥러닝", "머신러닝", "신경망", "트랜스포머", "모델"),
    "product_review": ("추천", "비교", "가격", "구매", "갤럭시", "아이폰", "노트북", "그램"),
}


@dataclass(slots=True)
class TimelineEntry:
    time_ref: str | None
    speaker: str | None
    text: str
    main_claim_ids: list[str] = field(default_factory=list)
    aside_claim_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KeyInformationRow:
    info_id: str
    label: str
    content: str
    time_ref: str | None
    source_claim_id: str
    confidence: str


@dataclass(slots=True)
class MainSummary:
    one_line: str
    timeline: list[TimelineEntry] = field(default_factory=list)
    key_information: list[KeyInformationRow] = field(default_factory=list)
    genre_required_sections: dict[str, str] = field(default_factory=dict)
    main_claim_count: int = 0
    aside_claim_count: int = 0

    def to_dict(self) -> dict:
        return {
            "one_line": self.one_line,
            "timeline": [asdict(e) for e in self.timeline],
            "key_information": [asdict(r) for r in self.key_information],
            "genre_required_sections": dict(self.genre_required_sections),
            "main_claim_count": self.main_claim_count,
            "aside_claim_count": self.aside_claim_count,
        }


def _clip_one_line(text: str) -> str:
    text = " ".join(str(text or "").split())
    return text[:_ONE_LINE_LIMIT] + ("…" if len(text) > _ONE_LINE_LIMIT else "")


def coerce_one_line_override(text: str | None) -> str | None:
    normalized = " ".join(str(text or "").split())
    if len(normalized) < 12:
        return None
    if normalized == "(no claims extracted)":
        return None
    if normalized.count("http://") or normalized.count("https://"):
        return None
    return _clip_one_line(normalized)


def _claim_index(claim_id: str | None) -> int:
    match = re.search(r"(\d+)$", str(claim_id or ""))
    if not match:
        return 999
    try:
        return int(match.group(1))
    except ValueError:
        return 999


def _adjacent_repeat_count(tokens: list[str]) -> int:
    repeats = sum(1 for i in range(1, len(tokens)) if tokens[i] == tokens[i - 1])
    for size in (2, 3):
        for i in range(size, len(tokens) - size + 1):
            if tokens[i - size : i] == tokens[i : i + size]:
                repeats += 1
    return repeats


def score_summary_text(
    text: str,
    *,
    claim_id: str | None = None,
    content_type: str = "other",
    confidence: str = "low",
    time_ref: str | None = None,
    is_aside: bool = False,
    genre_name: str | None = None,
) -> float:
    """Score transcript-derived text as a deterministic one-line candidate.

    This is still a scaffold heuristic, not semantic summarization. It avoids
    choosing the longest raw transcript fragment when a shorter, cleaner claim
    better represents the main content.
    """
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return -1000.0

    tokens = _TOKEN_RE.findall(normalized.lower())
    length = len(normalized)
    score = 0.0

    if is_aside:
        score -= 18
    if content_type and content_type != "other":
        score += 4
    preferred = _PREFERRED_TYPES_BY_GENRE.get(str(genre_name or ""))
    if preferred and content_type in preferred:
        score += 5
    demoted = _DEMOTED_TYPES_BY_GENRE.get(str(genre_name or ""))
    if demoted and content_type in demoted:
        score -= 10
    keywords = _GENRE_KEYWORDS.get(str(genre_name or ""), ())
    if keywords:
        lowered = normalized.lower()
        score += min(10, sum(3 for word in keywords if word.lower() in lowered))
    if confidence == "high":
        score += 8
    elif confidence == "medium":
        score += 4
    if time_ref:
        score += 2

    if 45 <= length <= 170:
        score += 16
    elif 28 <= length < 45:
        score += 7
    elif 170 < length <= 230:
        score += 3
    elif length > 230:
        score -= 12 + ((length - 230) / 18)
    else:
        score -= 8

    score += max(0.0, 11.0 - (_claim_index(claim_id) - 1) * 0.45)
    score -= _adjacent_repeat_count(tokens) * 7
    score -= sum(8 for marker in _NOISE_MARKERS if marker in normalized.lower())
    score -= sum(16 for phrase in _LOW_SIGNAL_PHRASES if phrase in normalized)
    if any(normalized.startswith(prefix) for prefix in _WEAK_STARTS):
        score -= 6
    if any(normalized.endswith(suffix) for suffix in _WEAK_ENDINGS):
        score -= 5
    if tokens:
        filler_count = sum(1 for token in tokens if token in {"어", "음", "네", "자"})
        if filler_count >= 3:
            score -= filler_count * 2
    if not any(ch.isalnum() or ("가" <= ch <= "힣") for ch in normalized):
        score -= 25
    return score


def score_claim_for_summary(claim: ClaimCandidate) -> float:
    return score_claim_for_summary_in_genre(claim, genre_name=None)


def score_claim_for_summary_in_genre(claim: ClaimCandidate, *, genre_name: str | None) -> float:
    return score_summary_text(
        claim.text,
        claim_id=claim.claim_id,
        content_type=claim.axes.content_type,
        confidence=claim.axes.confidence,
        time_ref=claim.time_ref,
        is_aside=claim.aside.is_aside,
        genre_name=genre_name,
    )


def _pick_one_line(claims: list[ClaimCandidate], *, genre: GenreDetection) -> str:
    """Deterministic placeholder: best-scored main claim, capped.

    Cheap-model upgrade replaces this with a real one-line summary; the
    deterministic version exists so the system runs without a model.
    """
    main_claims = [c for c in claims if not c.aside.is_aside]
    if not main_claims:
        # all claims are asides — fall back to longest claim
        main_claims = claims
    if not main_claims:
        return "(no claims extracted)"
    best = max(main_claims, key=lambda c: score_claim_for_summary_in_genre(c, genre_name=genre.genre))
    return _clip_one_line(best.text)


def _group_timeline(claims: list[ClaimCandidate]) -> list[TimelineEntry]:
    """Group consecutive claims sharing (time_ref, speaker) into one entry.

    Preserves the original segment grouping that the upstream extractor used,
    which is the most honest deterministic fallback when no real chaptering
    model is wired yet.
    """
    entries: list[TimelineEntry] = []
    current: TimelineEntry | None = None
    for c in claims:
        same_group = (
            current is not None
            and current.time_ref == c.time_ref
            and current.speaker == c.speaker
        )
        if not same_group:
            current = TimelineEntry(
                time_ref=c.time_ref,
                speaker=c.speaker,
                text=c.text,
            )
            entries.append(current)
        else:
            # extend the entry's representative text with the next sentence
            current.text = (current.text + " " + c.text).strip()
        if c.aside.is_aside:
            current.aside_claim_ids.append(c.claim_id)
        else:
            current.main_claim_ids.append(c.claim_id)
    return entries


def _extract_key_information(claims: list[ClaimCandidate], *, limit: int = 12) -> list[KeyInformationRow]:
    """Pick high-confidence main claims with concrete content as key-info rows.

    Heuristic: confidence == 'high' AND not aside AND content_type != 'other',
    then fall back to medium-confidence main claims if list is short. Capped at
    `limit` for compact display.
    """
    rows: list[KeyInformationRow] = []
    pool_high = [c for c in claims if not c.aside.is_aside and c.axes.confidence == "high" and c.axes.content_type != "other"]
    pool_med = [c for c in claims if not c.aside.is_aside and c.axes.confidence == "medium" and c.axes.content_type != "other"]
    chosen = (pool_high + pool_med)[:limit]
    for i, c in enumerate(chosen, start=1):
        rows.append(KeyInformationRow(
            info_id=f"K{i:03d}",
            label=c.axes.content_type,
            content=c.text,
            time_ref=c.time_ref,
            source_claim_id=c.claim_id,
            confidence=c.axes.confidence,
        ))
    return rows


def build_main_summary(
    claims: list[ClaimCandidate],
    *,
    genre: GenreDetection,
    one_line_override: str | None = None,
) -> MainSummary:
    """Build a deterministic main summary scaffold.

    Output is intentionally a SCAFFOLD: structure + a deterministic one-liner +
    a timeline + key-info rows + named genre-required sections (empty placeholders
    a model fills later). The structure is the contract; the content fillers are
    the part a cheap model upgrades.
    """
    main_count = sum(1 for c in claims if not c.aside.is_aside)
    aside_count = sum(1 for c in claims if c.aside.is_aside)

    one_line = coerce_one_line_override(one_line_override) or _pick_one_line(claims, genre=genre)
    timeline = _group_timeline(claims)
    key_info = _extract_key_information(claims)

    sections = {name: "" for name in genre.required_sections}

    return MainSummary(
        one_line=one_line,
        timeline=timeline,
        key_information=key_info,
        genre_required_sections=sections,
        main_claim_count=main_count,
        aside_claim_count=aside_count,
    )
