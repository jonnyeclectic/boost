# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""When a skill's files last changed, read from a tap clone's history.

A tap is cloned ``--depth 1``, and there ``git log -1 -- <dir>`` does not fail:
it names the one commit the clone has, for every dir. On a real
``anthropics/skills`` clone that gave all three skills tried the HEAD date,
where the full history gave three different ones. So a date read at a graft
point is no date, and these tests pin that, the real dates once the clone is
deepened, and that updating a deepened clone keeps it deep.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from boost_cli.core import gitutil

#: Committer times for the fixture's two commits: 2020-01-01 and 2021-01-01.
OLD, NEW = 1577836800, 1609459200


def _git(*args, cwd, when=None):
    env = os.environ.copy()
    if when is not None:
        stamp = "@%d +0000" % when
        env |= {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, env=env)


def _commit(repo, rel, when):
    f = repo / rel / "SKILL.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# %s %d\n" % (rel, when), encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "touch %s" % rel, cwd=repo, when=when)


@pytest.fixture()
def tap(tmp_path):
    """A repo whose ``skills/a`` changed in 2020 and ``skills/b`` in 2021."""
    repo = tmp_path / "src"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "t@test", cwd=repo)
    _git("config", "user.name", "T", cwd=repo)
    # Without it a file:// fetch drops --filter with a warning, and the test
    # would not exercise the blobless fetch a real tap makes.
    _git("config", "uploadpack.allowFilter", "true", cwd=repo)
    _commit(repo, "skills/a", OLD)
    _commit(repo, "skills/b", NEW)
    return repo


def _shallow_clone(src, dest):
    # A path clone ignores --depth; a file:// URL is what honours it.
    _git("clone", "-q", "--depth", "1", "--filter=blob:none", src.as_uri(),
         str(dest), cwd=src.parent)
    return dest


