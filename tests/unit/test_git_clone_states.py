# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tap clones in states git leaves behind: a stale lock, local edits, planted
files, and a subdirectory of a work tree given as a tap.

Each was a silent wrong answer. A killed git's ``index.lock`` made `update`
advise `boost untap` on a healthy tap and doctor say healthy; a modified file
outside the cone made `compact` report success with the file on disk; an
untracked SKILL.md survived every update and installed as if it came from the
tap's commit; and `boost tap <repo>/skills` advised `git init` inside the
user's own repository.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import compact as compactplan
from boost_cli.core import gitutil, paths, registry, util
from boost_cli.errors import BoostError

_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]
#: The upstream's `.gitignore`: tracked, unmodified and outside the cone.
_IGNORE = b"*.log\n"


def _git(repo, *argv):
    return subprocess.run(["git", "-C", str(repo), *argv], check=True,
                          capture_output=True, text=True).stdout


def _upstream(dest: Path) -> Path:
    """A repo with one skill, an out-of-cone asset and an ignore rule."""
    skill = dest / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\nbody\n", encoding="utf-8")
    (dest / "assets").mkdir()
    (dest / "assets" / "big.bin").write_bytes(b"x" * 4096)
    (dest / ".gitignore").write_bytes(_IGNORE)
    subprocess.run(["git", "init", "-q", "-b", "main", str(dest)], check=True,
                   capture_output=True)
    _git(dest, "add", "-A")
    _git(dest, *_ID, "commit", "-qm", "init")
    return dest


def _commit(repo: Path, msg: str = "more") -> str:
    readme = repo / "README.md"
    with readme.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD").strip()


def _plant(clone: Path) -> tuple[Path, Path]:
    evil = clone / "skills" / "evil" / "SKILL.md"
    evil.parent.mkdir(parents=True)
    evil.write_text("---\nname: evil\ndescription: planted\n---\nx\n",
                    encoding="utf-8")
    ignored = clone / "keep.log"
    ignored.write_text("mine\n", encoding="utf-8")
    return evil, ignored


@pytest.fixture()
def owned(sandbox, tmp_path):
    """(upstream, clone) with the clone where boost keeps its taps."""
    up = _upstream(tmp_path / "up")
    clone = paths.repos_dir() / "t"
    clone.parent.mkdir(parents=True, exist_ok=True)
    gitutil.clone_shallow(str(up), clone)
    return up, clone


