"""P1-F + Section 7: `youtube-intel clean` must never delete arbitrary or
dangerous paths, must be safe in installed-wheel environments, and must never
delete protected source directories even with --force.

Every target is resolved before deletion. Filesystem root, user home,
repository root, repository parent, outside paths, and symlink escapes are
refused; non-generated repository paths require --force; --dry-run deletes
nothing; missing paths are reported. When no source checkout is detected
(installed wheel), clean fails closed and deletes nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from youtube_intel.cli import _clean_plan, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "outputs" / "demo").mkdir(parents=True)
    (repo / "notes.txt").write_text("keep me", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "schemas").mkdir()
    (repo / ".github").mkdir()
    (repo / ".git").mkdir()
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


def test_directory_symlink_escape_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    escape_target = tmp_path / "secret"
    escape_target.mkdir()
    link = repo / "outputs" / "escape"
    link.symlink_to(escape_target, target_is_directory=True)
    _, _, refusals = _clean_plan([str(link)], repo_root=repo, force=True)
    assert any("outside the repository" in r for r in refusals), refusals


def test_file_symlink_escape_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    link = repo / "outputs" / "secret-link"
    link.symlink_to(outside_file)
    _, _, refusals = _clean_plan([str(link)], repo_root=repo, force=True)
    assert any("outside the repository" in r for r in refusals), refusals


def test_broken_symlink_reported_not_deleted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    link = repo / "outputs" / "broken"
    link.symlink_to(tmp_path / "does-not-exist-anywhere")
    # A broken symlink resolves to its (outside-repo) target, so it is refused
    # rather than deleted; the symlink itself must remain untouched.
    allowed, missing, refusals = _clean_plan([str(link)], repo_root=repo, force=True)
    assert any("outside the repository" in r for r in refusals), refusals
    assert allowed == []
    assert link.is_symlink(), "broken symlink itself must remain untouched"


def test_mixed_allowed_and_refused_delete_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr("youtube_intel.cli.find_source_root", lambda: repo)
    kept = repo / "outputs" / "demo"
    rc = main(["clean", str(repo / "src"), str(kept)])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert kept.exists(), "a refused plan must delete nothing"


def test_non_generated_path_requires_force(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _, _, refusals = _clean_plan([str(repo / "notes.txt")], repo_root=repo, force=False)
    assert any("non-generated" in r for r in refusals)
    allowed, _, _ = _clean_plan([str(repo / "notes.txt")], repo_root=repo, force=True)
    assert allowed == [(repo / "notes.txt").resolve()]


def test_force_cannot_delete_protected_source_dirs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    for protected in ("src", ".git", "tests", "schemas", ".github"):
        _, _, refusals = _clean_plan([str(repo / protected)], repo_root=repo, force=True)
        assert any("protected source directory" in r for r in refusals), (
            f"--force must not allow deleting {protected}/"
        )


def test_missing_path_reported_not_deleted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    missing_path = repo / "outputs" / "ghost"
    allowed, missing, refusals = _clean_plan([str(missing_path)], repo_root=repo, force=False)
    assert refusals == []
    assert allowed == []
    assert missing == [missing_path]


def test_dry_run_deletes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr("youtube_intel.cli.find_source_root", lambda: repo)
    target = repo / "outputs" / "demo"
    rc = main(["clean", str(target), "--dry-run"])
    assert rc == 0
    assert target.exists(), "dry-run must not delete anything"
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["would_remove"] == [str(target.resolve())]


def test_clean_refusal_is_structured_and_deletes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr("youtube_intel.cli.find_source_root", lambda: repo)
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
    monkeypatch.setattr("youtube_intel.cli.find_source_root", lambda: repo)
    target = repo / "outputs" / "demo"
    rc = main(["clean", str(target)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["removed"] == [str(target.resolve())]
    assert not target.exists()


def test_clean_fails_closed_in_installed_wheel(tmp_path: Path, monkeypatch, capsys) -> None:
    """Section 7: an installed wheel has no detected source checkout, so clean
    must refuse everything (exit 2) and delete nothing."""
    monkeypatch.setattr("youtube_intel.cli.find_source_root", lambda: None)
    target = tmp_path / "some-target"
    target.mkdir()
    rc = main(["clean", str(target)])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "source checkout" in payload["message"]
    assert target.exists(), "installed-wheel clean must delete nothing"
