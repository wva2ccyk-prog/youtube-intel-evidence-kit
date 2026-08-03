"""Third corrective pass, Defect 4: strict residual-package string contracts.

Required identity/text fields must actually be strings (never coerced through
``str()``), whitespace-only values are rejected, reserved fallback claim IDs are
rejected, and duplicate detection uses stripped normalized values. Both
``youtube-intel worth`` and ``youtube-intel handoff`` consume the shared
validator and must fail closed with exit 2.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from youtube_intel.package_validation import (
    PACKAGE_SCHEMA_VERSION,
    validate_residual_package_dict,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "youtube_intel", *args],
        cwd=REPO_ROOT, env=env, text=True, capture_output=True,
    )


def _valid_package() -> dict:
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "video": {"video_id": "real-video", "title": "Real Video", "language": "en"},
        "claim_candidates": [
            {"claim_id": "C0001", "text": "A real claim with enough words to matter here.", "speaker": "A", "time_ref": "00:00", "content_type": "claim_or_promotion", "evidence": "clear_internal_direct", "confidence": "medium"}
        ],
    }


def _write(tmp_path: Path, name: str, data) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    return p


def _valid_worth() -> dict:
    return {
        "schema_version": "youtube_analysis_worth_v0.1",
        "video": {"video_id": "real-video", "title": "Real Video", "language": "en"},
        "decision": {
            "analysis_worth": "worth_analyzing",
            "recommended_route": "full_verification",
            "max_cost_cents": 90,
        },
        "source_trace": [
            {
                "claim_id": "C0001",
                "time_ref": "00:00",
                "evidence": "clear_internal_direct",
                "confidence": "medium",
                "claim_type": "claim_or_promotion",
                "excerpt": "A real claim.",
            }
        ],
    }


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda p: p["video"].update(video_id="   "), "video_id is empty"),
        (lambda p: p["video"].update(title="   "), "title is empty"),
        (lambda p: p["video"].update(language="   "), "language is empty"),
        (lambda p: p["claim_candidates"][0].update(claim_id="  "), "has empty claim_id"),
        (lambda p: p["claim_candidates"][0].update(text="   "), "has empty text"),
        (lambda p: p["video"].update(video_id=123), "video_id must be a string"),
        (lambda p: p["video"].update(title={}), "title must be a string"),
        (lambda p: p["video"].update(language=[]), "language must be a string"),
        (lambda p: p["claim_candidates"][0].update(claim_id=True), "claim_id must be a string"),
        (lambda p: p["claim_candidates"][0].update(text=907), "text must be a string"),
        (lambda p: p["claim_candidates"][0].update(claim_id="unknown-claim"), "reserved fallback"),
        (lambda p: p["claim_candidates"].append(dict(p["claim_candidates"][0], claim_id=" C0001 ")), "duplicate claim_id"),
    ],
)
def test_worth_accepts_only_strict_package_strings(tmp_path, mutate, needle) -> None:
    p = _valid_package()
    mutate(p)
    _write(tmp_path, "pkg.json", p)
    r = _run_cli("worth", "--package", str(tmp_path / "pkg.json"), "--out", str(tmp_path / "out"))
    assert r.returncode == 2, f"stdout={r.stdout} stderr={r.stderr}"
    assert "Traceback" not in r.stderr
    payload = json.loads(r.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert needle in payload["message"]
    assert not (tmp_path / "out" / "analysis_worth.json").exists()


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda p: p["claim_candidates"][0].update(text="   "), "has empty text"),
        (lambda p: p["video"].update(video_id="   "), "video_id is empty"),
        (lambda p: p["claim_candidates"][0].update(claim_id="unknown-claim"), "reserved fallback"),
    ],
)
def test_handoff_accepts_only_strict_package_strings(tmp_path, mutate, needle) -> None:
    p = _valid_package()
    mutate(p)
    worth = _valid_worth()
    _write(tmp_path, "pkg.json", p)
    _write(tmp_path, "worth.json", worth)
    r = _run_cli(
        "handoff",
        "--package", str(tmp_path / "pkg.json"),
        "--analysis-worth", str(tmp_path / "worth.json"),
        "--out", str(tmp_path / "out"),
    )
    assert r.returncode == 2, f"stdout={r.stdout} stderr={r.stderr}"
    assert "Traceback" not in r.stderr
    payload = json.loads(r.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert needle in payload["message"]
    assert not (tmp_path / "out" / "handoff_manifest.json").exists()


def test_valid_unicode_strings_and_und_language_pass_validation() -> None:
    p = _valid_package()
    p["video"].update(video_id="비디오-1", title="한국어 제목", language="und")
    p["claim_candidates"][0]["text"] = "세제 사용량 지표가 이번 분기에 증가했습니다."
    assert validate_residual_package_dict(p) == []


def test_dup_ids_whitespace_normalized() -> None:
    issues = validate_residual_package_dict(_valid_package())
    assert issues == []
    p = _valid_package()
    p["claim_candidates"].append(dict(p["claim_candidates"][0], claim_id="C0001"))
    assert any("duplicate claim_id" in i for i in validate_residual_package_dict(p))