class TestGitLockPath:
    @pytest.mark.parametrize("lock", [
        "/r/.git/index.lock", "/r/.git/shallow.lock",
        "/r/.git/refs/heads/main.lock", "/r/.git/info/sparse-checkout.lock"])
    def test_names_any_lock_git_could_not_take(self, lock):
        text = "fatal: Unable to create '%s': File exists.\n\nAnother" % lock
        assert gitutil.git_lock_path(text) == lock

    @pytest.mark.parametrize("text", [
        "", "fatal: could not open '/r/.git/index.lock': Permission denied",
        "fatal: Unable to create '/r/.git/index': File exists."])
    def test_names_nothing_otherwise(self, text):
        assert gitutil.git_lock_path(text) is None

    def test_hint_names_the_path_and_never_untap(self):
        assert gitutil.lock_hint("/r/.git/index.lock") == (
            "another git process is working in this tap's clone; if none is, "
            "remove /r/.git/index.lock")

    def test_run_attaches_the_hint_from_real_git(self, owned):
        _up, clone = owned
        lock = clone / ".git" / "index.lock"
        lock.write_text("", encoding="utf-8")
        with pytest.raises(BoostError) as err:
            gitutil.run(["-C", str(clone), "reset", "--hard", "--quiet"])
        named = gitutil.git_lock_path(err.value.message)
        assert named is not None
        assert Path(named).resolve() == lock.resolve()
        assert err.value.hint == gitutil.lock_hint(named)

    def test_run_gives_no_hint_for_other_failures(self, tmp_path):
        with pytest.raises(BoostError) as err:
            gitutil.run(["-C", str(tmp_path), "rev-parse", "--verify",
                         "nope^{commit}"])
        assert err.value.hint is None

    def test_sparse_add_does_not_remove_a_lock_it_does_not_own(
            self, monkeypatch, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git" / "info").mkdir(parents=True)
        sparse_lock = repo / ".git" / "info" / "sparse-checkout.lock"
        sparse_lock.write_text("", encoding="utf-8")
        busy = ("git sparse-checkout failed: fatal: Unable to create "
                "'/x/.git/index.lock': File exists.")
        calls: list = []

        def fake(argv, **_k):
            calls.append(argv)
            raise BoostError(busy)
        monkeypatch.setattr(gitutil, "_sparse_list", lambda r: set())
        monkeypatch.setattr(gitutil, "run", fake)
        with pytest.raises(BoostError) as err:
            gitutil._sparse_add(repo, ["/skills/a/*"], "skills/a")
        assert len(calls) == 1
        assert sparse_lock.exists()
        assert err.value.message == ("could not fetch skills/a from the repo "
                                     "tap: " + busy)
        assert err.value.hint == gitutil.lock_hint("/x/.git/index.lock")


class TestStaleLocks:
    def test_finds_git_locks_and_skips_boost_s_own(self, tmp_path):
        git = tmp_path / "r" / ".git"
        for rel in ("index.lock", "info/sparse-checkout.lock",
                    "refs/heads/main.lock", "boost-sparse.lock",
                    "objects/ab/x.lock", "index"):
            (git / rel).parent.mkdir(parents=True, exist_ok=True)
            (git / rel).write_text("", encoding="utf-8")
        (git / "dir.lock").mkdir()
        assert gitutil.stale_locks(tmp_path / "r") == sorted([
            git / "index.lock", git / "info" / "sparse-checkout.lock",
            git / "refs" / "heads" / "main.lock"])

    def test_nothing_without_a_git_dir(self, tmp_path):
        (tmp_path / "plain").mkdir()
        assert gitutil.stale_locks(tmp_path / "plain") == []
        (tmp_path / "gitfile").mkdir()
        (tmp_path / "gitfile" / ".git").write_text("gitdir: x\n",
                                                   encoding="utf-8")
        assert gitutil.stale_locks(tmp_path / "gitfile") == []

    def test_a_healthy_clone_has_none(self, owned):
        assert gitutil.stale_locks(owned[1]) == []


class TestOwnedClone:
    def test_a_clone_in_the_repos_dir(self, owned):
        assert gitutil.owned_clone(owned[1]) is True

    def test_not_the_repos_dir_itself(self, owned):
        assert gitutil.owned_clone(paths.repos_dir()) is False

    def test_not_a_clone_elsewhere(self, sandbox, tmp_path):
        up = _upstream(tmp_path / "up")
        assert gitutil.owned_clone(up) is False

    def test_not_a_plain_dir_inside_an_enclosing_repo(self, sandbox):
        # repos_dir inside a repo (a $HOME kept in git): a `.git` there that
        # git does not accept resolves to the enclosing repo's top.
        root = paths.repos_dir()
        root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(root)], check=True,
                       capture_output=True)
        fake = root / "builtin"
        (fake / ".git").mkdir(parents=True)
        assert gitutil.owned_clone(fake) is False
        (root / "plain").mkdir()
        assert gitutil.owned_clone(root / "plain") is False

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks")
    def test_not_a_symlink_out_of_the_repos_dir(self, sandbox, tmp_path):
        up = _upstream(tmp_path / "up")
        paths.repos_dir().mkdir(parents=True, exist_ok=True)
        link = paths.repos_dir() / "linked"
        link.symlink_to(up, target_is_directory=True)
        assert gitutil.owned_clone(link) is False


class TestUntrackedFilesAreRemoved:
    def test_pull_cleans_untracked_and_keeps_ignored(self, owned):
        _up, clone = owned
        evil, ignored = _plant(clone)
        assert gitutil.pull(clone) == "already up to date"
        assert not evil.exists()
        assert not evil.parent.exists()
        assert ignored.read_text(encoding="utf-8") == "mine\n"
        assert _git(clone, "status", "--porcelain", "--untracked-files=all") \
            == ""

    def test_pull_after_an_upstream_move_does_not_index_it(self, owned):
        from boost_cli.core import catalog
        up, clone = owned
        evil, _ = _plant(clone)
        new = _commit(up)
        assert gitutil.pull(clone).endswith("→ %s" % new[:7])
        assert not evil.exists()
        names = {e["name"] for e in catalog.scan_dir(clone)}
        assert names == {"demo"}

    def test_checkout_commit_cleans_untracked(self, owned):
        up, clone = owned
        sha = _commit(up)
        evil, ignored = _plant(clone)
        gitutil.checkout_commit(clone, sha)
        assert not evil.exists()
        assert ignored.exists()

    def test_a_clone_boost_does_not_own_is_left_alone(self, sandbox, tmp_path):
        up = _upstream(tmp_path / "up")
        clone = tmp_path / "elsewhere"
        gitutil.clone_shallow(str(up), clone)
        evil, _ = _plant(clone)
        gitutil.pull(clone)
        assert evil.exists()


