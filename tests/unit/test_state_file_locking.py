# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: concurrent boost processes must not lose each other's state.

The project lock, config.json and policy.json were each a bare
read-modify-write: two processes overlapping each read the file, changed one
thing and wrote it back whole, so the second write reverted the first while
both reported success. Each now has a ``mutate(fn)`` that holds
`util.file_lock` on a sidecar and takes its read inside the lock — the
discipline `lockfile.mutate` already had for the user lock.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from boost_cli.core import builtin, config, paths, policy, projectlock, registry, util
from boost_cli.errors import BoostError

# Every child's cwd: under the mutation gate the child's import is mutmut's
# trampoline, which reads `[mutmut]` from the `setup.cfg` in the current
# directory only (see test_first_run_pointer.py).
ROOT = Path(config.__file__).resolve().parents[2]


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _race(go: Path, body: str, tags: list[str]) -> None:
    """Run ``body`` in one child per tag, all released at once by ``go``."""
    code = textwrap.dedent("""
        import os, sys, time
        tag = sys.argv[1]
        while not os.path.exists(%r):
            time.sleep(0.005)
    """) % str(go) + textwrap.dedent(body)
    procs = [subprocess.Popen([sys.executable, "-c", code, tag], env=_env(),
                              cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)
             for tag in tags]
    go.write_text("", encoding="utf-8")
    for p in procs:
        _out, err = p.communicate(timeout=180)
        assert p.returncode == 0, err


N = 15
TAGS = ["a", "b", "c", "d"]


class TestRaces:
    def test_project_lock_keeps_every_row(self, sandbox):
        repo = sandbox / "repo"
        (repo / ".git").mkdir(parents=True)
        _race(sandbox / "go", """
            from boost_cli.core import projectlock
            for i in range(%d):
                projectlock.set_skill(%r, tag + str(i), {"version": "1"})
        """ % (N, str(repo)), TAGS)
        assert set(projectlock.installed(repo)) == \
            {t + str(i) for t in TAGS for i in range(N)}

    def test_project_lock_removals_and_writes_interleave(self, sandbox):
        repo = sandbox / "repo"
        for t in TAGS:
            projectlock.set_skill(repo, "old-" + t, {"version": "1"})
        _race(sandbox / "go", """
            from boost_cli.core import projectlock
            assert projectlock.remove_skill(%r, "old-" + tag) is True
            for i in range(%d):
                projectlock.set_skill(%r, tag + str(i), {"version": "1"})
        """ % (str(repo), N, str(repo)), TAGS)
        assert set(projectlock.installed(repo)) == \
            {t + str(i) for t in TAGS for i in range(N)}

    def test_config_set_keeps_every_key(self, sandbox):
        _race(sandbox / "go", """
            from boost_cli.core import config
            for i in range(%d):
                config.set_value("race." + tag + str(i), str(i))
        """ % N, TAGS)
        raw = json.loads(paths.config_path().read_text(encoding="utf-8"))
        assert raw["race"] == {t + str(i): i for t in TAGS for i in range(N)}

    def test_tap_rows_survive_concurrent_config_sets(self, sandbox):
        _race(sandbox / "go", """
            from boost_cli.core import config, registry
            for i in range(%d):
                if tag == "a":
                    config.mutate(lambda cfg, i=i: registry._append_rows(
                        cfg, [{"name": "t" + str(i), "url": "u"}]))
                else:
                    config.set_value("race." + tag + str(i), str(i))
        """ % N, TAGS)
        assert [t.name for t in registry.list_taps()] == \
            ["t" + str(i) for i in range(N)]
        assert len(config._read_raw()["race"]) == N * (len(TAGS) - 1)

    def test_policy_lists_keep_every_entry(self, sandbox):
        _race(sandbox / "go", """
            from boost_cli.core import policy
            key = {"a": "blocked_skills", "b": "blocked_taps",
                   "c": "allowed_taps", "d": "denied_capabilities"}[tag]
            for i in range(%d):
                policy.mutate(lambda pol: pol[key].append(tag + str(i)))
        """ % N, TAGS)
        pol = policy.load()
        for tag, key in zip(TAGS, ("blocked_skills", "blocked_taps",
                                   "allowed_taps", "denied_capabilities"),
                            strict=True):
            assert pol[key] == [tag + str(i) for i in range(N)]

    def test_policy_set_keeps_every_last_value(self, sandbox):
        _race(sandbox / "go", """
            from boost_cli import cli
            key = {"a": "max_skills", "b": "min_quality_score"}[tag]
            for i in range(1, %d + 1):
                assert cli.main(["policy", "set", key, str(i)]) == 0
        """ % N, ["a", "b"])
        pol = policy.load()
        assert (pol["max_skills"], pol["min_quality_score"]) == (N, N)


