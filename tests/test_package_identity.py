"""Section 4 (corrective): the general `package` command must never fabricate
synthetic identity. video_id and title are required (from --video-id/--title or
the input file); language is required unless the explicit value 'und' is used.
Synthetic fallbacks remain only in explicitly synthetic demo commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "youtube_intel", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def _valid_segments(tmp_path: Path) -> Path:
    f = tmp_path / "segments.json"
    f.write_text(
        json.dumps({"video": {"video_id": "real-video", "title": "Real Title", "language": "en"},
                     "segments": [{"text": "A real segment with enough words to make a claim.", "speaker": "A"}]}),
        encoding="utf-8",
    )
    return f


def test_package_without_video_id_fails(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": {"title": "T", "language": "en"}, "segments": [{"text": "A real segment with enough words to make a claim.", "speaker": "A"}]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "video_id" in payload["message"]


def test_package_without_title_fails(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": {"video_id": "v1", "language": "en"}, "segments": [{"text": "A real segment with enough words to make a claim.", "speaker": "A"}]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "title" in payload["message"]


def test_package_without_language_fails(tmp_path) -> None:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": {"video_id": "v1", "title": "T"}, "segments": [{"text": "A real segment with enough words to make a claim.", "speaker": "A"}]}), encoding="utf-8")
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "language" in payload["message"]


def test_package_undefined_language_escape_hatch(tmp_path) -> None:
    f = _valid_segments(tmp_path)
    out = tmp_path / "out"
    result = _run_cli(
        "package", "--segments", str(f), "--out", str(out), "--language", "und"
    )
    assert result.returncode == 0, result.stderr
    package = json.loads((out / "residual_package.json").read_text(encoding="utf-8"))
    assert package["video"]["language"] == "und"


def test_package_cli_flags_override_file_metadata(tmp_path) -> None:
    f = _valid_segments(tmp_path)
    out = tmp_path / "out"
    result = _run_cli(
        "package", "--segments", str(f), "--out", str(out),
        "--video-id", "flagged-video", "--title", "Flagged Title", "--language", "ko",
    )
    assert result.returncode == 0, result.stderr
    package = json.loads((out / "residual_package.json").read_text(encoding="utf-8"))
    assert package["video"]["video_id"] == "flagged-video"
    assert package["video"]["title"] == "Flagged Title"
    assert package["video"]["language"] == "ko"


def test_package_output_identity_matches_supplied_identity(tmp_path) -> None:
    f = _valid_segments(tmp_path)
    out = tmp_path / "out"
    result = _run_cli("package", "--segments", str(f), "--out", str(out))
    assert result.returncode == 0, result.stderr
    package = json.loads((out / "residual_package.json").read_text(encoding="utf-8"))
    assert package["video"]["video_id"] == "real-video"
    assert package["video"]["title"] == "Real Title"
    assert package["video"]["language"] == "en"
    assert "synthetic" not in str(package["video"]["video_id"]).lower()


def test_demo_commands_still_use_synthetic_fixtures(tmp_path) -> None:
    out = tmp_path / "demo"
    result = _run_cli("single-video-demo", "--out", str(out))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    package = json.loads(Path(payload["paths"]["residual_package_json"]).read_text(encoding="utf-8"))
    assert package["video"]["video_id"] == "synthetic-field-demo"

# --- Fourth pass (Section 7): package CLI must reject non-string identity ----


def _write_pkg_segments(tmp_path: Path, video: dict) -> Path:
    f = tmp_path / "segments.json"
    f.write_text(json.dumps({"video": video, "segments": [{"text": "A real segment with enough words to make a claim.", "speaker": "A"}]}), encoding="utf-8")
    return f


def _assert_identity_failure(result: subprocess.CompletedProcess, out: Path) -> dict:
    assert result.returncode == 2, f"stdout={result.stdout} stderr={result.stderr}"
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert not (out / "residual_package.json").exists()
    return payload


@pytest.mark.parametrize("video, needle", [
    ({"video_id": 123, "title": "T", "language": "en"}, "video_id must be a string"),
    ({"video_id": True, "title": "T", "language": "en"}, "video_id must be a string"),
    ({"video_id": "v1", "title": {}, "language": "en"}, "title must be a string"),
    ({"video_id": "v1", "title": ["x"], "language": "en"}, "title must be a string"),
    ({"video_id": "v1", "title": "T", "language": 4}, "language must be a string"),
    ({"video_id": "   ", "title": "T", "language": "en"}, "video_id is empty"),
    ({"video_id": "v1", "title": "   ", "language": "en"}, "title is empty"),
    ({"video_id": "v1", "title": "T", "language": "  "}, "language is empty"),
    ({"video_id": "unknown-video", "title": "T", "language": "en"}, "reserved fallback"),
])
def test_package_cli_rejects_non_string_identity(tmp_path, video, needle) -> None:
    f = _write_pkg_segments(tmp_path, video)
    out = tmp_path / "out"
    r = _run_cli("package", "--segments", str(f), "--out", str(out))
    payload = _assert_identity_failure(r, out)
    assert needle in payload["message"]


def test_package_cli_accepts_valid_unicode_identity(tmp_path) -> None:
    f = _write_pkg_segments(tmp_path, {"video_id": "비디오-1", "title": "한국어 제목", "language": "ko"})
    out = tmp_path / "out"
    r = _run_cli("package", "--segments", str(f), "--out", str(out))
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    pkg = json.loads((out / "residual_package.json").read_text(encoding="utf-8"))
    assert pkg["video"]["video_id"] == "비디오-1"
    assert pkg["video"]["title"] == "한국어 제목"
    assert pkg["video"]["language"] == "ko"


def test_package_cli_accepts_und_language(tmp_path) -> None:
    f = _write_pkg_segments(tmp_path, {"video_id": "v1", "title": "T", "language": "und"})
    out = tmp_path / "out"
    r = _run_cli("package", "--segments", str(f), "--out", str(out))
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    pkg = json.loads((out / "residual_package.json").read_text(encoding="utf-8"))
    assert pkg["video"]["language"] == "und"

