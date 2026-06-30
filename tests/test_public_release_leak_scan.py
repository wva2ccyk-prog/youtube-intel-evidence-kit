from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

LEAK_SCAN = Path(__file__).resolve().parents[1] / "scripts" / "public_release_leak_scan.py"


def _run_scan_on_text(tmp_path: Path, content: str) -> int:
    f = tmp_path / "test_input.txt"
    f.write_text(content, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    return result.returncode


def test_leak_scan_catches_windows_user_path(tmp_path):
    code = _run_scan_on_text(tmp_path, 'path = "C:\\Users\\test\\file.txt"\n')
    assert code != 0


def test_leak_scan_catches_gmail(tmp_path):
    code = _run_scan_on_text(tmp_path, "contact: user@gmail.com\n")
    assert code != 0


def test_leak_scan_catches_openai_api_key(tmp_path):
    code = _run_scan_on_text(tmp_path, 'OPENAI_API_KEY=sk-abc123\n')
    assert code != 0


def test_leak_scan_catches_pilot_runs(tmp_path):
    code = _run_scan_on_text(tmp_path, "see pilot_runs/ for data\n")
    assert code != 0


def test_leak_scan_allows_clean_synthetic_docs(tmp_path):
    content = (
        "# Synthetic Demo\n\n"
        "This is a synthetic fixture for the opinion terrain demo.\n"
        "Not fact-checked. Not truth-ranked.\n"
    )
    f = tmp_path / "clean.md"
    f.write_text(content, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_leak_scan_catches_pycache_dir(tmp_path):
    d = tmp_path / "__pycache__"
    d.mkdir()
    (d / "x.pyc").write_bytes(b"compiled")
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_leak_scan_catches_pyc_file(tmp_path):
    f = tmp_path / "x.pyc"
    f.write_bytes(b"compiled")
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_leak_scan_does_not_skip_source_files(tmp_path):
    src = tmp_path / "src" / "youtube_mcp_handoff"
    src.mkdir(parents=True)
    f = src / "overlay_service.py"
    f.write_text('bad = "pilot_runs/private_output"\n', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_leak_scan_can_load_local_denylist(tmp_path):
    deny = tmp_path / ".release_private_denylist.local"
    deny.write_text("PRIVATE_TOPIC_X\n", encoding="utf-8")
    f = tmp_path / "clean.md"
    f.write_text("This mentions PRIVATE_TOPIC_X\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
