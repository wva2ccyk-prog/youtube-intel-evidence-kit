from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str, cwd: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        [sys.executable, "-m", "youtube_intel", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_doctor_reports_demo_and_gitignore_contract():
    root = Path(__file__).resolve().parents[1]
    result = _run_cli("doctor", cwd=root)
    assert result["ok"] is True
    assert result["core"]["synthetic_demo_available"] is True
    assert result["core"]["synthetic_topic_demo_available"] is True
    assert result["safety"]["all_required_ignores_present"] is True
    assert "youtube-intel topic-demo" in result["recommended_next_command"]


def test_demo_creates_operator_handoff_files(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "demo"
    result = _run_cli("demo", "--out", str(out), cwd=root)
    assert result["ok"] is True
    paths = result["paths"]
    for key in ("residual_package_json", "analysis_worth_json", "analysis_worth_md", "operator_summary_md", "ai_handoff_prompt_md"):
        assert Path(paths[key]).is_file(), key
    assert "not fact-checked" in Path(paths["ai_handoff_prompt_md"]).read_text(encoding="utf-8")


def test_package_worth_handoff_flow(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    pkg_dir = tmp_path / "pkg"
    worth_dir = tmp_path / "worth"
    handoff_dir = tmp_path / "handoff"
    segments = root / "examples" / "synthetic_segments.json"

    package_result = _run_cli("package", "--segments", str(segments), "--out", str(pkg_dir), cwd=root)
    assert package_result["ok"] is True

    package_path = Path(package_result["paths"]["residual_package_json"])
    worth_result = _run_cli("worth", "--package", str(package_path), "--out", str(worth_dir), cwd=root)
    assert worth_result["analysis_worth"]["decision"]["analysis_worth"] == "yes"
    assert Path(worth_result["paths"]["markdown"]).is_file()

    handoff_result = _run_cli(
        "handoff",
        "--package", str(package_path),
        "--analysis-worth", str(worth_dir / "analysis_worth.json"),
        "--out", str(handoff_dir),
        cwd=root,
    )
    assert handoff_result["ok"] is True
    assert Path(handoff_result["paths"]["operator_summary_md"]).is_file()


def test_topic_demo_creates_cross_video_terrain_files(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "topic_demo"
    result = _run_cli("topic-demo", "--out", str(out), cwd=root)
    assert result["ok"] is True
    assert result["purpose"] == "cross-video opinion terrain package"
    paths = result["paths"]
    for key in ("topic_collection_json", "topic_terrain_md", "repeated_claims_md", "disagreements_md", "outliers_md", "topic_handoff_prompt_md"):
        assert Path(paths[key]).is_file(), key
    collection = json.loads(Path(paths["topic_collection_json"]).read_text(encoding="utf-8"))
    assert collection["analysis_layer"] == "cross_video_topic_collection"
    assert collection["topic"]["final_objective"] == "cross-video opinion terrain, not single-video summarization"
    assert collection["terrain"]["truth_status"] == "not_evaluated"
    assert collection["terrain"]["repeated_claim_group_ids"]
    assert collection["terrain"]["disagreement_group_ids"]
    assert collection["terrain"]["outlier_group_ids"]
    terrain_md = Path(paths["topic_terrain_md"]).read_text(encoding="utf-8")
    assert "Single-video evidence packets are inputs" in terrain_md
    assert "It does not decide which claim is true" in terrain_md
