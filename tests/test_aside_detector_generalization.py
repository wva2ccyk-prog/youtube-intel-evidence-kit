from __future__ import annotations

import pytest

from youtube_residual.aside_profiles import LEGACY_FIXTURE_TYPE1_MARKERS
from youtube_residual.aside_signals import (
    ASIDE_NONE,
    ASIDE_TYPE1_HIDDEN,
    ASIDE_TYPE2_UNFORMED,
    detect_aside_signal,
)
from youtube_residual.extractor import build_claim_candidates


@pytest.mark.parametrize(
    "text",
    [
        "램값과 부품값 때문에 가격이 20만 원 올랐습니다.",
        "이 노트북은 휴대하기 부담스럽고 백팩이 필요합니다.",
        "성능 차이는 크게 안 나고 무게 차이도 얼마 안 됩니다.",
        "To be honest, this product is expensive.",
        "Officially released today.",
        "In reality the battery lasts eight hours.",
    ],
)
def test_ordinary_or_single_broad_markers_are_not_hidden_info(text: str) -> None:
    result = detect_aside_signal(text)
    assert result.aside_type == ASIDE_NONE
    assert result.score == 0


@pytest.mark.parametrize(
    "text",
    [
        "오프더레코드로 말씀드리면 공급이 이미 중단됐습니다.",
        "공식적으로는 정상이라지만 현장에서는 실제로는 멈춰 있습니다.",
        "From what I've seen on the ground, the official report misses repeated failures.",
        "You didn't hear it from me; privately, the rollout was cancelled.",
    ],
)
def test_explicit_private_or_structural_field_signals_remain_type1(text: str) -> None:
    result = detect_aside_signal(text)
    assert result.aside_type == ASIDE_TYPE1_HIDDEN
    assert result.score > 0
    assert result.needs_audio_check is True


def test_field_observation_plus_disclosure_gap_preserves_synthetic_orchard_case() -> None:
    text = (
        "In the field, the cheap probes drifted after two foggy nights, "
        "which the sponsored case study did not mention."
    )
    result = detect_aside_signal(text)
    assert result.aside_type == ASIDE_TYPE1_HIDDEN
    assert result.score == 4
    assert "in the field" in result.markers
    assert "did not mention" in result.markers


def test_type2_hypothesis_behavior_is_unchanged() -> None:
    result = detect_aside_signal("문득 이런 거 아닐까 싶습니다.")
    assert result.aside_type == ASIDE_TYPE2_UNFORMED
    assert result.score > 0


def test_fixture_specific_markers_are_opt_in_only() -> None:
    text = "램값과 부품값 때문에 가격이 올랐습니다."
    assert detect_aside_signal(text).aside_type == ASIDE_NONE

    profiled = detect_aside_signal(
        text,
        type1_profile_markers=LEGACY_FIXTURE_TYPE1_MARKERS,
    )
    assert profiled.aside_type == ASIDE_TYPE1_HIDDEN
    assert "램값과 부품값" in profiled.markers


def test_extractor_uses_generalized_default_detector() -> None:
    ordinary = build_claim_candidates("램값과 부품값 때문에 가격이 올랐습니다.")[0]
    hidden = build_claim_candidates("오프더레코드로 공급 중단을 확인했습니다.")[0]

    assert ordinary.aside.aside_type == ASIDE_NONE
    assert hidden.aside.aside_type == ASIDE_TYPE1_HIDDEN
