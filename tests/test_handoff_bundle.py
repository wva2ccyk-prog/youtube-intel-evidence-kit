"""P0-E + P0-D (handoff): handoff manifest persistence, fail-closed empty-input
behavior, and Section 5 structural/coherence validation.

P0-E regression: ``write_handoff_bundle`` used to write ``handoff_manifest.json``
BEFORE adding the manifest's own path to the in-memory ``paths`` object, so the
returned manifest and the on-disk manifest were different documents. The
manifest must now be fully constructed (including its own path) and then
written.

Section 5: a handoff bundle must not report success unless its supplied
artifacts are structurally valid (schema version, identity, claims) and
mutually coherent (matching video identity, resolving source-trace claim ids).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from youtube_intel.analysis_worth import build_analysis_worth
from youtube_intel.errors import InvalidInputError
from youtube_intel.reporting import write_handoff_bundle
from youtube_residual import build_residual_package

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


def _real_package() -> dict:
    package = build_residual_package(
        video_id="sample-video",
        title="Sample Video Title",
        language="en",
        segments=[{"text": "A real sample segment for the handoff test.", "speaker": "A"}],
    )
    return package.to_dict()


def _real_worth(video_id: str | None = None, title: str | None = None) -> dict:
    package = build_residual_package(
        video_id=video_id or "sample-video",
        title=title or "Sample Video Title",
        language="en",
        segments=[{"text": "A real sample segment for the handoff test.", "speaker": "A"}],
    )
    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory() as td:
        package_path = Path(td) / "residual_package.json"
        package_path.write_text(json.dumps(package.to_dict()), encoding="utf-8")
        result = build_analysis_worth(package_path=package_path)
    return result


def _sample_inputs() -> tuple[dict, dict]:
    return _real_package(), _real_worth()


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


def test_manifest_marks_bundle_completeness(tmp_path: Path) -> None:
    package, worth = _sample_inputs()
    returned = write_handoff_bundle(tmp_path, package=package, worth=worth)
    assert returned["bundle_completeness"] == "complete"


def test_handoff_rejects_empty_inputs_library_level(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="residual package"):
        write_handoff_bundle(tmp_path)
    with pytest.raises(InvalidInputError, match="residual package"):
        write_handoff_bundle(tmp_path, package={}, worth={})
    assert not (tmp_path / "handoff_manifest.json").exists()


def test_handoff_cli_rejects_missing_inputs_with_exit_2(tmp_path: Path) -> None:
    result = _run_cli("handoff", "--out", str(tmp_path / "out"))
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert "residual package" in payload["message"]
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
    assert result.returncode == 0, result.stderr
    stdout_manifest = json.loads(result.stdout)
    on_disk = json.loads((out / "handoff_manifest.json").read_text(encoding="utf-8"))
    assert stdout_manifest == on_disk


# --- Section 5: structural and coherence validation ---------------------------


def test_arbitrary_junk_package_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="residual package is not structurally valid"):
        write_handoff_bundle(tmp_path, package={"junk": True}, worth=_real_worth())


def test_arbitrary_junk_worth_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="analysis-worth artifact is not structurally valid"):
        write_handoff_bundle(tmp_path, package=_real_package(), worth={"junk": True})


def test_package_and_worth_with_different_video_ids_fail(tmp_path: Path) -> None:
    worth = _real_worth(video_id="other-video", title="Other Video Title")
    with pytest.raises(InvalidInputError, match="video_id mismatch"):
        write_handoff_bundle(tmp_path, package=_real_package(), worth=worth)


def test_duplicate_claim_ids_in_package_fail(tmp_path: Path) -> None:
    package = _real_package()
    package["claim_candidates"] = [
        {"claim_id": "C0001", "text": "first"},
        {"claim_id": "C0001", "text": "second"},
    ]
    with pytest.raises(InvalidInputError, match="residual package is not structurally valid"):
        write_handoff_bundle(tmp_path, package=package, worth=_real_worth())


def test_dangling_source_trace_claim_id_fails(tmp_path: Path) -> None:
    worth = _real_worth()
    worth["source_trace"] = [{"claim_id": "GHOST-ID", "time_ref": "00:00", "evidence": "unclear", "confidence": "low"}]
    with pytest.raises(InvalidInputError, match="source_trace claim_id does not resolve"):
        write_handoff_bundle(tmp_path, package=_real_package(), worth=worth)


def test_valid_package_and_worth_pair_succeeds(tmp_path: Path) -> None:
    package, worth = _sample_inputs()
    returned = write_handoff_bundle(tmp_path, package=package, worth=worth)
    assert returned["ok"] is True
    assert (tmp_path / "handoff_manifest.json").is_file()


def test_no_files_written_when_validation_fails(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError):
        write_handoff_bundle(tmp_path, package={"junk": True}, worth={"junk": True})
    assert list(tmp_path.iterdir()) == [], "no files may be written before validation succeeds"
