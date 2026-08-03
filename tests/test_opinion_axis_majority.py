"""Section 1 (corrective): opinion-axis majority must use actual claim counts
on the real build path.

Regression: ``build_topic_collection()`` used to compute ``support_roles`` as a
deduplicated set, so a group with one supporting and three challenging claims
was treated as a tie and the deterministic tie-break could select the wrong
axis. The group now carries ``support_role_counts`` (role -> claim count) and
opinion-axis dominance is computed from those counts. These tests call only the
public ``build_topic_collection()`` entry point.
"""

from __future__ import annotations

from youtube_intel.topic_collection import build_topic_collection


def _record(video_id: str, roles: list[str]) -> dict:
    claims = []
    for i, role in enumerate(roles, start=1):
        claims.append({
            "claim_uid": f"{video_id}:c{i}",
            "local_claim_id": f"c{i}",
            "source_video_id": video_id,
            # Near-duplicate text forces all claims into one group.
            "text": "The vendor says the kit can cut water use by twenty percent in dry weeks, "
                    "the same sentence repeated for grouping stability here.",
            "speaker": "A",
            "time_ref": "00:00",
            "content_type": "claim_or_promotion",
            "evidence": "clear_internal_direct",
            "evidence_ids": [f"{video_id}:e{i}"],
            "evidence_coordinate": {
                "evidence_id": f"{video_id}:e{i}",
                "video_id": video_id,
                "timestamp_start": 0.0,
                "timestamp_end": 4.0,
                "time_ref": "00:00",
                "speaker": "A",
                "speaker_confidence": "high",
                "modality": ["caption"],
            },
            "stance": "claim_or_promotion",
            "support_role": role,
            "modality_sources": ["caption"],
        })
    return {
        "schema_version": "youtube_video_knowledge_record.v0.1",
        "video": {"video_id": video_id, "title": "T", "language": "en"},
        "claim_records": claims,
        "evidence_records": [
            {
                "evidence_id": f"{video_id}:e{i}",
                "video_id": video_id,
                "timestamp_start": 0.0,
                "timestamp_end": 4.0,
                "time_ref": "00:00",
                "speaker": "A",
                "speaker_confidence": "high",
                "modality": ["caption"],
                "text": "The vendor says the kit can cut water use by twenty percent.",
                "confidence": "medium",
            }
            for i in range(1, len(roles) + 1)
        ],
    }


def _axes_by_group(collection: dict) -> dict[str, str]:
    """Return {claim_group_id: dominant axis} from the public opinion-groups layer."""
    axes: dict[str, str] = {}
    for og in collection["opinion_groups"]:
        for gid in og["member_claim_group_ids"]:
            axes[gid] = og["axis"]
    return axes


def _single_group_collection(roles: list[str]) -> dict:
    return build_topic_collection(
        [_record("v1", roles)],
        topic_id="t",
        topic_title="T",
        allow_single_video_opinions=True,
    )


def test_one_supporting_three_challenging_selects_challenging() -> None:
    collection = _single_group_collection(
        ["supporting_or_promotional", "challenging_or_limiting", "challenging_or_limiting", "challenging_or_limiting"]
    )
    assert len(collection["claim_groups"]) == 1, "fixture must produce exactly one claim group"
    axes = _axes_by_group(collection)
    assert axes, "expected at least one opinion group"
    assert all(axis == "challenging" for axis in axes.values()), (
        f"majority challenging claims must win; got {axes}"
    )


def test_three_supporting_one_challenging_selects_supporting() -> None:
    collection = _single_group_collection(
        ["supporting_or_promotional", "supporting_or_promotional", "supporting_or_promotional", "challenging_or_limiting"]
    )
    axes = _axes_by_group(collection)
    assert axes, "expected at least one opinion group"
    assert all(axis == "supporting" for axis in axes.values()), (
        f"majority supporting claims must win; got {axes}"
    )


def test_equal_counts_follow_documented_tie_break() -> None:
    collection = _single_group_collection(
        ["supporting_or_promotional", "challenging_or_limiting"]
    )
    axes = _axes_by_group(collection)
    assert axes, "expected at least one opinion group"
    assert all(axis == "supporting" for axis in axes.values()), (
        f"tie must break to declared axis order (supporting first); got {axes}"
    )


def test_reversed_claim_order_preserves_majority() -> None:
    forward_roles = ["supporting_or_promotional", "challenging_or_limiting", "challenging_or_limiting", "challenging_or_limiting"]
    reversed_roles = list(reversed(forward_roles))
    forward = _single_group_collection(forward_roles)
    backward = _single_group_collection(reversed_roles)
    assert _axes_by_group(forward) == _axes_by_group(backward) == {"G0001": "challenging"}


def test_reversed_record_order_preserves_majority() -> None:
    roles = ["supporting_or_promotional", "challenging_or_limiting", "challenging_or_limiting"]
    records = [_record("v1", [roles[0]]), _record("v2", roles[1:])]
    forward = build_topic_collection(
        records, topic_id="t", topic_title="T", allow_single_video_opinions=True
    )
    backward = build_topic_collection(
        list(reversed(records)), topic_id="t", topic_title="T", allow_single_video_opinions=True
    )
    assert _axes_by_group(forward) == _axes_by_group(backward)
    assert "challenging" in _axes_by_group(forward).values(), _axes_by_group(forward)
