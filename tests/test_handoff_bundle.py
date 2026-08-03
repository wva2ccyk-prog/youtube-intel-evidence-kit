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


def test_source_trace_non_dict_row_cannot_bypass_validation(tmp_path) -> None:
    worth = _real_worth()
    worth["source_trace"] = ["not-a-dict"]
    with pytest.raises(InvalidInputError, match="source_trace row 0 is not an object"):
        write_handoff_bundle(tmp_path, package=_real_package(), worth=worth)


def test_source_trace_empty_claim_id_row_cannot_bypass_validation(tmp_path) -> None:
    worth = _real_worth()
    worth["source_trace"] = [{"claim_id": "", "time_ref": "00:00", "evidence": "unclear", "confidence": "low"}]
    with pytest.raises(InvalidInputError, match="source_trace row 0 claim_id is empty"):
        write_handoff_bundle(tmp_path, package=_real_package(), worth=worth)


def test_source_trace_malformed_row_among_valid_ones_fails(tmp_path) -> None:
    worth = _real_worth()
    valid_ids = [c["claim_id"] for c in _real_package()["claim_candidates"]]
    worth["source_trace"] = [
        {"claim_id": valid_ids[0], "time_ref": "00:00", "evidence": "unclear", "confidence": "low"},
        42,
    ]
    with pytest.raises(InvalidInputError, match="source_trace row 1 is not an object"):
        write_handoff_bundle(tmp_path, package=_real_package(), worth=worth)


# --- Third pass (Defect 5): complete handoff identity and source-trace ---------


def _full_cli_inputs(tmp_path: Path, *, package=None, worth=None, title=None) -> tuple[Path, Path]:
    pkg = package if package is not None else _real_package()
    wr = worth if worth is not None else _real_worth()
    if title:
        pkg["video"]["title"] = title
        wr["video"]["title"] = title
    package_path = tmp_path / "pkg.json"
    package_path.write_text(json.dumps(pkg), encoding="utf-8")
    worth_path = tmp_path / "worth.json"
    worth_path.write_text(json.dumps(wr), encoding="utf-8")
    return package_path, worth_path


def _run_handoff_cli(tmp_path: Path, package_path: Path, worth_path: Path, out: Path) -> subprocess.CompletedProcess:
    return _run_cli(
        "handoff",
        "--package", str(package_path),
        "--analysis-worth", str(worth_path),
        "--out", str(out),
    )


def _assert_handoff_cli_failure(result: subprocess.CompletedProcess, out: Path) -> dict:
    assert result.returncode == 2, f"stdout={result.stdout} stderr={result.stderr}"
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "InvalidInputError"
    assert not (out / "handoff_manifest.json").exists()
    assert not (out / "operator_summary.md").exists()
    assert not (out / "ai_handoff_prompt.md").exists()
    return payload


def test_handoff_missing_worth_title(tmp_path) -> None:
    worth = _real_worth()
    del worth["video"]["title"]
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    payload = _assert_handoff_cli_failure(r, out)
    assert "title" in payload["message"]


def test_handoff_blank_worth_title(tmp_path) -> None:
    worth = _real_worth()
    worth["video"]["title"] = "   "
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    _assert_handoff_cli_failure(r, out)


def test_handoff_title_mismatch(tmp_path) -> None:
    package, wfile = _full_cli_inputs(tmp_path, title="Mismatch Title")
    worth = json.loads(wfile.read_text(encoding="utf-8"))
    worth["video"]["title"] = "Different Title"
    wfile.write_text(json.dumps(worth), encoding="utf-8")
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    payload = _assert_handoff_cli_failure(r, out)
    assert "title mismatch" in payload["message"]


def _trace_good() -> list[dict]:
    return [
        {
            "claim_id": "C0001",
            "time_ref": None,
            "evidence": "video_internal",
            "confidence": "medium",
            "claim_type": "other",
            "excerpt": "A real sample segment for the handoff test.",
        }
    ]


def test_handoff_whitespace_trace_claim_id(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0]["claim_id"] = "  "
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    _assert_handoff_cli_failure(r, out)


def test_handoff_duplicate_trace_claim_id(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace.append(dict(trace[0]))
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    payload = _assert_handoff_cli_failure(r, out)
    assert "duplicate claim_id" in payload["message"]


def test_handoff_missing_time_ref_key(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0].pop("time_ref")
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    # Missing time_ref is allowed when the source claim has no time coordinate
    # (Option B). This row resolves: package C0001 here has time_ref? _real_package
    # uses segments without time_ref, so the claim time_ref is None -> allows null.
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


def test_handoff_invalid_time_ref_type(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0]["time_ref"] = ["not-a-string"]
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    payload = _assert_handoff_cli_failure(r, out)
    assert "time_ref" in payload["message"]


def test_handoff_trace_time_mismatch(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0]["time_ref"] = "01:30"
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"


def test_handoff_missing_evidence_field(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0].pop("evidence")
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    _assert_handoff_cli_failure(r, out)


def test_handoff_blank_evidence_field(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0]["evidence"] = "  "
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    _assert_handoff_cli_failure(r, out)


def test_handoff_missing_confidence_field(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0].pop("confidence")
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    _assert_handoff_cli_failure(r, out)


def test_handoff_blank_confidence_field(tmp_path) -> None:
    worth = _real_worth()
    trace = _trace_good()
    trace[0]["confidence"] = " "
    worth["source_trace"] = trace
    package, wfile = _full_cli_inputs(tmp_path, worth=worth)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    _assert_handoff_cli_failure(r, out)


def test_handoff_valid_complete_trace_succeeds(tmp_path) -> None:
    package, wfile = _full_cli_inputs(tmp_path)
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package, wfile, out)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert (out / "handoff_manifest.json").exists()

def test_handoff_trace_time_mismatch_when_source_has_time_ref(tmp_path) -> None:
    pkg = _real_package()
    pkg["claim_candidates"][0]["time_ref"] = "00:05"
    worth = _real_worth()
    worth["source_trace"][0]["time_ref"] = "99:99"
    wid = worth["source_trace"][0]["claim_id"]
    # keep coherence
    package_path = tmp_path / "pkg.json"
    package_path.write_text(json.dumps(pkg), encoding="utf-8")
    worth_path = tmp_path / "worth.json"
    worth_path.write_text(json.dumps(worth), encoding="utf-8")
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package_path, worth_path, out)
    payload = _assert_handoff_cli_failure(r, out)
    assert "time_ref does not match source claim" in payload["message"]


def test_handoff_trace_evidence_mismatch_with_source_claim(tmp_path) -> None:
    pkg = _real_package()
    pkg["claim_candidates"][0]["evidence"] = "field_observation"
    worth = _real_worth()
    worth["source_trace"][0]["evidence"] = "source_contradiction"
    package_path = tmp_path / "pkg.json"
    package_path.write_text(json.dumps(pkg), encoding="utf-8")
    worth_path = tmp_path / "worth.json"
    worth_path.write_text(json.dumps(worth), encoding="utf-8")
    out = tmp_path / "out"
    r = _run_handoff_cli(tmp_path, package_path, worth_path, out)
    payload = _assert_handoff_cli_failure(r, out)
    assert "does not match source claim" in payload["message"]
