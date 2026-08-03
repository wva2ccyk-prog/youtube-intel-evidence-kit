"""P1-A: deterministic, cohesive claim clustering.

The clusterers used a single-link rule (a claim joins when similar to ANY
member), which permitted bridge chaining and made results input-order
dependent. Both clusterers now sort claims deterministically and use a
complete-link cohesion rule (similarity to EVERY member). Opinion-axis
dominance is decided by role counts, not by enum order.
"""

from __future__ import annotations

from youtube_intel.topic_collection import (
    _claim_similarity,
    _dominant_axis,
    _group_claims_by_similarity,
    _group_claims_by_token_jaccard,
    build_opinion_groups,
    build_topic_collection,
)

# --- bridge-chain claims ----------------------------------------------------
# A~B are near-duplicates; B~C share a few tokens; A~C are far apart.
# Under single-link, C rides in through B (bridge chaining). Under
# complete-link with threshold 0.30, C must stay out because A~C < 0.30.
BRIDGE_A = {"claim_uid": "bridge:A", "text": "The kit cuts water use by twenty percent."}
BRIDGE_B = {"claim_uid": "bridge:B", "text": "The kit cuts water use by twenty percent, the vendor claims."}
BRIDGE_C = {"claim_uid": "bridge:C", "text": "The vendor claims the kit needs yearly maintenance."}


def _record(claims: list[dict], video_ids: list[str]) -> list[dict]:
    return [
        {
            "video": {"video_id": vid},
            "claim_records": [dict(c, source_video_id=vid, stance="claim_or_promotion", support_role="supporting_or_promotional", evidence_ids=[]) for c in claims],
            "evidence_records": [],
        }
        for vid in video_ids
    ]


def test_bridge_chain_is_broken_under_complete_link() -> None:
    assert _claim_similarity(BRIDGE_A, BRIDGE_B) >= 0.30
    assert _claim_similarity(BRIDGE_B, BRIDGE_C) >= 0.30
    assert _claim_similarity(BRIDGE_A, BRIDGE_C) < 0.30
    grouped = _group_claims_by_similarity([BRIDGE_A, BRIDGE_B, BRIDGE_C], threshold=0.30)
    members = sorted(
        sorted(claim["claim_uid"] for claim in group)
        for _, group, _, _ in grouped
    )
    assert members == [["bridge:A", "bridge:B"], ["bridge:C"]], (
        "complete-link must not let C ride in through the B bridge"
    )


def test_normalized_clusterer_is_permutation_invariant() -> None:
    claims = [BRIDGE_A, BRIDGE_B, BRIDGE_C]
    forward = _group_claims_by_similarity(claims, threshold=0.30)
    backward = _group_claims_by_similarity(list(reversed(claims)), threshold=0.30)
    normalized = [
        (key, sorted(c["claim_uid"] for c in group), mean, min_score)
        for key, group, mean, min_score in forward
    ]
    normalized_back = [
        (key, sorted(c["claim_uid"] for c in group), mean, min_score)
        for key, group, mean, min_score in backward
    ]
    assert normalized == normalized_back


def test_token_jaccard_clusterer_is_permutation_invariant() -> None:
    claims = [BRIDGE_A, BRIDGE_B, BRIDGE_C]
    forward = _group_claims_by_token_jaccard(claims, threshold=0.30)
    backward = _group_claims_by_token_jaccard(list(reversed(claims)), threshold=0.30)
    normalized = [
        (key, sorted(c["claim_uid"] for c in group), mean, min_score)
        for key, group, mean, min_score in forward
    ]
    normalized_back = [
        (key, sorted(c["claim_uid"] for c in group), mean, min_score)
        for key, group, mean, min_score in backward
    ]
    assert normalized == normalized_back


def test_token_jaccard_group_representation_updates_with_members() -> None:
    # C shares tokens with B (0.27 jaccard >= 0.20) but not with A (0.09);
    # the union representation must not be pinned to whichever claim was
    # sorted first, and C must not ride in through the B bridge.
    grouped = _group_claims_by_token_jaccard([BRIDGE_A, BRIDGE_B, BRIDGE_C], threshold=0.20)
    member_sets = [
        sorted(claim["claim_uid"] for claim in group)
        for _, group, _, _ in grouped
    ]
    assert all(len(members) <= 2 for members in member_sets)
    assert ["bridge:B", "bridge:C"] in member_sets or ["bridge:A", "bridge:B"] in member_sets


def test_empty_token_claims_do_not_collide() -> None:
    empty_a = {"claim_uid": "e:a", "text": ""}
    empty_b = {"claim_uid": "e:b", "text": "!!!"}
    for clusterer in (_group_claims_by_similarity, _group_claims_by_token_jaccard):
        grouped = clusterer([empty_a, empty_b])
        assert len(grouped) == 2, "empty-token claims must not be force-merged"