@pytest.fixture
def hold(sandbox):
    """Hold a sidecar in another process; yields a start(path) function."""
    procs: list[subprocess.Popen] = []

    def start(path: Path) -> None:
        p = subprocess.Popen(
            [sys.executable, "-c", textwrap.dedent("""
                import sys, time
                from boost_cli.core import util
                with util.file_lock(sys.argv[1]):
                    print("held", flush=True)
                    time.sleep(30)
            """), str(path)], env=_env(), cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        procs.append(p)
        assert p.stdout is not None
        assert p.stdout.readline().strip() == "held"
    yield start
    for p in procs:
        p.kill()
        p.communicate()


class TestHeldElsewhere:
    def test_project_lock_waits_and_names_itself(self, sandbox, hold,
                                                 monkeypatch):
        repo = sandbox / "repo"
        projectlock.set_skill(repo, "a", {"version": "1"})
        before = projectlock.lock_path(repo).read_bytes()
        hold(projectlock.guard_path(repo))
        monkeypatch.setattr(util, "FILE_LOCK_TIMEOUT", 0.2)
        with pytest.raises(BoostError) as ei:
            projectlock.set_skill(repo, "b", {"version": "1"})
        assert str(ei.value) == \
            "another boost process has held the project lock for over 0.2s"
        assert projectlock.lock_path(repo).read_bytes() == before

    def test_config_waits_and_names_itself(self, sandbox, hold, monkeypatch):
        config.set_value("x.y", "1")
        before = paths.config_path().read_bytes()
        hold(config.guard_path())
        monkeypatch.setattr(util, "FILE_LOCK_TIMEOUT", 0.2)
        with pytest.raises(BoostError) as ei:
            config.set_value("x.y", "2")
        assert str(ei.value) == \
            "another boost process has held the config file for over 0.2s"
        assert paths.config_path().read_bytes() == before

    def test_policy_waits_and_names_itself(self, sandbox, hold, monkeypatch):
        policy.set_key("max_skills", 3)
        before = paths.policy_path().read_bytes()
        hold(policy.guard_path())
        monkeypatch.setattr(util, "FILE_LOCK_TIMEOUT", 0.2)
        with pytest.raises(BoostError) as ei:
            policy.set_key("max_skills", 4)
        assert str(ei.value) == \
            "another boost process has held the policy file for over 0.2s"
        assert paths.policy_path().read_bytes() == before


class TestGuardPaths:
    def test_project_guard_hides_in_dot_git(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert projectlock.guard_path(tmp_path) == \
            tmp_path / ".git" / "boost-skill-lock.lock"

    def test_project_guard_follows_a_worktree_gitdir_file(self, tmp_path):
        # A linked worktree's `.git` is a file naming its private git dir.
        (tmp_path / "wt-git").mkdir()
        (tmp_path / ".git").write_text("gitdir: wt-git\n", encoding="utf-8")
        assert projectlock.guard_path(tmp_path) == \
            tmp_path / "wt-git" / "boost-skill-lock.lock"

    @pytest.mark.parametrize("dotgit", [None, "gitdir: missing\n",
                                        "not a pointer\n"])
    def test_project_guard_falls_back_beside_the_lock(self, tmp_path,
                                                      dotgit):
        if dotgit is not None:
            (tmp_path / ".git").write_text(dotgit, encoding="utf-8")
        assert projectlock.guard_path(tmp_path) == \
            tmp_path / ".boost" / "skill-lock.json.lock"

    def test_project_guard_falls_back_on_an_undecodable_dotgit(self,
                                                               tmp_path):
        (tmp_path / ".git").write_bytes(b"\xff\xfe")
        assert projectlock.guard_path(tmp_path) == \
            tmp_path / ".boost" / "skill-lock.json.lock"

    def test_config_and_policy_guards_sit_beside_their_files(self, sandbox):
        assert config.guard_path() == \
            paths.config_path().with_name("config.json.lock")
        assert policy.guard_path() == \
            paths.policy_path().with_name("policy.json.lock")

    def test_project_write_in_a_repo_leaves_dot_boost_clean(self, tmp_path):
        (tmp_path / ".git").mkdir()
        projectlock.set_skill(tmp_path, "a", {"version": "1"})
        assert sorted(p.name for p in (tmp_path / ".boost").iterdir()) == \
            ["skill-lock.json"]


class TestMutate:
    def test_project_returns_whether_it_wrote(self, tmp_path):
        assert projectlock.mutate(tmp_path, lambda lock: False) is False
        assert not projectlock.exists(tmp_path)
        assert projectlock.mutate(tmp_path, lambda lock: None) is True
        assert projectlock.installed(tmp_path) == {}

    def test_project_remove_absent_creates_nothing(self, tmp_path):
        assert projectlock.remove_skill(tmp_path, "nope") is False
        assert not (tmp_path / ".boost").exists()
        projectlock.set_skill(tmp_path, "a", {"version": "1"})
        before = projectlock.lock_path(tmp_path).read_bytes()
        assert projectlock.remove_skill(tmp_path, "nope") is False
        assert projectlock.lock_path(tmp_path).read_bytes() == before

    def test_project_mutate_refuses_a_corrupt_lock(self, tmp_path, capsys):
        p = projectlock.lock_path(tmp_path)
        p.parent.mkdir()
        p.write_text("{nope", encoding="utf-8")
        with pytest.raises(BoostError, match="project lock is corrupt"):
            projectlock.mutate(tmp_path, lambda lock: None)
        assert p.read_text(encoding="utf-8") == "{nope"

    def test_project_mutate_exception_writes_nothing(self, tmp_path):
        projectlock.set_skill(tmp_path, "a", {"version": "1"})
        before = projectlock.lock_path(tmp_path).read_bytes()

        def boom(lock):
            lock["skills"]["b"] = {}
            raise KeyError("x")
        with pytest.raises(KeyError):
            projectlock.mutate(tmp_path, boom)
        assert projectlock.lock_path(tmp_path).read_bytes() == before
        with util.file_lock(projectlock.guard_path(tmp_path), timeout=0):
            pass

    def test_config_returns_whether_it_wrote(self, sandbox):
        assert config.mutate(lambda cfg: False) is False
        assert not paths.config_path().exists()
        assert config.mutate(lambda cfg: None) is True
        assert paths.config_path().exists()

    def test_config_mutate_bypasses_the_stat_cache(self, sandbox):
        config.set_value("x.y", "1")
        p = paths.config_path()
        assert config.load()["x"] == {"y": 1}        # primes the cache
        st = p.stat()
        # Same size, same mtime: invisible to the (path, mtime, size) stamp.
        p.write_text(p.read_text(encoding="utf-8").replace('"y": 1',
                                                           '"y": 2'),
                     encoding="utf-8")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
        if sys.platform != "win32":
            # Windows stamps the rewrite anyway (its mtime resolution and
            # change time differ), so the stale read is only provable here.
            assert config.load()["x"] == {"y": 1}
        seen = []
        config.mutate(lambda cfg: seen.append(cfg["x"]["y"]) or False)
        assert seen == [2]

    def test_config_mutate_reads_only_overrides(self, sandbox):
        # Every writer sees the on-disk overrides, never the DEFAULTS-merged
        # view: handing it the merged view is what wrote all of DEFAULTS to
        # disk on the first `config set` or `boost tap`.
        p = paths.config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"x": {"y": 1}}', encoding="utf-8")
        seen: list[dict] = []
        config.mutate(lambda cfg: seen.append(cfg) or False)
        assert seen == [{"x": {"y": 1}}]

    def test_config_unset_absent_writes_nothing(self, sandbox):
        config.set_value("x.y", "1")
        before = paths.config_path().read_bytes()
        assert config.unset("x.z") is False
        assert config.unset("q.z") is False
        assert paths.config_path().read_bytes() == before
        assert config.unset("x.y") is True
        assert config._read_raw()["x"] == {}

    def test_policy_returns_whether_it_wrote(self, sandbox):
        assert policy.mutate(lambda pol: False) is False
        assert not paths.policy_path().exists()
        assert policy.mutate(lambda pol: None) is True
        assert json.loads(paths.policy_path().read_text(encoding="utf-8")) \
            == policy.DEFAULTS

    def test_policy_set_key_reads_fresh(self, sandbox):
        policy.set_key("max_skills", 5)
        policy.set_key("min_quality_score", 40)
        raw = json.loads(paths.policy_path().read_text(encoding="utf-8"))
        assert (raw["max_skills"], raw["min_quality_score"]) == (5, 40)


class TestRegistryRows:
    def test_append_rows_skips_a_name_already_there(self):
        cfg = {"taps": [{"name": "Foo", "url": "u"}, "junk"]}
        assert registry._append_rows(cfg, [{"name": "foo", "url": "v"},
                                           {"name": "bar", "url": "w"},
                                           {"name": "BAR", "url": "x"}]) \
            is True
        assert cfg["taps"] == [{"name": "Foo", "url": "u"}, "junk",
                               {"name": "bar", "url": "w"}]

    def test_append_rows_reports_nothing_new(self):
        cfg: dict = {}
        assert registry._append_rows(cfg, []) is False
        assert cfg == {"taps": []}
        assert registry._append_rows(cfg, [{"name": "a"}]) is True
        assert registry._append_rows(cfg, [{"name": "A"}]) is False
        assert cfg == {"taps": [{"name": "a"}]}


ROW = {"name": builtin.BUILTIN_TAP, "url": builtin.BUILTIN_URL,
       "curated": True}


class TestBuiltinRegister:

    def test_skips_when_already_registered(self):
        cfg = {"taps": [dict(ROW, url="other")]}
        assert builtin._register(cfg) is False
        assert cfg == {"taps": [dict(ROW, url="other")]}

    def test_appends_to_an_empty_config(self):
        cfg: dict = {}
        assert builtin._register(cfg) is True
        assert cfg == {"taps": [ROW]}

    def test_keeps_a_malformed_row(self):
        cfg = {"taps": ["junk"]}
        assert builtin._register(cfg) is True
        assert cfg == {"taps": ["junk", ROW]}

    def test_ensure_tap_writes_once(self, sandbox):
        builtin.ensure_tap()
        before = paths.config_path().read_bytes()
        builtin.ensure_tap()
        assert paths.config_path().read_bytes() == before
        assert [t.name for t in registry.list_taps()] == [builtin.BUILTIN_TAP]


class TestProjectPinRereads:
    """`store.set_project_pin` decides on the row it reads under the lock."""

    def test_a_row_removed_after_the_unlocked_check_is_not_resurrected(
            self, sandbox, monkeypatch):
        from boost_cli.core import store
        repo = sandbox / "repo"
        projectlock.set_skill(repo, "keep", {"version": "1"})
        lock = projectlock.lock_path(repo)
        before = lock.stat()
        # The unlocked probe still sees "x"; another process removed it
        # before this one took the lock.
        monkeypatch.setattr(projectlock, "get_skill",
                            lambda base, name: {"version": "1"})
        assert store.set_project_pin(repo, "x", True) is None
        # Not rewritten at all: a rewrite is an os.replace, a new inode.
        after = lock.stat()
        assert (after.st_ino, after.st_mtime_ns) == \
            (before.st_ino, before.st_mtime_ns)

    def test_pinning_keeps_rows_another_process_wrote(self, sandbox,
                                                      monkeypatch):
        from boost_cli.core import store
        repo = sandbox / "repo"
        projectlock.set_skill(repo, "x", {"version": "1", "commit_pin": "c"})
        real = projectlock.get_skill

        def probe(base, name):
            row = real(base, name)
            projectlock.set_skill(base, "other", {"version": "2"})
            return row
        monkeypatch.setattr(projectlock, "get_skill", probe)
        assert store.set_project_pin(repo, "x", False) == {"version": "1"}
        assert projectlock.installed(repo) == {
            "x": {"version": "1"}, "other": {"version": "2"}}