class TestNarrowWithLocalEdits:
    def _dirty(self, clone: Path) -> Path:
        _git(clone, "sparse-checkout", "disable")
        big = clone / "assets" / "big.bin"
        big.write_bytes(b"y" * 8192)
        assert _git(clone, "ls-files", "-m") == "assets/big.bin\n"
        return big

    def test_an_owned_clone_frees_what_the_dry_run_promised(self, owned):
        _up, clone = owned
        big = self._dirty(clone)
        promised = compactplan.plan(clone, []).freight
        assert promised == 8192 + len(_IGNORE)
        gone = big.stat().st_size + (clone / ".gitignore").stat().st_size
        assert gone == promised
        gitutil.narrow(clone)
        assert not big.exists()
        assert not (clone / ".gitignore").exists()
        assert (clone / "skills" / "demo" / "SKILL.md").exists()
        assert compactplan.plan(clone, []).freight == 0

    def test_elsewhere_it_is_not_promised_and_not_reported_as_done(
            self, sandbox, tmp_path):
        up = _upstream(tmp_path / "up")
        clone = tmp_path / "elsewhere"
        gitutil.clone_shallow(str(up), clone)
        big = self._dirty(clone)
        assert compactplan.plan(clone, []).freight == len(_IGNORE)
        with pytest.raises(BoostError) as err:
            gitutil.narrow(clone)
        assert err.value.message == ("git kept 1 locally modified file outside "
                                     "the sparse cone: assets/big.bin")
        assert err.value.hint == (
            "discard the edits (`git -C %s checkout -- .`), then run "
            "`boost compact` again" % util.shell_arg(str(clone)))
        assert big.read_bytes() == b"y" * 8192

    def test_reapply_reads_every_path_git_left(self, monkeypatch, tmp_path):
        stderr = ("warning: The following paths are not up to date and were "
                  "left despite sparse patterns:\n\ta/x.bin\n\tb c/y.bin\n\n"
                  "After fixing the above paths, you may want to run `git "
                  "sparse-checkout reapply`.\n\tnot/a/path\n")
        seen: list = []

        def fake(argv, **_k):
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", stderr)
        monkeypatch.setattr(gitutil, "run", fake)
        assert gitutil._reapply(tmp_path) == ["a/x.bin", "b c/y.bin"]
        assert seen == [["-c", "core.precomposeunicode=false", "-c",
                         "core.quotepath=false", "-C", str(tmp_path),
                         "sparse-checkout", "reapply"]]

    def test_reapply_with_nothing_left(self, monkeypatch, tmp_path):
        monkeypatch.setattr(gitutil, "run", lambda argv, **_k:
                            subprocess.CompletedProcess(argv, 0, "", None))
        assert gitutil._reapply(tmp_path) == []


class TestTapASubdirectory:
    def test_names_the_repository_and_never_git_init(self, sandbox, tmp_path):
        up = _upstream(tmp_path / "up")
        sub = up / "skills"
        with pytest.raises(BoostError) as err:
            registry.parse_spec(str(sub))
        top = up.resolve()
        assert err.value.message == (
            "%s is inside the git repository at %s; boost taps a whole "
            "repository" % (sub, top))
        assert err.value.hint == (
            "`boost tap %s`, or `boost import %s` to copy just this directory "
            "in without a tap" % (util.shell_arg(str(top)),
                                  util.shell_arg(str(sub))))
        assert "git init" not in err.value.hint

    def test_enclosing_toplevel(self, tmp_path):
        up = _upstream(tmp_path / "up")
        assert gitutil.enclosing_toplevel(up / "skills" / "demo") \
            == up.resolve()
        assert gitutil.enclosing_toplevel(up) is None
        (tmp_path / "plain").mkdir()
        assert gitutil.enclosing_toplevel(tmp_path / "plain") is None


class TestCommandsNameTheLock:
    @pytest.fixture()
    def locked(self, boost, tmp_path):
        up = tmp_path / "lk"
        shutil.copytree(_upstream(tmp_path / "src"), up)
        boost("tap", up)
        clone = registry.get("lk").path
        lock = clone / ".git" / "index.lock"
        lock.write_text("", encoding="utf-8")
        _commit(up)
        return clone, lock

    def test_update_names_the_lock_instead_of_untap(self, boost, locked):
        _clone, lock = locked
        r = boost("update", expect=1)
        named = gitutil.git_lock_path(r.out)
        assert named is not None and Path(named).resolve() == lock.resolve()
        assert "lk: %s" % gitutil.lock_hint(named) in r.out
        assert "boost untap" not in r.out
        assert "could not be refreshed" not in r.out

    def test_doctor_flags_it(self, boost, locked):
        _clone, lock = locked
        r = boost("doctor", "--json", expect=None)
        assert r.rc == 1
        issues = [c["message"] for c in json.loads(r.out)["checks"]
                  if c["name"] == "tap" and c["status"] != "ok"]
        assert issues == ["tap lk has a git lock file in its clone — %s"
                          % gitutil.lock_hint(paths.tilde(lock))]

    def test_doctor_is_quiet_once_it_is_gone(self, boost, locked):
        _clone, lock = locked
        lock.unlink()
        r = boost("doctor", "--json", expect=None)
        assert "git lock file" not in r.out

    def test_compact_prints_the_hint(self, boost, locked):
        _clone, _lock = locked
        r = boost("compact", "lk", expect=1)
        assert "could not compact lk" in r.out
        assert "another git process is working in this tap's clone" in r.out