class TestPathUpdatedAt:
    def test_each_dir_gets_its_own_date(self, tap):
        assert gitutil.path_updated_at(tap, "skills/a") == OLD
        assert gitutil.path_updated_at(tap, "skills/b") == NEW

    def test_the_root_gets_the_newest(self, tap):
        assert gitutil.path_updated_at(tap, ".") == NEW
        assert gitutil.path_updated_at(tap) == NEW

    def test_at_a_named_revision(self, tap):
        first = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"],
                               cwd=tap, capture_output=True, text=True,
                               check=True).stdout.strip()
        assert gitutil.path_updated_at(tap, ".", rev=first) == OLD
        assert gitutil.path_updated_at(tap, "skills/b", rev=first) is None

    def test_an_empty_revision_means_head(self, tap):
        assert gitutil.path_updated_at(tap, "skills/b", rev="") == NEW

    def test_a_dir_no_commit_touched(self, tap):
        assert gitutil.path_updated_at(tap, "skills/nope") is None

    def test_an_unknown_revision(self, tap):
        assert gitutil.path_updated_at(tap, ".", rev="f" * 40) is None

    def test_not_a_repo(self, tmp_path):
        assert gitutil.path_updated_at(tmp_path) is None

    def test_a_shallow_clone_has_no_date(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        assert gitutil.is_shallow(clone)
        # The graft point "touched" both dirs; neither date can be trusted.
        assert gitutil.path_updated_at(clone, "skills/a") is None
        assert gitutil.path_updated_at(clone, "skills/b") is None

    def test_a_dir_inside_a_shallow_clone_too(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        assert gitutil.path_updated_at(clone / "skills", "b") is None

    def test_a_commit_past_the_graft_point_is_a_real_date(self, tap, tmp_path):
        _commit(tap, "skills/a", NEW + 100)
        clone = tmp_path / "clone"
        _git("clone", "-q", "--depth", "2", tap.as_uri(), str(clone),
             cwd=tmp_path)
        assert gitutil.is_shallow(clone)
        assert gitutil.path_updated_at(clone, "skills/a") == NEW + 100
        assert gitutil.path_updated_at(clone, "skills/b") is None

    def test_the_graft_list_is_found_through_a_dot_git_file(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        wt = tmp_path / "wt"
        _git("worktree", "add", "-q", "--detach", str(wt), cwd=clone)
        assert (wt / ".git").is_file()
        assert gitutil.path_updated_at(wt, "skills/b") is None


class TestUnshallow:
    def test_deepens_a_shallow_clone(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        assert gitutil.unshallow(clone) is True
        assert not gitutil.is_shallow(clone)
        assert gitutil.path_updated_at(clone, "skills/a") == OLD
        assert gitutil.path_updated_at(clone, "skills/b") == NEW

    def test_a_complete_clone_is_left_alone(self, tap, monkeypatch):
        monkeypatch.setattr(gitutil, "run", lambda *a, **k: pytest.fail("ran"))
        assert gitutil.unshallow(tap) is True

    def test_a_failed_fetch_is_false_and_raises_nothing(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        _git("remote", "set-url", "origin", (tmp_path / "gone").as_uri(),
             cwd=clone)
        assert gitutil.unshallow(clone) is False
        assert gitutil.is_shallow(clone)

    def test_a_fetch_that_leaves_it_shallow_is_false(self, tap, tmp_path,
                                                     monkeypatch):
        clone = _shallow_clone(tap, tmp_path / "clone")
        monkeypatch.setattr(gitutil, "run",
                            lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
        assert gitutil.unshallow(clone) is False

    def test_the_fetch_has_its_own_short_timeout(self, tap, tmp_path, monkeypatch):
        clone = _shallow_clone(tap, tmp_path / "clone")
        seen = []

        def rec(args, **kw):
            seen.append(kw.get("timeout"))
            return subprocess.CompletedProcess(args, 0, "", "")
        monkeypatch.setattr(gitutil, "run", rec)
        gitutil.unshallow(clone)
        assert seen == [gitutil.UNSHALLOW_TIMEOUT] and gitutil.UNSHALLOW_TIMEOUT == 60

    def test_a_timed_out_fetch_is_false(self, tap, tmp_path, monkeypatch):
        clone = _shallow_clone(tap, tmp_path / "clone")

        def boom(*a, **k):
            raise gitutil.BoostError("git fetch timed out after 60s")
        monkeypatch.setattr(gitutil, "run", boom)
        assert gitutil.unshallow(clone) is False

    def test_a_timed_out_fetch_leaves_no_shallow_lock(self, tap, tmp_path,
                                                      monkeypatch):
        # A killed `fetch --unshallow` leaves .git/shallow.lock, and every
        # later fetch of that tap then dies "Unable to create ... File exists".
        clone = _shallow_clone(tap, tmp_path / "clone")
        lock = clone / ".git" / "shallow.lock"
        real = gitutil.run

        def killed(args, **kw):
            if "--unshallow" in args:
                lock.write_text("", encoding="utf-8")
                raise gitutil.BoostError("git fetch timed out after 60s")
            return real(args, **kw)
        monkeypatch.setattr(gitutil, "run", killed)
        assert gitutil.unshallow(clone) is False
        assert not lock.exists()
        _commit(tap, "skills/a", NEW + 100)
        gitutil.pull(clone)            # the next update still fetches

    def test_a_lock_held_before_the_fetch_is_not_removed(self, tap, tmp_path,
                                                         monkeypatch):
        clone = _shallow_clone(tap, tmp_path / "clone")
        lock = clone / ".git" / "shallow.lock"
        lock.write_text("", encoding="utf-8")

        def boom(*a, **k):
            raise gitutil.BoostError("git fetch timed out after 60s")
        monkeypatch.setattr(gitutil, "run", boom)
        assert gitutil.unshallow(clone) is False
        assert lock.exists(), "another git process's lock is not ours to drop"

    def test_the_fetch_stays_blobless(self, tap, tmp_path, monkeypatch):
        clone = _shallow_clone(tap, tmp_path / "clone")
        calls = []
        real = gitutil.run

        def rec(args, **kw):
            calls.append(args)
            return real(args, **kw)
        monkeypatch.setattr(gitutil, "run", rec)
        gitutil.unshallow(clone)
        assert ["-C", str(clone), "fetch", "--quiet", "--unshallow",
                "--filter=blob:none", "origin"] in calls


class TestUpdatingKeepsADeepCloneDeep:
    def test_pull(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        gitutil.unshallow(clone)
        _commit(tap, "skills/a", NEW + 100)
        gitutil.pull(clone)
        assert not gitutil.is_shallow(clone)
        assert gitutil.path_updated_at(clone, "skills/b") == NEW

    def test_checkout_commit(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        gitutil.unshallow(clone)
        _commit(tap, "skills/a", NEW + 100)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tap,
                             capture_output=True, text=True,
                             check=True).stdout.strip()
        gitutil.checkout_commit(clone, sha)
        assert gitutil.head_commit(clone) == sha
        assert not gitutil.is_shallow(clone)

    def test_a_shallow_clone_is_still_fetched_at_depth_one(self, tap, tmp_path):
        clone = _shallow_clone(tap, tmp_path / "clone")
        _commit(tap, "skills/a", NEW + 100)
        _commit(tap, "skills/b", NEW + 200)
        gitutil.pull(clone)
        out = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=clone,
                             capture_output=True, text=True, check=True)
        assert out.stdout.strip() == "1"


class TestHeadTime:
    def test_the_newest_commit(self, tap):
        assert gitutil.head_time(tap) == NEW

    def test_a_shallow_clone_still_has_one(self, tap, tmp_path):
        assert gitutil.head_time(_shallow_clone(tap, tmp_path / "clone")) == NEW

    def test_not_a_repo(self, tmp_path):
        assert gitutil.head_time(tmp_path) is None
