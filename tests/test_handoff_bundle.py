"""P0-E + P0-D (handoff): single-video handoff manifest persistence and
fail-closed empty-input behavior.

P0-E regression: ``write_handoff_bundle`` used to write ``handoff_manifest.json``
BEFORE adding the manifest's own path to the in-memory ``paths`` object, so the
returned manifest and the on-disk manifest were different documents. The
manifest must now be fully constructed (including its own path) and then
written.

P0-D (handoff): an empty or incoherent input set must not produce a successful
empty bundle; it raises ``InvalidInputError`` and the CLI renders exit code 2
with structured ``{"ok": false, "error": "InvalidInputError", ...}``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from youtube_intel.errors import InvalidInputError
from youtube_intel.reporting import write_handoff_bundle

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


def _sample_inputs() -> tuple[dict, dict]:
    package = {
        "schema_version": "youtube_residual_package.v0.1",
        "video_id": "sample-video",
        "segments": [{"text": "A sample segment.", "speaker": "A"}],
    }
    worth = {"analysis_worth": "yes", "decision": {"analysis_worth": "yes"}}
    return package, worth


def test_returned_manifest_equals_on_disk_manifest(tmp_path: Path) -> None:
    """P0-E: the returned manifest and the persisted manifest must be identical."""
    package, worth = _sample_inputs()
    returned = write_handoff_bundle(tmp_path, package=package, worth=worth)
    manifest_path = tmp_path / "handoff_manifest.json"
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == returned
    assert returned["paths"]["manifest_json"] == str(manifest_path)


def test_every_manifest_path_exists_on_success(tmp_path: Path) -> None:
    package, worth = _sample_inputs()
    returned = write_handoff_bundle(tmp_path, package=package, worth=worth)
    assert returned["ok"] is True
    for key, path_text in returned["paths"].items():
        assert Path(path_text).is_file(), f"missing artifact: {key} -> {path_text}"


def test_handoff_rejects_empty_inputs_library_level(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="coherent input set"):
        write_handoff_bundle(tmp_path)
    with pytest.raises(InvalidInputError, match="coherent input set"):
        write_handoff_bundle(tmp_path, package={}, worth={})
    # Nothing may be written on refusal.
    assert not (tmp_path / "handoff_manifest.json").exists()


def test_handoff_cli_rejects_missing_inputs_with_exit_2(tmp_path: Path) -> None:
    """P0-D: `handoff` without any input fails closed: exit 2, ok:false,
    structured JSON, no manifest written."""
    result = _run_cli("handoff", "--out", str(tmp_path / "out"))
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert "coherent input set" in payload["message"]
    assert not (tmp_path / "out" / "handoff_manifest.json").exists()


def test_handoff_cli_persisted_manifest_equals_stdout_manifest(tmp_path: Path) -> None:
    out = tmp_path / "out"
    package_path = tmp_path / "residual_package.json"
    worth_path = tmp_path / "analysis_worth.json"
    package, worth = _sample_inputs()
    package_path.write_text(json.dumps(package), encoding="utf-8")
    worth_path.write_text(json.dumps(worth), encoding="utf-8")
    result = _run_cli(
        "handoff",
        "--package", str(package_path),
        "--analysis-worth", str(worth_path),
        "--out", str(out),
    )
    assert result.returncode == 0
    stdout_manifest = json.loads(result.stdout)
    on_disk = json.loads((out / "handoff_manifest.json").read_text(encoding="utf-8"))
    assert stdout_manifest == on_disk
