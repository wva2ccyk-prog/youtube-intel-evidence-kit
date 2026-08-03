"""Section 10 (corrective): `doctor` status must reflect actual health.

doctor must fail (ok=false, exit 2) when runtime resources are missing, when a
source checkout is missing required ignore rules, or when resources cannot be
resolved at all; installed mode must not fail because repository-only scripts
are absent; missing-resource mode must exit 2.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from youtube_intel.cli import cmd_doctor, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = {"PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "youtube_intel", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def _doctor_payload(monkeypatch, capsys) -> tuple[int, dict]:
    monkeypatch.setattr("youtube_intel.cli.is_source_checkout", lambda: False)
    monkeypatch.setattr("youtube_intel.cli.is_installed_package", lambda: False)
    import argparse
    rc = main(["doctor"])
    return rc, json.loads(capsys.readouterr().out)


def test_healthy_source_checkout_returns_success() -> None:
    result = _run_cli("doctor")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["core"]["runtime_mode"] == "source_checkout"
    assert payload["checks"]["gitignore_safety"]["ok"] is True
    assert payload["checks"]["repository_safety_scripts"]["ok"] is True


def test_missing_source_fixture_returns_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr("youtube_intel.cli.is_source_checkout", lambda: True)
    monkeypatch.setattr("youtube_intel.cli.is_installed_package", lambda: False)
    monkeypatch.setattr("youtube_intel.cli.find_source_root", lambda: REPO_ROOT)
    monkeypatch.setattr("youtube_intel.cli.fixture_path", lambda name: REPO_ROOT / "does-not-exist" / name)
    rc = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["checks"]["runtime_resources"]["ok"] is False


def test_missing_packaged_fixture_returns_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr("youtube_intel.cli.is_source_checkout", lambda: False)
    monkeypatch.setattr("youtube_intel.cli.is_installed_package", lambda: True)
    monkeypatch.setattr("youtube_intel.cli.fixture_path", lambda name: REPO_ROOT / "does-not-exist" / name)
    rc = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["core"]["runtime_mode"] == "installed_package"
    assert payload["checks"]["runtime_resources"]["ok"] is False


def test_missing_required_ignore_entry_fails_in_source_mode(tmp_path, monkeypatch, capsys) -> None:
    fake_root = tmp_path / "repo"
    fake_root.mkdir()
    (fake_root / ".gitignore").write_text("# incomplete\n", encoding="utf-8")
    monkeypatch.setattr("youtube_intel.cli.is_source_checkout", lambda: True)
    monkeypatch.setattr("youtube_intel.cli.is_installed_package", lambda: False)
    monkeypatch.setattr("youtube_intel.cli.find_source_root", lambda: fake_root)
    monkeypatch.setattr("youtube_intel.cli.fixture_path", lambda name: REPO_ROOT / "examples" / name)
    rc = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["checks"]["gitignore_safety"]["ok"] is False
    assert payload["checks"]["gitignore_safety"]["missing"]


def test_installed_mode_does_not_require_repo_only_scripts(monkeypatch, capsys) -> None:
    monkeypatch.setattr("youtube_intel.cli.is_source_checkout", lambda: False)
    monkeypatch.setattr("youtube_intel.cli.is_installed_package", lambda: True)
    monkeypatch.setattr("youtube_intel.cli.fixture_path", lambda name: REPO_ROOT / "examples" / name)
    rc = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["checks"]["repository_safety_scripts"]["not_applicable"] is True
    assert payload["checks"]["gitignore_safety"]["not_applicable"] is True


def test_missing_resource_mode_fails_with_explicit_mocking(monkeypatch, capsys) -> None:
    monkeypatch.setattr("youtube_intel.cli.is_source_checkout", lambda: False)
    monkeypatch.setattr("youtube_intel.cli.is_installed_package", lambda: False)
    rc = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["core"]["runtime_mode"] == "missing_resources"
