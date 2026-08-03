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


# --- P1-G: tracked-file coverage and denylist tracking safety -----------------


def _git_init(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Leak Scan Test"], check=True
    )


def _git_commit_all(tmp_path: Path) -> None:
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "test snapshot"], check=True
    )


def test_leak_scan_covers_tracked_non_allowlist_extensions(tmp_path):
    """Tracked .env / .sh / .ini / .cfg / .jsonl / .html / extensionless files
    must be content-scanned, not skipped by an extension allowlist."""
    _git_init(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")
    (tmp_path / "deploy.sh").write_text("export ACCESS_TOKEN=abc\n", encoding="utf-8")
    (tmp_path / "config.ini").write_text("api_key = sk-123\n", encoding="utf-8")
    (tmp_path / "config.cfg").write_text("cookie=secret\n", encoding="utf-8")
    (tmp_path / "data.jsonl").write_text('{"user": "user@gmail.com"}\n', encoding="utf-8")
    (tmp_path / "page.html").write_text("<p>refresh_token=xyz</p>\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text("deploy:\n\techo bearer_token=abc\n", encoding="utf-8")
    _git_commit_all(tmp_path)
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, result.stdout
    for name in (".env", "deploy.sh", "config.ini", "config.cfg", "data.jsonl", "page.html", "Makefile"):
        assert name in result.stdout, f"{name} was not scanned"


def test_tracked_local_denylist_file_fails_scan(tmp_path):
    """A local denylist file tracked by git must fail the scan."""
    _git_init(tmp_path)
    (tmp_path / ".release_private_denylist.local").write_text("PRIVATE_X\n", encoding="utf-8")
    (tmp_path / "clean.md").write_text("all clean here\n", encoding="utf-8")
    _git_commit_all(tmp_path)
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "local denylist file is tracked" in result.stdout


def test_ignored_local_denylist_file_is_allowed_and_applied(tmp_path):
    """An untracked (gitignored) denylist file must not fail the scan and its
    patterns must still be applied to tracked files."""
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text(
        ".release_private_denylist.local\nprivate_denylist.local\n", encoding="utf-8"
    )
    (tmp_path / ".release_private_denylist.local").write_text("PRIVATE_Y\n", encoding="utf-8")
    (tmp_path / "clean.md").write_text("mentions PRIVATE_Y here\n", encoding="utf-8")
    _git_commit_all(tmp_path)
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, "denylist pattern must still be enforced"
    assert "local_denylist" in result.stdout
    assert "is tracked" not in result.stdout


def test_utf8_decode_failure_does_not_skip_file(tmp_path):
    """A tracked file that fails strict UTF-8 decoding must still be scanned
    (decode with replacement), so a non-UTF-8 file cannot hide patterns."""
    _git_init(tmp_path)
    (tmp_path / "latin1.txt").write_bytes(b"caf\xe9 OPENAI_API_KEY=sk-secret\n")
    _git_commit_all(tmp_path)
    result = subprocess.run(
        [sys.executable, str(LEAK_SCAN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "latin1.txt" in result.stdout
