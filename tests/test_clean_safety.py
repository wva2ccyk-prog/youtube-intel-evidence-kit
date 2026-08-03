"""P1-F: `youtube-intel clean` must never delete arbitrary or dangerous paths.

Every target is resolved before deletion. Filesystem root, user home,
repository root, repository parent, and any path outside the repository are
refused; symlink escapes resolve outside and are refused; non-generated
repository paths require --force; --dry-run deletes nothing; missing paths are
reported, not silently deleted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from youtube_intel.cli import _clean_plan, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "outputs" / "demo").mkdir(parents=True)
    (repo / "notes.txt").write_text("keep me", encoding="utf-8")
    return repo


def test_allowed_generated_path_is_deleted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "outputs" / "demo"
    allowed, missing, refusals = _clean_plan([str(target)], repo_root=repo, force=False)
    assert refusals == []
    assert allowed == [target.resolve()]
    assert missing == []


def test_repository_root_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _, _, refusals = _clean_plan([str(repo)], repo_root=repo, force=True)
    assert any("repository root" in r for r in refusals)


def test_repository_parent_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _, _, refusals = _clean_plan([str(tmp_path)], repo_root=repo, force=True)
    assert any("outside the repository" in r for r in refusals)


def test_outside_workspace_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    _, _, refusals = _clean_plan([str(outside)], repo_root=repo, force=True)
    assert any("outside the repository" in r for r in refusals)


def test_symlink_escape_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    escape_target = tmp_path / "secret"
    escape_target.mkdir()
    link = repo / "outputs" / "escape"
    link.symlink_to(escape_target, target_is_directory=True)
    _, _, refusals = _clean_plan([str(link)], repo_root=repo, force=True)
    assert any("outside the repository" in r for r in refusals), refusals


def test_non_generated_path_requires_force(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _, _, refusals = _clean_plan([str(repo / "notes.txt")], repo_root=repo, force=False)
    assert any("non-generated" in r for r in refusals)
    allowed, _, _ = _clean_plan([str(repo / "notes.txt")], repo_root=repo, force=True)
    assert allowed == [(repo / "notes.txt").resolve()]


def test_missing_path_reported_not_deleted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    missing_path = repo / "outputs" / "ghost"
    allowed, missing, refusals = _clean_plan([str(missing_path)], repo_root=repo, force=False)
    assert refusals == []
    assert allowed == []
    assert missing == [missing_path]


def test_dry_run_deletes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr("youtube_intel.cli._repo_root", lambda: repo)
    target = repo / "outputs" / "demo"
    rc = main(["clean", str(target), "--dry-run"])
    assert rc == 0
    assert target.exists(), "dry-run must not delete anything"
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["would_remove"] == [str(target.resolve())]


def test_clean_refusal_is_structured_and_deletes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr("youtube_intel.cli._repo_root", lambda: repo)
    kept = repo / "outputs" / "demo"
    rc = main(["clean", str(repo), str(kept)])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == "UnsafeCleanTargetError"
    assert any("repository root" in r for r in payload["refusals"])
    assert kept.exists(), "a refused plan must delete nothing"


def test_clean_removes_generated_output(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr("youtube_intel.cli._repo_root", lambda: repo)
    target = repo / "outputs" / "demo"
    rc = main(["clean", str(target)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["removed"] == [str(target.resolve())]
    assert not target.exists()

