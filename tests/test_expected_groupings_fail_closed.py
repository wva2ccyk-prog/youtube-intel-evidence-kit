"""Fourth corrective pass, Section 8: expected-groupings evaluation must be
fail-closed at the library API boundary too.

``evaluate_topic_collection`` must never silently skip malformed rows or produce
a score from a reduced set. ``validate_expected_groupings_document`` is the
dependency-free validator; ``assert_valid_expected_groupings_document`` raises
``InvalidInputError`` on any defect. These tests exercise the library API
directly (not only the topic-demo CLI path).
"""

from __future__ import annotations

import pytest

from youtube_intel.errors import InvalidInputError
from youtube_intel.topic_collection import (
    assert_valid_expected_groupings_document,
    evaluate_topic_collection,
    validate_expected_groupings_document,
)


def _valid_expected() -> dict:
    return {
        "must_link": [["alpha", "beta"]],
        "cannot_link": [["gamma", "delta"]],
        "threshold": 0.5,
    }


def _collection() -> dict:
    # A minimal but structurally sufficient TopicCollection for the evaluator.
    return {
        "claim_index": {
            "alpha": {"text": "alpha"},
            "beta": {"text": "beta"},
            "gamma": {"text": "gamma"},
            "delta": {"text": "delta"},
        },
        "claim_groups": [
            {"group_id": "g1", "claim_uids": ["alpha", "beta"]},
            {"group_id": "g2", "claim_uids": ["gamma", "delta"]},
        ],
    }


def test_valid_document_passes() -> None:
    assert validate_expected_groupings_document(_valid_expected()) == []
    assert_valid_expected_groupings_document(_valid_expected(), label="expected")
    result = evaluate_topic_collection(_collection(), _valid_expected())
    assert result["status"] == "pass"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("must_link"),
        lambda d: d.update({"must_link": None}),
        lambda d: d.update({"must_link": "scalar"}),
        lambda d: d.update({"must_link": [["a", "b", "c"]]}),
        lambda d: d.update({"must_link": [["", "b"]]}),
        lambda d: d.update({"must_link": [["a", 42]]}),
        lambda d: d.update({"must_link": [["a", "b"], ["a", "b"]]}),
        lambda d: d.update({"must_link": [["a", "b"], ["b", "a"]]}),
        lambda d: d.update({"must_link": [["a", "a"]]}),
        lambda d: d.update({"cannot_link": "scalar"}),
        lambda d: d.update({"threshold": "NaN"}),
        lambda d: d.update({"threshold": True}),
        lambda d: d.update({"threshold": float("nan")}),
        lambda d: d.update({"threshold": 1.5}),
        lambda d: d.update({"threshold": -0.1}),
        lambda d: d.update({"bogus_field": 1}),
    ],
)
def test_malformed_documents_are_rejected(mutate) -> None:
    doc = _valid_expected()
    mutate(doc)
    assert validate_expected_groupings_document(doc), "expected an issue list"
    with pytest.raises(InvalidInputError):
        assert_valid_expected_groupings_document(doc, label="expected")
    with pytest.raises(InvalidInputError):
        evaluate_topic_collection(_collection(), doc)


def test_contradictory_pair_rejected() -> None:
    doc = _valid_expected()
    doc["cannot_link"] = [["alpha", "beta"]]
    assert validate_expected_groupings_document(doc)
    with pytest.raises(InvalidInputError):
        evaluate_topic_collection(_collection(), doc)


def test_evaluator_never_accepts_non_dict_expected() -> None:
    with pytest.raises(InvalidInputError):
        evaluate_topic_collection(_collection(), [])  # type: ignore[arg-type]