# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a tap spec's name and URL say what it is, and nothing else.

Three ways a `boost tap` answered for a different repo than the one asked for:
a second local repo with the same basename was reported "already tapped"
(exit 0, nothing tapped); `file://` and `git://` specs were rewritten to
`https://github.com/<spec>` and `.git` was cut from the middle of a name; and a
repo with no commits tapped as "0 items", then failed `boost update` with git's
raw FETCH_HEAD error.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.commands import taps as taps_cmd
from boost_cli.core import config, gitutil, registry
from boost_cli.errors import BoostError


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _repo(path, commit=True):
    (path / "skills" / "a").mkdir(parents=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "t@test", cwd=path)
    _git("config", "user.name", "T", cwd=path)
    (path / "skills" / "a" / "SKILL.md").write_text(
        "---\nname: a\ndescription: A skill\n---\nx\n", encoding="utf-8")
    if commit:
        _git("add", "-A", cwd=path)
        _git("commit", "-qm", "add a", cwd=path)
    return path


def _urls():
    return [t["url"] for t in config.load().get("taps", [])]


class TestSchemeUrls:
    def test_file_url_is_cloned_as_given(self):
        assert registry.parse_spec("file:///srv/repos/fixture-tap") == (
            "repos/fixture-tap", "file:///srv/repos/fixture-tap")

    def test_git_url_is_cloned_as_given(self):
        assert registry.parse_spec("git://example.com/x/y.git") == (
            "x/y", "git://example.com/x/y.git")

    def test_any_scheme_is_a_url(self):
        assert registry.parse_spec("git+ssh://host/x/y")[1] == "git+ssh://host/x/y"

    def test_only_a_trailing_git_suffix_leaves_the_name(self):
        assert registry.parse_spec("https://github.com/foo/my.github.io") == (
            "foo/my.github.io", "https://github.com/foo/my.github.io")

    def test_trailing_git_after_slash(self):
        assert registry.parse_spec("https://github.com/foo/bar.git/")[0] == "foo/bar"

    def test_git_at_keeps_inner_git(self):
        assert registry.parse_spec("git@github.com:foo/x.gitops.git")[0] == \
            "foo/x.gitops"


class TestSameSource:
    @pytest.mark.parametrize("a,b", [
        ("https://github.com/o/r", "https://github.com/o/r.git"),
        ("https://github.com/o/r", "https://github.com/o/r/"),
        ("https://github.com/o/r", "git@github.com:o/r.git"),
        ("https://github.com/o/r", "ssh://git@github.com/o/r"),
        ("https://GitHub.com/O/R", "https://github.com/o/r"),
        ("/srv/a/tap", "/srv/a/tap"),
        # Userinfo is not part of the repository's identity...
        ("https://user@host.example/o/r", "https://host.example/o/r"),
        ("ssh://git@github.com:22/o/r", "ssh://github.com:22/o/r"),
        # ...and a host is case-blind wherever it appears.
        ("https://GIT.CORP/Team/Repo", "https://git.corp/Team/Repo"),
        ("git@GitHub.com:O/R.git", "https://github.com/o/r"),
        ("ssh://git@GitHub.com:22/O/R", "ssh://github.com:22/o/r"),
    ])
    def test_same(self, a, b):
        assert registry.same_source(a, b)

    @pytest.mark.parametrize("a,b", [
        ("https://github.com/o/r", "https://gitlab.com/o/r"),
        ("/srv/a/tap", "/srv/b/tap"),
        ("/srv/A/tap", "/srv/a/tap"),
        ("https://github.com/o/r", "https://github.com/o/r2"),
        # An `@` in the path is not userinfo: cutting at it made every
        # `…/o/r@x` the same as every other, whatever the host.
        ("https://h1.example/o/r@x", "https://h2.example/o/r@x"),
        # Only GitHub's paths are case-blind; a self-hosted forge or a
        # file:// path is the case it was written in.
        ("https://git.corp/Team/Repo", "https://git.corp/team/repo"),
        ("file:///srv/A/tap", "file:///srv/a/tap"),
        ("ssh://git@git.corp:22/Team/Repo", "ssh://git@git.corp:22/team/repo"),
    ])
    def test_different(self, a, b):
        assert not registry.same_source(a, b)