def test_korean_claims_group_deterministically() -> None:
    ko_a = {"claim_uid": "ko:a", "text": "관개용 물 사용량을 줄이면 비용이 절감됩니다."}
    ko_b = {"claim_uid": "ko:b", "text": "관개용 물 사용량 감소는 비용 절감으로 이어집니다."}
    ko_c = {"claim_uid": "ko:c", "text": "이 배터리는 충전 속도가 느립니다."}
    # Korean normalized similarity runs lower than English (no space-delimited
    # tokenization benefit), so the test pins the threshold explicitly. See
    # docs for the remaining Korean grouping limitations.
    forward = _group_claims_by_similarity([ko_a, ko_b, ko_c], threshold=0.15)
    backward = _group_claims_by_similarity([ko_c, ko_b, ko_a], threshold=0.15)
    norm = lambda rows: sorted((key, sorted(c["claim_uid"] for c in g), mean, mn) for key, g, mean, mn in rows)
    assert norm(forward) == norm(backward)
    member_sets = [sorted(c["claim_uid"] for c in g) for _, g, _, _ in forward]
    assert ["ko:a", "ko:b"] in member_sets, "related Korean claims should group together"


def test_out_of_domain_english_claims_stay_separate() -> None:
    claims = [
        {"claim_uid": "o:1", "text": "The new electric truck charges in thirty minutes."},
        {"claim_uid": "o:2", "text": "The new electric truck charges in thirty minutes flat."},
        {"claim_uid": "o:3", "text": "Interest rates are expected to rise next quarter."},
    ]
    grouped = _group_claims_by_similarity(claims)
    member_sets = [sorted(c["claim_uid"] for c in g) for _, g, _, _ in grouped]
    assert ["o:1", "o:2"] in member_sets
    assert not any("o:3" in members and len(members) > 1 for members in member_sets), (
        "out-of-domain claim must not join another claim's group"
    )

def test_build_topic_collection_permutation_invariant() -> None:
    claims_a = [
        {"claim_uid": "v1:c1", "text": "The vendor says the kit can cut water use by twenty percent."},
        {"claim_uid": "v1:c2", "text": "But local soil and maintenance discipline may explain it, not the device."},
    ]
    claims_b = [
        {"claim_uid": "v2:c1", "text": "The kit can cut water use, the vendor claims twenty percent."},
        {"claim_uid": "v2:c2", "text": "Local soil and maintenance may explain the yield bump, not the device."},
    ]
    forward = build_topic_collection(_record(claims_a, ["v1"]) + _record(claims_b, ["v2"]), topic_id="t", topic_title="T")
    backward = build_topic_collection(_record(claims_b, ["v2"]) + _record(claims_a, ["v1"]), topic_id="t", topic_title="T")
    assert forward["claim_groups"] == backward["claim_groups"]
    assert forward["opinion_groups"] == backward["opinion_groups"]


# --- opinion-axis dominance --------------------------------------------------


def _opinion_group(roles: list[str]) -> dict:
    return {
        "group_id": "g1",
        "claim_group_key": "k",
        "claim_uids": [f"c{i}" for i in range(len(roles))],
        "support_roles": roles,
    }


def test_dominant_axis_uses_majority_counts() -> None:
    group = _opinion_group(["supporting_or_promotional", "challenging_or_limiting", "challenging_or_limiting"])
    assert _dominant_axis(group) == "challenging", "majority challenging roles must win"


def test_dominant_axis_tie_break_is_deterministic() -> None:
    tie = _opinion_group(["supporting_or_promotional", "challenging_or_limiting"])
    assert _dominant_axis(tie) == "supporting", "ties break to declared axis order (supporting first)"
    tie_reversed = _opinion_group(["challenging_or_limiting", "supporting_or_promotional"])
    assert _dominant_axis(tie_reversed) == "supporting", "tie-break must not depend on role order"


def test_dominant_axis_falls_back_to_reported() -> None:
    assert _dominant_axis(_opinion_group([])) == "reported"
    assert _dominant_axis(_opinion_group(["reported_context"])) == "reported"


def test_opinion_groups_reflect_majority_axis() -> None:
    groups = [
        {
            "group_id": "g-support",
            "claim_group_key": "water-saving",
            "claim_uids": ["a", "b"],
            "support_roles": ["supporting_or_promotional", "supporting_or_promotional"],
        },
        {
            "group_id": "g-challenge",
            "claim_group_key": "soil-causality",
            "claim_uids": ["c", "d"],
            "support_roles": ["challenging_or_limiting", "challenging_or_limiting"],
        },
    ]
    opinion_groups, _ = build_opinion_groups(groups, allow_single_video=True)
    axes = {og["axis"] for og in opinion_groups}
    assert "supporting" in axes
    assert "challenging" in axes
