# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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
    (path / "a.txt").write_text("one\n", encoding="utf-8")
    _git("add", "-A", cwd=path)
    _git("commit", "-qm", "add a", cwd=path)
    return path


class FakeProc:
    def __init__(self, rc=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = rc, stdout, stderr


def _record_run(monkeypatch, stdout=""):
    """Replace gitutil.run with a recorder returning a fixed FakeProc.

    Returns the list of (args, kwargs) tuples every call appends to, so a test
    can assert the exact git argv the wrapper builds — independent of the host
    filesystem's case sensitivity (which lets HEAD/head, .git/.GIT survive on
    a real repo).
    """
    calls = []

    def rec(args, **kw):
        calls.append((args, kw))
        return FakeProc(rc=0, stdout=stdout)
    monkeypatch.setattr("boost_cli.core.gitutil.run", rec)
    return calls


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

    def test_has_git_queries_the_git_binary_by_name(self, monkeypatch):
        seen = []
        monkeypatch.setattr("boost_cli.core.gitutil.shutil.which",
                            lambda name: seen.append(name) or "/usr/bin/git")
        gitutil.has_git()
        assert seen == ["git"]     # exact binary name, not "GIT"

    def test_run_invokes_git_binary_with_default_timeout(self, monkeypatch):
        calls = []

        def rec(argv, **kw):
            calls.append((argv, kw))
            return FakeProc(rc=0, stdout="ok")
        monkeypatch.setattr("boost_cli.core.gitutil.subprocess.run", rec)
        gitutil.run(["status", "-s"], cwd=None)
        (argv, kw), = calls
        assert argv == ["git", "status", "-s"]     # literal "git", args appended
        assert kw["timeout"] == 300                 # default timeout forwarded
        assert kw["capture_output"] is True and kw["text"] is True

    def test_run_failure_prefers_stdout_when_stderr_empty(self, monkeypatch):
        # stderr empty, stdout carries the real error -> it must reach the message
        monkeypatch.setattr("boost_cli.core.gitutil.subprocess.run",
                            lambda *a, **k: FakeProc(rc=1, stdout="fatal: bad object\n"))
        with pytest.raises(BoostError) as ei:
            gitutil.run(["cat-file", "-p", "deadbeef"])
        assert ei.value.message == "git cat-file failed: fatal: bad object"

    def test_failure_names_the_subcommand_not_a_global_flag(self, monkeypatch):
        """Most calls here are repo-scoped (`-C <path> …`), and taking args[0]
        reported every one of them as `git -C failed` — a flag, not a command."""
        monkeypatch.setattr("boost_cli.core.gitutil.subprocess.run",
                            lambda *a, **k: FakeProc(rc=1, stdout="fatal: nope\n"))
        with pytest.raises(BoostError) as ei:
            gitutil.run(["-C", "/some/repo", "fetch", "--depth", "1", "origin"])
        assert ei.value.message == "git fetch failed: fatal: nope"

    def test_failure_skips_dash_c_config_pairs_too(self, monkeypatch):
        monkeypatch.setattr("boost_cli.core.gitutil.subprocess.run",
                            lambda *a, **k: FakeProc(rc=1, stdout="fatal: nope\n"))
        with pytest.raises(BoostError) as ei:
            gitutil.run(["-c", "user.name=x", "commit", "-m", "y"])
        assert ei.value.message == "git commit failed: fatal: nope"

    def test_failure_on_an_all_flag_argv_still_says_git(self, monkeypatch):
        monkeypatch.setattr("boost_cli.core.gitutil.subprocess.run",
                            lambda *a, **k: FakeProc(rc=1, stdout="fatal: nope\n"))
        with pytest.raises(BoostError) as ei:
            gitutil.run(["--version"])
        assert ei.value.message == "git failed: fatal: nope"


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

    def test_clone_shallow_issues_exact_argv(self, tmp_path, monkeypatch):
        calls = _record_run(monkeypatch)
        gitutil.clone_shallow("git@example:x.git", tmp_path / "d", sparse=False)
        (args, kw), = calls
        assert args == ["clone", "--depth", "1", "--quiet",
                        "-c", "core.autocrlf=false", "-c", "core.eol=lf", "--",
                        "git@example:x.git", str(tmp_path / "d")]
        assert kw.get("timeout") == 600     # long clone timeout, not the 300 default

    def test_sparse_clone_issues_exact_argv(self, tmp_path, monkeypatch):
        """The default: same flags plus the blobless/sparse pair, then the cone."""
        calls = _record_run(monkeypatch)
        gitutil.clone_shallow("git@example:x.git", tmp_path / "d")
        (clone_args, kw), (cone_args, _) = calls
        assert clone_args == ["clone", "--depth", "1", "--quiet",
                              "-c", "core.autocrlf=false", "-c", "core.eol=lf",
                              "--filter=blob:none", "--sparse", "--",
                              "git@example:x.git", str(tmp_path / "d")]
        assert kw.get("timeout") == 600
        assert cone_args == ["-C", str(tmp_path / "d"), "sparse-checkout",
                             "set", "--no-cone", *gitutil.SPARSE_PATTERNS]

    def test_clone_shallow_puts_end_of_options_before_url(self, tmp_path,
                                                          monkeypatch):
        # a URL beginning with `-` must be a positional, never a git flag
        calls = _record_run(monkeypatch)
        gitutil.clone_shallow("--upload-pack=evil", tmp_path / "d")
        args, _kw = calls[0]
        assert "--" in args and args.index("--") < args.index("--upload-pack=evil")

    @pytest.mark.parametrize("bad", [
        "ext::sh -c evil", "file::/etc/passwd", "fd::7",
        "EXT::sh -c evil",           # case-insensitive
        "  ext::sh -c evil",         # leading whitespace stripped first
    ])
    def test_clone_shallow_rejects_unsafe_transports(self, tmp_path, monkeypatch,
                                                     bad):
        calls = _record_run(monkeypatch)
        with pytest.raises(BoostError) as ei:
            gitutil.clone_shallow(bad, tmp_path / "d")
        assert "unsafe git transport" in ei.value.message
        assert calls == []           # git is never invoked for a rejected URL

    def test_clone_shallow_allows_ordinary_https(self, tmp_path, monkeypatch):
        calls = _record_run(monkeypatch)
        gitutil.clone_shallow("https://github.com/o/r", tmp_path / "d")
        # a normal remote clones, not rejected: the clone, then its sparse cone
        assert len(calls) == 2
        assert calls[0][0][0] == "clone"
        assert "sparse-checkout" in calls[1][0]

    def test_head_commit_argv_is_rev_parse_head(self, tmp_path, monkeypatch):
        calls = _record_run(monkeypatch, stdout="c0ffee\n")
        assert gitutil.head_commit(tmp_path / "r") == "c0ffee"
        (args, kw), = calls
        assert args == ["-C", str(tmp_path / "r"), "rev-parse", "HEAD"]
        assert kw.get("check") is False     # non-fatal: empty string on failure

    def test_remote_url_argv_is_remote_get_url_origin(self, tmp_path, monkeypatch):
        calls = _record_run(monkeypatch, stdout="https://x/y\n")
        assert gitutil.remote_url(tmp_path / "r") == "https://x/y"
        (args, kw), = calls
        assert args == ["-C", str(tmp_path / "r"), "remote", "get-url", "origin"]
        assert kw.get("check") is False


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
        (origin / "b.txt").write_text("two\n", encoding="utf-8")
        _git("add", "-A", cwd=origin)
        _git("commit", "-qm", "add b", cwd=origin)

        summary = gitutil.pull(clone)
        after = gitutil.head_commit(clone)
        assert re.fullmatch(r"[0-9a-f]{7} → [0-9a-f]{7}", summary)
        assert summary == "%s → %s" % (before[:7], after[:7])
        assert after == gitutil.head_commit(origin)
        assert after != before

    def test_pull_issues_reset_sequence_and_falls_back_to_fetch_head(
            self, tmp_path, monkeypatch):
        # Drive pull() through a recorder so the exact git argv is asserted.
        # rev-parse returns the SAME sha before and after the origin/HEAD reset,
        # which forces the FETCH_HEAD fallback branch; the final rev-parse moves.
        shas = iter(["a" * 40, "a" * 40, "b" * 40])
        calls = []

        def rec(args, **kw):
            calls.append((args, kw))
            out = next(shas) + "\n" if "rev-parse" in args else ""
            return FakeProc(rc=0, stdout=out)
        monkeypatch.setattr("boost_cli.core.gitutil.run", rec)

        repo = tmp_path / "clone"
        summary = gitutil.pull(repo)
        assert summary == "aaaaaaa → bbbbbbb"

        argvs = [a for a, _ in calls]
        # every subcommand targets the given repo, never str(None)
        assert all(a[1] == str(repo) for a in argvs)
        assert ["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"] in argvs
        # the origin/HEAD reset is non-fatal (check=False), exact tokens
        oh = ["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"]
        assert oh in argvs
        assert calls[[a for a, _ in calls].index(oh)][1].get("check") is False
        # fallback fired: FETCH_HEAD reset must be present
        assert ["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"] in argvs

    def test_pull_skips_fallback_when_origin_head_moves(self, tmp_path, monkeypatch):
        # When the origin/HEAD reset already advances HEAD, the FETCH_HEAD
        # fallback must NOT run (guards the == before condition, not !=).
        shas = iter(["a" * 40, "b" * 40, "b" * 40])
        calls = []

        def rec(args, **kw):
            calls.append(args)
            out = next(shas) + "\n" if "rev-parse" in args else ""
            return FakeProc(rc=0, stdout=out)
        monkeypatch.setattr("boost_cli.core.gitutil.run", rec)

        gitutil.pull(tmp_path / "clone")
        assert not any("FETCH_HEAD" in a for a in calls)


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
        (sub / "c.txt").write_text("c\n", encoding="utf-8")
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

    def test_log_for_path_argv_forwards_path_and_limit(self, tmp_path, monkeypatch):
        calls = _record_run(monkeypatch, stdout="")
        gitutil.log_for_path(tmp_path / "r", "sub/dir", n=5)
        (args, kw), = calls
        assert args == ["-C", str(tmp_path / "r"), "log", "--date=short",
                        "-n", "5", "--pretty=format:%h  %ad  %an  %s",
                        "--", "sub/dir"]
        assert kw.get("check") is False

    def test_log_for_path_defaults_to_twenty_entries(self, tmp_path, monkeypatch):
        calls = _record_run(monkeypatch, stdout="")
        gitutil.log_for_path(tmp_path / "r")           # no n= -> default cap
        (args, _), = calls
        assert args[args.index("-n") + 1] == "20"      # default limit, not 21
        assert args[-1] == "."                         # default rel_path