class TestFileUrlOfALocalDirectory:
    """`file://<dir>` is the directory, not a second spelling of a new tap."""

    def test_parses_like_the_bare_path(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        assert registry.parse_spec(a.as_uri()) == \
            registry.parse_spec(str(a)) == ("fixture-tap", str(a.resolve()))

    def test_percent_encoding_and_localhost(self, sandbox):
        a = _repo(sandbox / "my tap")
        spec = a.as_uri().replace("file://", "file://localhost", 1)
        assert "%20" in spec
        assert registry.parse_spec(spec) == ("my tap", str(a.resolve()))

    def test_add_after_bare_path_is_already_configured(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        registry.add(str(a))
        with pytest.raises(BoostError, match="already configured"):
            registry.add(a.as_uri())
        assert _urls() == [str(a.resolve())]

    def test_add_many_after_bare_path_is_skipped(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        registry.add(str(a))
        [res] = registry.add_many([a.as_uri()])
        assert res["skipped"] is True
        assert taps_cmd._skip_if_already_tapped(a.as_uri()) is True

    def test_directory_that_is_not_a_repo_says_so(self, sandbox):
        d = sandbox / "plain"
        d.mkdir()
        with pytest.raises(BoostError, match="is not a git repository"):
            registry.parse_spec(d.as_uri())

    def test_remote_host_is_left_a_url(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        spec = "file://otherhost" + str(a)
        assert registry.parse_spec(spec)[1] == spec


class TestNameTakenByAnotherUrl:
    def test_add_refuses_and_names_the_existing_url(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        b = _repo(sandbox / "b" / "fixture-tap")
        registry.add(str(a))
        with pytest.raises(BoostError) as exc:
            registry.add(str(b))
        assert str(a.resolve()) in exc.value.message
        assert "fixture-tap" in exc.value.message
        assert _urls() == [str(a.resolve())]

    def test_add_same_url_still_says_already_configured(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        registry.add(str(a))
        with pytest.raises(BoostError, match="already configured"):
            registry.add(str(a))

    def test_add_many_reports_conflict_as_a_failure_not_a_skip(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        b = _repo(sandbox / "b" / "fixture-tap")
        registry.add(str(a))
        [res] = registry.add_many([str(b)])
        assert res["ok"] is False
        assert not res.get("skipped")
        assert str(a.resolve()) in res["error"]
        assert _urls() == [str(a.resolve())]

    def test_add_many_same_url_is_still_skipped(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        registry.add(str(a))
        [res] = registry.add_many([str(a)])
        assert res["skipped"] is True

    def test_add_many_conflict_within_one_batch(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        b = _repo(sandbox / "b" / "fixture-tap")
        first, second = registry.add_many([str(a), str(b)])
        assert first["ok"] is True
        assert second["ok"] is False and not second.get("skipped")
        # Nothing held the name before this run, so "already used by" (and
        # the untap advice that goes with it) would be false.
        assert second["error"] == (
            "two specs in this batch both name fixture-tap: %s and %s"
            % (a.resolve(), b.resolve()))
        assert _urls() == [str(a.resolve())]

    def test_add_many_conflict_with_config_says_already_used(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        b = _repo(sandbox / "b" / "fixture-tap")
        registry.add(str(a))
        [res] = registry.add_many([str(b)])
        assert res["error"] == "tap name fixture-tap is already used by %s" \
            % a.resolve()

    def test_add_many_same_spec_twice_in_a_batch_is_skipped(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        first, second = registry.add_many([str(a), str(a)])
        assert first["ok"] is True
        assert second["skipped"] is True

    def test_cli_single_spec_exits_nonzero(self, sandbox, capsys):
        a = _repo(sandbox / "a" / "fixture-tap")
        b = _repo(sandbox / "b" / "fixture-tap")
        assert taps_cmd.cmd_tap([str(a)]) == 0
        with pytest.raises(BoostError) as exc:
            taps_cmd.cmd_tap([str(b)])
        assert str(a.resolve()) in exc.value.message
        assert "already tapped" not in capsys.readouterr().out

    def test_cli_same_spec_is_still_a_muted_skip(self, sandbox, capsys):
        a = _repo(sandbox / "a" / "fixture-tap")
        assert taps_cmd.cmd_tap([str(a)]) == 0
        capsys.readouterr()
        assert taps_cmd.cmd_tap([str(a)]) == 0
        assert "already tapped" in capsys.readouterr().out

    def test_cli_multi_spec_conflict_exits_one(self, sandbox):
        a = _repo(sandbox / "a" / "fixture-tap")
        b = _repo(sandbox / "b" / "fixture-tap")
        c = _repo(sandbox / "c" / "other")
        assert taps_cmd.cmd_tap([str(a)]) == 0
        assert taps_cmd.cmd_tap([str(b), str(c)]) == 1
        assert _urls() == [str(a.resolve()), str(c.resolve())]


class TestRepoWithNoCommits:
    def test_add_refuses_and_leaves_nothing_behind(self, sandbox):
        wip = _repo(sandbox / "wip", commit=False)
        with pytest.raises(BoostError) as exc:
            registry.add(str(wip))
        assert "no commits" in exc.value.message
        assert "commit" in (exc.value.hint or "")
        assert _urls() == []
        assert not registry.Tap("wip", str(wip)).path.exists()

    def test_add_many_reports_it_per_spec(self, sandbox):
        wip = _repo(sandbox / "wip", commit=False)
        [res] = registry.add_many([str(wip)])
        assert res["ok"] is False
        assert "no commits" in res["error"]
        assert _urls() == []
        assert not registry.Tap("wip", str(wip)).path.exists()

    def test_clone_shallow_removes_the_empty_clone(self, sandbox):
        wip = _repo(sandbox / "wip", commit=False)
        dest = sandbox / "dest"
        with pytest.raises(BoostError, match="no commits"):
            gitutil.clone_shallow(str(wip), dest)
        assert not dest.exists()

    def test_pull_of_an_empty_upstream_explains_itself(self, sandbox):
        upstream = _repo(sandbox / "up", commit=False)
        clone = sandbox / "clone"
        clone.mkdir()
        _git("init", "-q", cwd=clone)
        _git("remote", "add", "origin", str(upstream), cwd=clone)
        with pytest.raises(BoostError) as exc:
            gitutil.pull(clone)
        assert "no commits" in exc.value.message
        assert "FETCH_HEAD" not in exc.value.message

    def test_pull_from_empty_to_first_commit_names_both_ends(self, sandbox):
        upstream = _repo(sandbox / "up", commit=False)
        clone = sandbox / "clone"
        clone.mkdir()
        _git("init", "-q", cwd=clone)
        _git("remote", "add", "origin", str(upstream), cwd=clone)
        _git("add", "-A", cwd=upstream)
        _git("commit", "-qm", "first", cwd=upstream)
        summary = gitutil.pull(clone)
        assert summary.startswith("(no commits) → ")
        assert summary.endswith(gitutil.head_commit(clone)[:7])
