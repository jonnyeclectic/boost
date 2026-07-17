"""Unit tests: boost_cli/core/gitutil.py — the stdlib git wrapper."""
from __future__ import annotations

import re
import subprocess

import pytest

from boost_cli.core import gitutil
from boost_cli.errors import BoostError


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _make_repo(path, author="Test Author"):
    path.mkdir(parents=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@test", cwd=path)
    _git("config", "user.name", author, cwd=path)
    (path / "a.txt").write_text("one\n")
    _git("add", "-A", cwd=path)
    _git("commit", "-qm", "add a", cwd=path)
    return path


class FakeProc:
    def __init__(self, rc=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = rc, stdout, stderr


class TestHasGitAndRun:
    def test_has_git_true_on_real_path(self):
        assert gitutil.has_git() is True

    def test_has_git_false_when_missing(self, monkeypatch):
        monkeypatch.setattr("boost_cli.core.gitutil.shutil.which", lambda n: None)
        assert gitutil.has_git() is False

    def test_run_missing_git_raises_with_brew_hint(self, monkeypatch):
        monkeypatch.setattr("boost_cli.core.gitutil.shutil.which", lambda n: None)
        with pytest.raises(BoostError) as ei:
            gitutil.run(["status"])
        assert ei.value.message == "git is required but was not found on PATH"
        assert "brew install git" in ei.value.hint

    def test_run_happy(self):
        proc = gitutil.run(["--version"])
        assert proc.returncode == 0
        assert proc.stdout.startswith("git version")

    def test_run_check_failure_raises_with_stderr_tail(self, tmp_path):
        with pytest.raises(BoostError) as ei:
            gitutil.run(["rev-parse", "HEAD"], cwd=tmp_path)
        assert ei.value.message.startswith("git rev-parse failed:")
        assert "not a git repository" in ei.value.message.lower()

    def test_run_check_failure_unknown_error(self, monkeypatch):
        monkeypatch.setattr("boost_cli.core.gitutil.subprocess.run",
                            lambda *a, **k: FakeProc(rc=1))
        with pytest.raises(BoostError) as ei:
            gitutil.run(["status"])
        assert ei.value.message == "git status failed: unknown error"

    def test_run_check_false_returns_proc(self, tmp_path):
        proc = gitutil.run(["rev-parse", "HEAD"], cwd=tmp_path, check=False)
        assert proc.returncode != 0

    def test_run_timeout_raises(self, monkeypatch):
        def boom(*a, **k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=7)
        monkeypatch.setattr("boost_cli.core.gitutil.subprocess.run", boom)
        with pytest.raises(BoostError) as ei:
            gitutil.run(["fetch"], timeout=7)
        assert ei.value.message == "git fetch timed out after 7s"


class TestCloneAndInspect:
    def test_clone_shallow_and_head_commit(self, tmp_path, fixture_tap_src):
        dest = tmp_path / "deep" / "nested" / "clone"   # parent auto-created
        gitutil.clone_shallow(str(fixture_tap_src), dest)
        assert (dest / "skills" / "brainstorming" / "SKILL.md").is_file()
        assert gitutil.is_repo(dest) is True
        head = gitutil.head_commit(dest)
        assert re.fullmatch(r"[0-9a-f]{40}", head)
        assert gitutil.remote_url(dest) == str(fixture_tap_src)

    def test_is_repo_false_on_plain_dir(self, tmp_path):
        assert gitutil.is_repo(tmp_path) is False

    def test_head_commit_empty_on_non_repo(self, tmp_path):
        assert gitutil.head_commit(tmp_path) == ""

    def test_remote_url_empty_on_non_repo(self, tmp_path):
        assert gitutil.remote_url(tmp_path) == ""


class TestPull:
    def test_pull_already_up_to_date(self, tmp_path):
        origin = _make_repo(tmp_path / "origin")
        clone = tmp_path / "clone"
        gitutil.clone_shallow(str(origin), clone)
        assert gitutil.pull(clone) == "already up to date"

    def test_pull_new_commit_reports_shas(self, tmp_path):
        origin = _make_repo(tmp_path / "origin")
        clone = tmp_path / "clone"
        gitutil.clone_shallow(str(origin), clone)
        before = gitutil.head_commit(clone)
        (origin / "b.txt").write_text("two\n")
        _git("add", "-A", cwd=origin)
        _git("commit", "-qm", "add b", cwd=origin)

        summary = gitutil.pull(clone)
        after = gitutil.head_commit(clone)
        assert re.fullmatch(r"[0-9a-f]{7} → [0-9a-f]{7}", summary)
        assert summary == "%s → %s" % (before[:7], after[:7])
        assert after == gitutil.head_commit(origin)
        assert after != before


class TestLogForPath:
    def test_line_format(self, tmp_path):
        repo = _make_repo(tmp_path / "repo")
        lines = gitutil.log_for_path(repo)
        assert len(lines) == 1
        assert re.fullmatch(
            r"[0-9a-f]{7,}  \d{4}-\d{2}-\d{2}  Test Author  add a", lines[0])

    def test_path_filtering_and_limit(self, tmp_path):
        repo = _make_repo(tmp_path / "repo")
        sub = repo / "b"
        sub.mkdir()
        (sub / "c.txt").write_text("c\n")
        _git("add", "-A", cwd=repo)
        _git("commit", "-qm", "add c", cwd=repo)

        all_lines = gitutil.log_for_path(repo)
        assert len(all_lines) == 2
        assert all_lines[0].endswith("add c")     # newest first
        assert all_lines[1].endswith("add a")

        only_b = gitutil.log_for_path(repo, "b")
        assert len(only_b) == 1
        assert only_b[0].endswith("add c")

        limited = gitutil.log_for_path(repo, ".", n=1)
        assert len(limited) == 1
        assert limited[0].endswith("add c")

    def test_no_commits_for_path(self, tmp_path):
        repo = _make_repo(tmp_path / "repo")
        assert gitutil.log_for_path(repo, "nonexistent-path") == []
