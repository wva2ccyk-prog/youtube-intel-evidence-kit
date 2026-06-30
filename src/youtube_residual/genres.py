"""Genre detection + per-genre output requirements.

Adopted (in part) from the web-derived candidate package
`youtube_analysis_codex_package_v0_1/config/genre_rules.yaml`. We carry the
rules as Python data (no YAML dependency in this dependency-free core) and add
a deterministic genre detector based on multi-language keyword scoring.

Why genres matter even when asides are the primary target:
- the MAIN summary still needs to be produced (operator made this requirement
  explicit: "곁가지 한다고 중심요약을 날려버리면 안 된다")
- the SHAPE of the main summary is genre-dependent: a health video needs
  numeric/warning extraction; a development tutorial needs commands + steps;
  a debate needs speaker-claim mapping
- aside extraction also benefits from genre context: economic_forecast asides
  carry different weight than personal_experience asides

Detection is deterministic and dependency-free; for ambiguous videos the
operator (or a cheap-model upgrade later) can override the detected genre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Genre values must match the schema enum used by claim_axes content_type
# downstream (this is "video genre", not per-claim content). Keeping a single
# vocabulary across the codebase.
GENRES = (
    "health_medical",
    "it_ai_concept",
    "news_politics",
    "product_review",
    "development_tutorial",
    "finance_economy",
    "interview_podcast",
    "history_culture",       # added: operator's primary domain (역사 토론)
    "real_estate_local",     # added: real-estate / local-development domain
    "other",
)
_GENRE_ALIASES = {
    "tutorial": "development_tutorial",
    "market_analysis": "finance_economy",
    "ai_tech": "it_ai_concept",
    "political_debate": "news_politics",
    "general_news": "news_politics",
}

# Risk domain per genre — feeds Tier-1 validation (high-risk genres require a
# risk_and_uncertainty section, etc.)
RISK_DOMAIN = {
    "health_medical": "high",
    "it_ai_concept": "medium",
    "news_politics": "high",
    "product_review": "medium",
    "development_tutorial": "medium",
    "finance_economy": "high",
    "interview_podcast": "medium",
    "history_culture": "low",
    "real_estate_local": "high",   # finance-adjacent + 작전/광고 risk
    "other": "low",
}

# Required output sections per genre (drawn from candidate genre_rules.yaml,
# extended for the two added domains). The MAIN summary renderer reads this
# table and includes the genre-required sections in addition to the universal
# sections (one_line, timeline, key_information).
GENRE_REQUIRED_SECTIONS = {
    "health_medical": (
        "health_information_table",       # numbers/metrics/dosages
        "generalization_risks",           # what should NOT be generalized
        "expert_consultation_needed",     # explicit "see a doctor" notes
    ),
    "it_ai_concept": (
        "concept_map",                    # related concepts and hierarchy
        "examples",
        "study_order",                    # recommended learning sequence
    ),
    "news_politics": (
        "speaker_claim_map",              # who claimed what
        "fact_claim_opinion_split",       # 3-way separation
        "neutral_summary",
    ),
    "product_review": (
        "product_comparison_table",
        "subjective_objective_split",
        "recommendation_by_user_type",
    ),
    "development_tutorial": (
        "implementation_steps",
        "commands_index",
        "file_structure",
        "error_points",
    ),
    "finance_economy": (
        "concept_table",
        "fact_forecast_opinion_split",    # 3-way
        "investment_warnings",            # NOT advice; warnings only
    ),
    "interview_podcast": (
        "question_answer_structure",
        "advice_steps",
        "examples_and_metaphors",
    ),
    "history_culture": (
        "timeline_of_events",
        "competing_interpretations",      # multiple scholar views
        "consensus_vs_debate",            # what is settled vs contested
    ),
    "real_estate_local": (
        "location_facts",                 # objective info (zoning, transit)
        "claimed_upside_vs_evidence",     # claim/evidence split
        "promotion_signals",              # ad/scheme markers, NOT verdicts
        "verification_needed",
    ),
    "other": (),
}

# Genre-detection markers (multi-language). Order matters only for tie-breaking.
_GENRE_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    ("health_medical", (
        "혈압", "혈당", "당뇨", "콜레스테롤", "복용", "처방", "의사", "병원", "치료", "증상",
        "blood pressure", "diabetes", "cholesterol", "medication", "doctor",
        "patient", "diagnosis", "symptom", "treatment", "clinical",
    )),
    ("real_estate_local", (
        "부동산", "분양", "재개발", "재건축", "호재", "입지", "역세권", "공시지가",
        "real estate", "housing market", "rezoning", "development project",
        "property value", "neighborhood",
    )),
    ("finance_economy", (
        "금리", "환율", "주식", "증시", "물가", "인플레이션", "코스피", "나스닥", "포트폴리오", "수익률",
        "interest rate", "stock market", "inflation", "earnings", "fed", "central bank",
        "portfolio", "valuation", "recession",
    )),
    ("news_politics", (
        "대통령", "국회", "여당", "야당", "선거", "법안", "정책", "외교", "북한",
        "president", "congress", "senate", "election", "policy", "foreign policy",
        "the white house", "diplomatic", "geopolitical",
    )),
    ("development_tutorial", (
        "패키지", "설치", "코드", "커밋", "디버그", "라이브러리", "프레임워크", "터미널", "함수",
        "install", "package", "library", "framework", "function", "debug",
        "terminal", "code", "commit", "deploy", "compile",
    )),
    ("it_ai_concept", (
        "머신러닝", "딥러닝", "신경망", "트랜스포머", "임베딩", "강화학습", "토큰", "어텐션",
        "machine learning", "deep learning", "neural network", "transformer",
        "embedding", "reinforcement", "attention", "model architecture",
    )),
    ("product_review", (
        "리뷰", "후기", "구매", "스펙", "비교", "가성비", "추천", "단점", "장점",
        "review", "unboxing", "specs", "comparison", "value for money",
        "pros and cons", "verdict",
    )),
    ("history_culture", (
        "역사", "왕조", "사료", "유적", "전쟁", "조선", "고려", "고대", "근대",
        "교과서", "외교", "왕", "황제", "통치", "사관", "근현대",
        "history", "historical", "dynasty", "ancient", "medieval", "primary source",
        "archaeology", "civilization", "diplomacy of", "kingdom", "empire",
        "monarch", "according to the records",
    )),
    ("interview_podcast", (
        "인터뷰", "대담", "팟캐스트", "토론", "질문", "답변",
        "interview", "podcast", "discussion", "panel", "q and a", "guest",
        "host", "conversation",
    )),
]


@dataclass(slots=True)
class GenreDetection:
    genre: str
    risk_domain: str
    required_sections: tuple[str, ...]
    score: int = 0
    matched_markers: list[str] = field(default_factory=list)
    detection_basis: str = "marker_score"  # marker_score | override | default

    def to_dict(self) -> dict:
        return {
            "genre": self.genre,
            "risk_domain": self.risk_domain,
            "required_sections": list(self.required_sections),
            "score": self.score,
            "matched_markers": list(self.matched_markers),
            "detection_basis": self.detection_basis,
        }


def detect_genre(text: str, *, override: str | None = None) -> GenreDetection:
    """Detect genre from concatenated transcript/title text.

    If `override` is supplied (a valid genre name), use it; otherwise score by
    marker overlap. The default fallback is `other` so the system is honest
    when a video does not match any genre cleanly.
    """
    if override:
        canonical = canonical_genre(override)
    else:
        canonical = None
    if canonical and canonical in GENRES:
        g = canonical
        return GenreDetection(
            genre=g,
            risk_domain=RISK_DOMAIN[g],
            required_sections=GENRE_REQUIRED_SECTIONS[g],
            score=0,
            matched_markers=[],
            detection_basis="override",
        )

    lowered = text.lower()
    best_genre = "other"
    best_score = 0
    best_markers: list[str] = []
    for genre, markers in _GENRE_MARKERS:
        hits = [m for m in markers if (m in text or m in lowered)]
        if len(hits) > best_score:
            best_score = len(hits)
            best_genre = genre
            best_markers = hits

    return GenreDetection(
        genre=best_genre,
        risk_domain=RISK_DOMAIN[best_genre],
        required_sections=GENRE_REQUIRED_SECTIONS[best_genre],
        score=best_score,
        matched_markers=best_markers,
        detection_basis="marker_score" if best_score > 0 else "default",
    )


def canonical_genre(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw in GENRES:
        return raw
    compact = raw.lower().replace("/", "_").replace(" ", "_")
    if compact in GENRES:
        return compact
    if compact in _GENRE_ALIASES:
        return _GENRE_ALIASES[compact]
    lowered = raw.lower()
    if "건강" in lowered or "의학" in lowered:
        return "health_medical"
    if "금융" in lowered or "경제" in lowered or "시장" in lowered:
        return "finance_economy"
    if "개발" in lowered or "튜토리얼" in lowered:
        return "development_tutorial"
    if "it/ai" in lowered or "ai 강" in lowered or "인공지능" in lowered:
        return "it_ai_concept"
    if "뉴스" in lowered or "시사" in lowered or "토론" in lowered:
        return "news_politics"
    if "인터뷰" in lowered or "팟캐스트" in lowered:
        return "interview_podcast"
    if "제품" in lowered or "리뷰" in lowered or "후기" in lowered:
        return "product_review"
    return compact
