from __future__ import annotations

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
