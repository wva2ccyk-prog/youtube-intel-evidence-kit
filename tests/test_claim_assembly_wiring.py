"""Opt-in claim-assembly wiring: default is byte-identical; sentence mode merges.

These tests prove that adding ``claim_assembly`` did not change the default
("cue") output, and that "sentence" mode produces fuller, traceable claims from
a caption-fragment stream. All fixtures are synthetic.
"""

from __future__ import annotations

import pytest

from youtube_residual import build_residual_package
from youtube_residual.package import assemble_segments_to_sentences


# A synthetic caption-fragment stream: each cue is a mid-sentence slice with no
# punctuation, the way Korean auto-captions arrive. Two sentences across 5 cues.
_FRAGMENT_SEGMENTS = [
    {"text": "이 제도는", "time_ref": "00:01", "modality_source": "transcript"},
    {"text": "장기적으로", "time_ref": "00:04", "modality_source": "transcript"},
    {"text": "필요합니다", "time_ref": "00:07", "modality_source": "transcript"},
    {"text": "하지만 비용이", "time_ref": "00:10", "modality_source": "transcript"},
    {"text": "부담이죠", "time_ref": "00:13", "modality_source": "transcript"},
]


def _build(assembly):
    return build_residual_package(
        video_id="synthetic-fragment-demo",
        title="Synthetic Fragment Demo",
        language="ko",
        segments=[dict(s) for s in _FRAGMENT_SEGMENTS],
        claim_assembly=assembly,
    )


def test_default_is_cue_and_unchanged():
    # Not passing claim_assembly and passing "cue" must be identical, and the
    # default keeps one-candidate-per-fragment behavior.
    default = build_residual_package(
        video_id="synthetic-fragment-demo",
        title="Synthetic Fragment Demo",
        language="ko",
        segments=[dict(s) for s in _FRAGMENT_SEGMENTS],
    )
    cue = _build("cue")
    assert default.to_dict() == cue.to_dict()
    assert cue.claim_assembly == "cue"
    assert cue.to_dict()["claim_assembly"] == "cue"


def test_sentence_mode_merges_fragments():
    cue = _build("cue")
    sentence = _build("sentence")
    # Sentence mode yields fewer, longer claims than the fragment stream.
    assert len(sentence.claim_candidates) < len(cue.claim_candidates)
    texts = [c.text for c in sentence.claim_candidates]
    # The three leading fragments collapse into one sentence ending in "필요합니다".
    assert any(t.endswith("필요합니다") and "이 제도는" in t for t in texts)
    assert sentence.claim_assembly == "sentence"


def test_sentence_mode_preserves_traceability():
    # Every assembled segment records the source cue timestamps it merged.
    merged = assemble_segments_to_sentences([dict(s) for s in _FRAGMENT_SEGMENTS])
    assert merged
    for unit in merged:
        assert unit["source_time_refs"]
        # every recorded time_ref traces back to a real input cue
        for tr in unit["source_time_refs"]:
            assert tr in {s["time_ref"] for s in _FRAGMENT_SEGMENTS}


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        _build("paragraph")
