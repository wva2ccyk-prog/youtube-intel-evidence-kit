"""Two-axis claim taxonomy.

The central schema-integration decision (see proposal): a claim carries BOTH
- a CONTENT axis (what kind of claim it is), from the web-derived package
  schema (medical_advice / tutorial_step / ...), and
- an EPISTEMIC axis (how grounded it is), aligned to the trust-os evidence /
  confidence model (video_internal / external / inference / unclear + confidence).

These are different axes, not competing versions. Keeping both preserves the
prior claim-typing work in youtube-intel (epistemic) AND the genre-routing
value of the web package (content). This module is deterministic and
dependency-free so it can be unit-tested without models.

Korean + English markers are both handled, because the operator's real corpus
is Korean-dominant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Content axis (what kind of claim) ----------------------------------------
# Mirrors the web-derived youtube_knowledge_package schema claim_type enum.
CONTENT_CLAIM_TYPES = {
    "medical_advice",
    "health_claim",
    "technical_explanation",
    "political_claim",
    "economic_forecast",
    "investment_opinion",
    "product_recommendation",
    "personal_experience",
    "tutorial_step",
    "concept_definition",
    "other",
}

# --- Epistemic axis (how grounded) --------------------------------------------
# evidence = where the support comes from (aligned with trust-os source split)
EPISTEMIC_EVIDENCE = {
    "video_internal",  # directly stated/shown in the video
    "external",        # relies on outside knowledge
    "inference",       # inferred from video content
    "unclear",         # support unclear
}

CONFIDENCE_LEVELS = {"high", "medium", "low"}


@dataclass(slots=True)
class ClaimAxes:
    """The two-axis classification result for a single claim."""

    content_type: str
    evidence: str
    confidence: str
    content_markers: list[str] = field(default_factory=list)
    evidence_markers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "content_type": self.content_type,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "content_markers": list(self.content_markers),
            "evidence_markers": list(self.evidence_markers),
        }


# Legacy epistemic labels from youtube-intel's claim_types.py mapped onto the
# evidence/confidence axes so existing outputs migrate cleanly.
LEGACY_EPISTEMIC_MAP = {
    "fact": ("video_internal", "high"),
    "interpretation": ("inference", "medium"),
    "uncertainty": ("unclear", "low"),
    "memory/context": ("external", "medium"),
    "unsupported/needs-review": ("unclear", "low"),
}


# Content-axis marker tables. Order matters: earlier entries win ties only when
# scores are equal (see classify_content_axis). Each entry: (type, markers).
_CONTENT_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    ("medical_advice", (
        "복용", "처방", "투약", "용량", "치료받", "진단받", "병원 가",
        "dosage", "prescription", "take the medication", "consult a doctor",
    )),
    ("health_claim", (
        "혈압", "혈당", "당뇨", "콜레스테롤", "건강에", "면역", "체중", "증상",
        "blood pressure", "blood sugar", "diabetes", "cholesterol", "immune", "symptom",
    )),
    ("investment_opinion", (
        "매수", "매도", "사야", "팔아야", "비중", "포트폴리오", "투자해",
        "buy", "sell", "should invest", "allocation", "position",
    )),
    ("economic_forecast", (
        "전망", "예상된다", "오를 것", "내릴 것", "경기", "성장률", "금리 인상", "금리 인하", "침체",
        "forecast", "will rise", "will fall", "recession", "interest rate",
    )),
    ("political_claim", (
        "정부", "정책", "여당", "야당", "대통령", "국회", "선거", "법안",
        "government", "policy", "election", "the party", "bill",
    )),
    ("product_recommendation", (
        "추천", "가성비", "사길", "구매", "이 제품", "비교하면",
        "갤럭시", "아이폰", "안드로이드", "삼성페이", "삼성 페이",
        "애플페이", "애플 페이", "통화 녹음", "통화녹음", "통록",
        "에어드랍", "airdrop", "애플 생태", "연동성", "맥 스튜디오",
        "맥스튜디오", "에어팟", "애플워치", "애플 워치", "페이스 아이디",
        "face id", "지문", "보안", "피싱", "폐쇄성", "디자인", "카메라",
        "망원", "접사", "초점", "화질", "앱 아이콘", "홈화면",
        "통화 목록", "뒤로 가기", "스와이프", "키보드", "자판", "오타",
        "기변", "바꿔도", "넘어가", "못 넘어", "불편", "메인컴",
        "노트북", "갤럭시 북", "갤북", "그램프로", "그램 프로",
        "울트라 PC", "울트라 pc", "사무용", "학생용", "14in", "14인치",
        "16in", "16인치", "17in", "17인치", "터치 스크린", "터치스크린",
        "휴대성", "무게", "백팩", "가방", "가격이 올라", "저렴한 가격",
        "recommend", "worth buying", "this product", "compared to",
    )),
    ("tutorial_step", (
        "먼저", "다음으로", "설치", "실행", "코드", "명령어", "단계", "클릭",
        "next.js", "nextjs", "넥스트", "supabase", "슈파 베이스", "슈퍼 베이스",
        "슈퍼베이스", "수파 베이스", "tailwind", "테일윈드", "테일 윈드",
        "테일 인드", "shadcn", "샤드 cn", "샤드cn", "crud", "크리에이트",
        "딜리트", "업데이트", "커스텀 훅", "훅", "훅스", "jotai", "조타이",
        "조타", "상태 관리", "전역 상태", "서버리스", "백엔드", "데이터베이스",
        "first", "next step", "install", "run the", "command", "click",
    )),
    ("technical_explanation", (
        "작동 원리", "구조는", "알고리즘", "메커니즘", "내부적으로", "처리한다",
        "인공지능", "머신러닝", "기계학습", "딥러닝", "심층 신경망", "신경망",
        "뉴럴 네트워크", "뉴럴네트워크", "딥뉴럴", "뉴런 네트워크", "히든 피쳐",
        "액티베이션", "가중치", "바이어스", "시그모이드", "파라미터", "매개 변수",
        "매개변수", "수학적 함수", "하나의 함수", "행렬", "벡터",
        "비선형 변환", "패턴을 포착", "패턴을 추출", "구조적 원리",
        "작동 원리", "히든 레이어", "트랜스포머", "거대 언어 모델",
        "라지 랭귀지 모델", "프론티어 AI", "규모의 법칙", "학습 데이터",
        "할루시네이션", "환각", "XAI", "설명할 수 있는 인공지능", "몬테카",
        "경사 하강법", "잠재된 패턴", "가짜 뉴스", "국제 기구", "규제",
        "오남용", "악용", "위험한 존재", "지도 학습", "지도학습",
        "슈퍼바이즈", "supervised", "비지도", "언슈퍼바이즈", "unsupervised",
        "반지도", "준지도", "세미스퍼바이즈", "semi-supervised", "강화 학습",
        "강화학습", "리인포스먼트", "reinforcement", "분류", "classification",
        "회귀", "regression", "군집", "clustering", "차원 축소", "디멘션 리덕션",
        "레이블", "문제와 정답", "문제와 답", "수치적인 답", "보상", "피드백",
        "how it works", "architecture", "algorithm", "mechanism", "under the hood",
    )),
    ("concept_definition", (
        "이란", "라는 것은", "라는 겁니다", "라는 건데", "정의하면", "의미한다",
        "의미해", "부르는 것입니다", "라고 보시면", "라고 이해", "개념",
        "is defined as", "refers to", "the concept of", "means that",
    )),
    ("personal_experience", (
        "제 경험", "제가 해보니", "저는", "직접 해", "겪어보니", "느꼈",
        "나 같은 경우", "내가", "써 보니", "사용기", "1년 사용",
        "경험했다고", "개인적으로", "입장에서", "아재 기준",
        "in my experience", "i tried", "i felt", "personally i",
    )),
]


# Evidence-axis markers.
_EXTERNAL_MARKERS = (
    "일반적으로", "알려져 있", "통계에 따르면", "연구에 따르면", "원래", "사실 외부",
    "generally", "it is known", "studies show", "according to research", "in general",
)
_INFERENCE_MARKERS = (
    "아마", "추측", "추정", "보입니다", "보인다", "인 듯", "것 같", "짐작",
    "probably", "i guess", "seems", "likely", "presumably", "i suspect",
)
_UNCLEAR_MARKERS = (
    "모르겠", "불확실", "확실치 않", "잘 모", "애매",
    "not sure", "unclear", "uncertain", "hard to say",
)
_VIDEO_INTERNAL_MARKERS = (
    "여기 보시면", "이 영상", "방금 말씀", "화면에", "앞서 말",
    "as shown here", "in this video", "as i just said", "on screen",
)


def _scan(text: str, markers: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    found = []
    for m in markers:
        # Korean markers are matched case-sensitively against original text;
        # ascii markers against lowered text. Checking both is harmless.
        if m in text or m in lowered:
            found.append(m)
    return found


def classify_content_axis(text: str) -> tuple[str, list[str]]:
    """Return (content_type, matched_markers). Deterministic, marker-scored."""
    best_type = "other"
    best_markers: list[str] = []
    best_score = 0
    for ctype, markers in _CONTENT_MARKERS:
        hits = _scan(text, markers)
        if len(hits) > best_score:
            best_score = len(hits)
            best_type = ctype
            best_markers = hits
    return best_type, best_markers


def classify_epistemic_axis(text: str, source_hint: str | None = None) -> tuple[str, str, list[str]]:
    """Return (evidence, confidence, matched_markers).

    source_hint, when provided, biases the result:
    - "transcript"/"video": leans video_internal unless markers say otherwise
    - "external_pack": leans external
    """
    unclear = _scan(text, _UNCLEAR_MARKERS)
    if unclear:
        return "unclear", "low", unclear
    inference = _scan(text, _INFERENCE_MARKERS)
    if inference:
        return "inference", "medium", inference
    external = _scan(text, _EXTERNAL_MARKERS)
    if external:
        return "external", "medium", external
    internal = _scan(text, _VIDEO_INTERNAL_MARKERS)
    if internal:
        return "video_internal", "high", internal
    # No marker: fall back to source hint, conservative confidence.
    if source_hint in {"external_pack", "external"}:
        return "external", "medium", []
    # Default: treat as video-internal but only medium confidence (no explicit cue).
    return "video_internal", "medium", []


def normalize_content_type(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return raw if raw in CONTENT_CLAIM_TYPES else "other"


def normalize_evidence(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in EPISTEMIC_EVIDENCE:
        return raw
    if raw in LEGACY_EPISTEMIC_MAP:
        return LEGACY_EPISTEMIC_MAP[raw][0]
    return "unclear"


def classify_axes(text: str, source_hint: str | None = None) -> ClaimAxes:
    content_type, content_markers = classify_content_axis(text)
    evidence, confidence, evidence_markers = classify_epistemic_axis(text, source_hint)
    return ClaimAxes(
        content_type=content_type,
        evidence=evidence,
        confidence=confidence,
        content_markers=content_markers,
        evidence_markers=evidence_markers,
    )
