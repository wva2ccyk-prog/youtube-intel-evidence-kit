from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIM_AXES = ROOT / "src" / "youtube_residual" / "claim_axes.py"
TEST_FILE = ROOT / "tests" / "test_korean_high_risk_marker_boundaries.py"

source = CLAIM_AXES.read_text(encoding="utf-8")

source = source.replace(
    "from dataclasses import dataclass, field\n",
    "from dataclasses import dataclass, field\nimport re\n",
    1,
)

anchor = "\n\n# Evidence-axis markers.\n"
insert = r'''

# High-risk medical classification must not be triggered by substring
# collisions such as "용량" inside "사용량", or by a generic capacity statement.
# Ambiguous markers are admitted only as whole Korean terms and only when a
# medical-domain context marker is present in the same text unit.
_MEDICAL_ADVICE_AMBIGUOUS_MARKERS = {"용량"}
_MEDICAL_CONTEXT_KOREAN = (
    "복용", "처방", "투약", "약물", "의약품", "알약", "캡슐", "정제",
    "환자", "의사", "의료진", "병원",
)
_MEDICAL_CONTEXT_ENGLISH = (
    "medication", "medicine", "drug", "tablet", "capsule", "patient", "doctor",
)
_KOREAN_TERM_PARTICLES = (
    "은", "는", "이", "가", "을", "를", "의", "도", "만", "과", "와",
    "로", "으로", "에서", "에게", "께", "마다", "부터", "까지",
)


def _contains_korean_term(text: str, term: str) -> bool:
    particles = "|".join(sorted(_KOREAN_TERM_PARTICLES, key=len, reverse=True))
    pattern = rf"(?<![0-9A-Za-z가-힣]){re.escape(term)}(?:{particles})?(?![0-9A-Za-z가-힣])"
    return re.search(pattern, text) is not None


def _has_medical_context(text: str) -> bool:
    lowered = text.lower()
    return any(_contains_korean_term(text, marker) for marker in _MEDICAL_CONTEXT_KOREAN) or any(
        marker in lowered for marker in _MEDICAL_CONTEXT_ENGLISH
    )


def _scan_medical_advice(text: str, markers: tuple[str, ...]) -> list[str]:
    direct_markers = tuple(marker for marker in markers if marker not in _MEDICAL_ADVICE_AMBIGUOUS_MARKERS)
    hits = _scan(text, direct_markers)
    if _contains_korean_term(text, "용량") and _has_medical_context(text):
        hits.append("용량")
    return hits
'''

if anchor not in source:
    raise SystemExit("claim_axes.py evidence marker anchor not found")
source = source.replace(anchor, insert + anchor, 1)

old_loop = '''    for ctype, markers in _CONTENT_MARKERS:
        hits = _scan(text, markers)
        if len(hits) > best_score:
'''
new_loop = '''    for ctype, markers in _CONTENT_MARKERS:
        hits = _scan_medical_advice(text, markers) if ctype == "medical_advice" else _scan(text, markers)
        if len(hits) > best_score:
'''
if old_loop not in source:
    raise SystemExit("claim_axes.py classify loop not found")
source = source.replace(old_loop, new_loop, 1)

CLAIM_AXES.write_text(source, encoding="utf-8")

TEST_FILE.write_text(
    '''from __future__ import annotations

import pytest

from youtube_residual.claim_axes import classify_content_axis
from youtube_residual.extractor import build_claim_candidates


@pytest.mark.parametrize(
    "text",
    [
        "서버 사용량이 급증했다.",
        "관개수 사용량을 줄였다.",
        "배터리 용량이 크다.",
        "저장 용량을 두 배로 늘렸다.",
        "노트북의 배터리 용량을 비교했다.",
        "보안 설계와 지문 인식 성능을 개선했다.",
    ],
)
def test_generic_korean_capacity_and_usage_do_not_become_medical_advice(text: str) -> None:
    content_type, markers = classify_content_axis(text)
    assert content_type != "medical_advice"
    assert "용량" not in markers


@pytest.mark.parametrize(
    "text",
    [
        "하루 복용 용량을 지키세요.",
        "의사가 처방한 용량을 따르세요.",
        "약물 용량을 의료진과 상의하세요.",
        "의약품의 권장 용량을 확인하세요.",
        "Take the medication at the prescribed dosage.",
    ],
)
def test_genuine_medication_advice_remains_detected(text: str) -> None:
    content_type, markers = classify_content_axis(text)
    assert content_type == "medical_advice"
    assert markers


def test_extractor_and_downstream_claim_shape_receive_corrected_content_type() -> None:
    ordinary = build_claim_candidates("서버 사용량이 급증했다.")[0]
    medical = build_claim_candidates("약물 용량을 의료진과 상의하세요.")[0]

    assert ordinary.axes.content_type != "medical_advice"
    assert medical.axes.content_type == "medical_advice"
    assert medical.to_dict()["content_type"] == "medical_advice"
''',
    encoding="utf-8",
)
