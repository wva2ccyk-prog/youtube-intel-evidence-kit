"""Second corrective pass, Section 5: `worth` must fail closed on any
structurally invalid residual package, comparison package, or run-dir input.

Every expected failure: exit 2, structured ok:false InvalidInputError, no
traceback, and no analysis_worth.json written.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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
        "schema_version": "youtube_residual_v0.1",
        "video": {"video_id": "real-video", "title": "Real Video", "language": "en"},
        "claim_candidates": [
            {"claim_id": "C0001", "text": "A real claim with enough words to matter here.", "speaker": "A", "time_ref": "00:00", "content_type": "claim_or_promotion", "evidence": "clear_internal_direct", "confidence": "medium"}
        ],
    }


def _write(tmp_path: Path, name: str, data) -> Path:
    p = tmp_path / name
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8")
    else:
        p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _assert_failure(result: subprocess.CompletedProcess, out: Path) -> dict:
    assert result.returncode == 2, f"expected exit 2: {result.stdout}\n{result.stderr}"
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert not (out / "analysis_worth.json").exists()
    return payload


def _run_worth(tmp_path, out_name, *extra) -> subprocess.CompletedProcess:
    return _run_cli("worth", *extra, "--out", str(tmp_path / out_name))


def test_worth_invalid_json(tmp_path) -> None:
    _write(tmp_path, "pkg.json", "{ not json")
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    _assert_failure(r, tmp_path / "out")


def test_worth_package_top_level_scalar(tmp_path) -> None:
    _write(tmp_path, "pkg.json", "42")
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    _assert_failure(r, tmp_path / "out")


def test_worth_package_no_schema_version(tmp_path) -> None:
    p = _valid_package(); p.pop("schema_version")
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "schema_version mismatch" in payload["message"]


def test_worth_package_no_video(tmp_path) -> None:
    p = _valid_package(); p.pop("video")
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "package.video is missing" in payload["message"]


def test_worth_package_blank_video_id(tmp_path) -> None:
    p = _valid_package(); p["video"]["video_id"] = ""
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "video_id is empty" in payload["message"]


def test_worth_package_blank_title(tmp_path) -> None:
    p = _valid_package(); p["video"]["title"] = ""
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "title is empty" in payload["message"]


def test_worth_package_no_claims(tmp_path) -> None:
    p = _valid_package(); p["claim_candidates"] = []
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "claim_candidates is empty" in payload["message"]


def test_worth_package_non_dict_claim_row(tmp_path) -> None:
    p = _valid_package(); p["claim_candidates"] = ["junk"]
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "is not an object" in payload["message"]


def test_worth_package_blank_claim_id(tmp_path) -> None:
    p = _valid_package(); p["claim_candidates"][0]["claim_id"] = ""
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "empty claim_id" in payload["message"]


def test_worth_package_blank_claim_text(tmp_path) -> None:
    p = _valid_package(); p["claim_candidates"][0]["text"] = ""
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "empty text" in payload["message"]


def test_worth_package_duplicate_claim_ids(tmp_path) -> None:
    p = _valid_package()
    p["claim_candidates"].append(dict(p["claim_candidates"][0]))
    _write(tmp_path, "pkg.json", p)
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "duplicate claim_id" in payload["message"]


def test_worth_missing_compare_package(tmp_path) -> None:
    _write(tmp_path, "pkg.json", _valid_package())
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"), "--compare-package", str(tmp_path / "missing.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "compare package 1" in payload["message"]


def test_worth_invalid_compare_package_json(tmp_path) -> None:
    _write(tmp_path, "pkg.json", _valid_package())
    _write(tmp_path, "cmp.json", "{ nope")
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"), "--compare-package", str(tmp_path / "cmp.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "compare package 1" in payload["message"]


def test_worth_structurally_invalid_compare_package(tmp_path) -> None:
    _write(tmp_path, "pkg.json", _valid_package())
    _write(tmp_path, "cmp.json", {"junk": True})
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"), "--compare-package", str(tmp_path / "cmp.json"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "compare package 1" in payload["message"]


def test_worth_missing_run_directory(tmp_path) -> None:
    r = _run_worth(tmp_path, "out", "--run-dir", str(tmp_path / "run"))
    payload = _assert_failure(r, tmp_path / "out")
    assert "run directory" in payload["message"]


def test_worth_malformed_run_dir_package(tmp_path) -> None:
    run = tmp_path / "run"
    (run / "residual").mkdir(parents=True)
    _write(run, "residual/package.json", {"junk": True})
    r = _run_worth(tmp_path, "out", "--run-dir", str(run))
    payload = _assert_failure(r, tmp_path / "out")
    assert "not a valid residual package" in payload["message"]


def test_worth_malformed_optional_metadata(tmp_path) -> None:
    run = tmp_path / "run"
    (run / "residual").mkdir(parents=True)
    _write(run, "residual/package.json", _valid_package())
    _write(run, "metadata.json", "{ bad")
    r = _run_worth(tmp_path, "out", "--run-dir", str(run))
    payload = _assert_failure(r, tmp_path / "out")
    assert "run metadata" in payload["message"]


def test_worth_valid_package_and_compare_succeed(tmp_path) -> None:
    _write(tmp_path, "pkg.json", _valid_package())
    _write(tmp_path, "cmp.json", _valid_package())
    r = _run_worth(tmp_path, "out", "--package", str(tmp_path / "pkg.json"), "--compare-package", str(tmp_path / "cmp.json"))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "out" / "analysis_worth.json").is_file()
