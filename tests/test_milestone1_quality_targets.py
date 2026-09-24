"""Milestone 1 quality targets (see ROADMAP.md, "Milestone 1").

The contract tests elsewhere guard artifact shape. These tests guard whether
the terrain is useful on inputs the engine was not tuned for: a Korean topic,
an English topic outside the orchard demo domain, and filler-heavy captions.

Every target that the current engine misses is marked
``xfail(strict=True)``. When a change makes a target pass, pytest reports
XPASS as a failure; remove that marker in the same change so the target stays
pinned as a regular regression test.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from youtube_intel.topic_collection import build_topic_demo_from_segments

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent / "fixtures" / "eval_topics"
ORCHARD_DIR = REPO_ROOT / "examples" / "topic_demo"
TERRAIN_FIXTURES = ("ko_ev_battery", "en_ev_battery")

# Words that only make sense for the synthetic orchard demo topic. A grouping,
# stance, or need-gate rule that mentions them is tuned to the demo fixture
# rather than to the language.
ORCHARD_DOMAIN_WORDS = ("irrigation", "salinity", "subsidy", "subsidies", "probe", "probes", "drift", "drifted")

MILESTONE_1 = "Milestone 1 target not met yet (ROADMAP.md)"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build(topic_dir: Path, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = build_topic_demo_from_segments(
        topic_dir,
        topic_id=f"eval-{topic_dir.name}",
        topic_title=f"Evaluation topic {topic_dir.name}",
        output_dir=out,
    )
    collection = _read(Path(manifest["paths"]["topic_collection_json"]))
    return manifest, collection


def _text_to_uid(collection: dict[str, Any]) -> dict[str, str]:
    return {claim["text"]: uid for uid, claim in collection["claim_index"].items()}


def _expected_texts(topic_dir: Path) -> set[str]:
    texts: set[str] = set()
    groupings = _read(topic_dir / "expected_groupings.json")
    disagreements = _read(topic_dir / "expected_disagreements.json")
    for key in ("must_link", "cannot_link"):
        for pair in groupings.get(key, []):
            texts.update(pair)
    for pair in disagreements["cross_video_contradiction_pairs"]:
        texts.update(pair)
    return texts


@pytest.mark.parametrize("name", TERRAIN_FIXTURES)
def test_eval_fixture_labels_resolve_to_exact_claims(name: str, tmp_path: Path) -> None:
    topic_dir = EVAL_ROOT / name
    manifest, collection = _build(topic_dir, tmp_path)
    assert manifest["ok"] is True
    assert "grouping_evaluation" in manifest
    missing = _expected_texts(topic_dir) - set(_text_to_uid(collection))
    assert not missing, f"labels no longer match extracted claim text: {sorted(missing)}"


@pytest.mark.xfail(strict=True, reason=MILESTONE_1)
def test_orchard_demo_meets_its_own_grouping_threshold(tmp_path: Path) -> None:
    manifest, _ = _build(ORCHARD_DIR, tmp_path)
    assert manifest["grouping_evaluation"]["status"] == "pass", manifest["grouping_evaluation"]["score"]


@pytest.mark.xfail(strict=True, reason=MILESTONE_1)
@pytest.mark.parametrize("name", TERRAIN_FIXTURES)
def test_out_of_domain_grouping_meets_threshold(name: str, tmp_path: Path) -> None:
    manifest, _ = _build(EVAL_ROOT / name, tmp_path)
    evaluation = manifest["grouping_evaluation"]
    assert evaluation["status"] == "pass", evaluation["score"]


@pytest.mark.xfail(strict=True, reason=MILESTONE_1)
@pytest.mark.parametrize("name", TERRAIN_FIXTURES)
def test_cross_video_contradictions_are_flagged(name: str, tmp_path: Path) -> None:
    topic_dir = EVAL_ROOT / name
    _, collection = _build(topic_dir, tmp_path)
    uids = _text_to_uid(collection)
    terrain = collection["terrain"]
    flagged: list[set[str]] = [
        {item["left_claim_uid"], item["right_claim_uid"]} for item in terrain["contradiction_candidates"]
    ]
    flagged += [set(item["claim_uids"]) for item in terrain["disagreement_relations"]]
    expected = _read(topic_dir / "expected_disagreements.json")["cross_video_contradiction_pairs"]
    unflagged = [
        pair for pair in expected
        if not any({uids[pair[0]], uids[pair[1]]} <= found for found in flagged)
    ]
    assert not unflagged, f"cross-video contradictions not flagged: {unflagged}"


@pytest.mark.xfail(strict=True, reason=MILESTONE_1)
def test_filler_lines_are_not_repeated_claims(tmp_path: Path) -> None:
    topic_dir = EVAL_ROOT / "ko_filler_noise"
    _, collection = _build(topic_dir, tmp_path)
    filler = set(_read(topic_dir / "filler_lines.json")["filler_lines"])
    claim_index = collection["claim_index"]
    filler_groups = [
        group["group_id"]
        for group in collection["claim_groups"]
        if group["status"]["repeated_claim"]
        and {claim_index[uid]["text"] for uid in group["claim_uids"]} <= filler
    ]
    assert not filler_groups, f"filler reported as repeated claims: {filler_groups}"


@pytest.mark.xfail(strict=True, reason=MILESTONE_1)
def test_grouping_rules_carry_no_orchard_demo_vocabulary() -> None:
    hits: list[str] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        if "_fixtures" in path.parts or path.name == "cli.py":
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        for word in ORCHARD_DOMAIN_WORDS:
            if f'"{word}"' in lowered:
                hits.append(f"{path.relative_to(REPO_ROOT)}: {word}")
    assert not hits, hits


@pytest.mark.xfail(strict=True, reason=MILESTONE_1)
def test_failed_grouping_evaluation_is_surfaced_in_manifest(tmp_path: Path) -> None:
    topic_dir = tmp_path / "topic"
    topic_dir.mkdir()
    for source in ORCHARD_DIR.glob("video_*.json"):
        shutil.copy(source, topic_dir / source.name)
    (topic_dir / "expected_groupings.json").write_text(json.dumps({
        "threshold": 1.0,
        "must_link": [[
            "The subsidy deadline is pushing sensor adoption faster than farmer demand.",
            "This might be wrong, but local salinity may explain the yield bump more than the sensor software.",
        ]],
    }), encoding="utf-8")
    manifest, _ = _build(topic_dir, tmp_path / "out")
    assert manifest["grouping_evaluation"]["status"] == "fail"
    warnings = manifest.get("warnings", [])
    assert any("grouping_evaluation" in str(w) for w in warnings), warnings
