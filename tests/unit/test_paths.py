# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/paths.py — all locations derive from $HOME."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from boost_cli.core import paths


class TestHomeDerivation:
    def test_paths_follow_home_at_call_time(self, tmp_path, monkeypatch):
        home_a = tmp_path / "a"
        home_b = tmp_path / "b"
        monkeypatch.delenv("BOOST_HOME", raising=False)
        monkeypatch.delenv("BOOST_AGENTS_STORE", raising=False)

        monkeypatch.setenv("HOME", str(home_a))
        assert paths.home() == home_a
        assert paths.boost_home() == home_a / ".boost"
        assert paths.store_dir() == home_a / ".agents" / "skills"

        # move HOME mid-test: every path must move with it
        monkeypatch.setenv("HOME", str(home_b))
        assert paths.home() == home_b
        assert paths.boost_home() == home_b / ".boost"
        assert paths.store_dir() == home_b / ".agents" / "skills"
        assert paths.config_path() == home_b / ".boost" / "config.json"

    def test_full_layout(self, sandbox):
        vh = sandbox / ".boost"
        assert paths.boost_home() == vh
        assert paths.repos_dir() == vh / "repos"
        assert paths.cache_dir() == vh / "cache"
        assert paths.logs_dir() == vh / "logs"
        assert paths.state_dir() == vh / "state"
        assert paths.snapshots_dir() == vh / "state" / "snapshots"
        assert paths.lock_history_dir() == vh / "state" / "lock-history"
        assert paths.profiles_dir() == vh / "state" / "profiles"
        assert paths.config_path() == vh / "config.json"
        assert paths.pulse_path() == vh / "state" / "pulse.jsonl"
        assert paths.policy_path() == vh / "state" / "policy.json"
        assert paths.store_dir() == sandbox / ".agents" / "skills"
        assert paths.lockfile_path() == (
            sandbox / ".agents" / "skills" / ".skill-lock.json")


class TestOverrides:
    def test_boost_home_override(self, sandbox, monkeypatch):
        override = sandbox / "elsewhere"
        monkeypatch.setenv("BOOST_HOME", str(override))
        assert paths.boost_home() == override
        assert paths.repos_dir() == override / "repos"
        assert paths.state_dir() == override / "state"
        assert paths.config_path() == override / "config.json"
        # store is NOT under BOOST_HOME
        assert paths.store_dir() == sandbox / ".agents" / "skills"

    def test_agents_store_override(self, sandbox, monkeypatch):
        override = sandbox / "custom-store"
        monkeypatch.setenv("BOOST_AGENTS_STORE", str(override))
        assert paths.store_dir() == override
        assert paths.lockfile_path() == override / ".skill-lock.json"
        # boost_home unaffected
        assert paths.boost_home() == sandbox / ".boost"


class TestExpand:
    def test_bare_tilde_is_home(self, sandbox):
        assert paths.expand("~") == sandbox

    def test_tilde_slash(self, sandbox):
        assert paths.expand("~/x/y") == sandbox / "x" / "y"

    def test_absolute_untouched(self, sandbox):
        assert paths.expand("/abs/path") == Path("/abs/path")

    def test_relative_untouched(self, sandbox):
        assert paths.expand("rel/path") == Path("rel/path")

    def test_tilde_user_not_expanded(self, sandbox):
        # only ~ and ~/ forms are special; ~user is left as-is
        assert paths.expand("~other") == Path("~other")


class TestTilde:
    def test_exact_home_is_tilde(self, sandbox):
        assert paths.tilde(str(sandbox)) == "~"

    def test_path_under_home_contracts(self, sandbox):
        p = sandbox / "x" / "y"
        assert paths.tilde(str(p)) == "~/x/y"

    def test_sibling_prefix_not_contracted(self, sandbox):
        # regression: /Users/bob-backup must NOT contract to ~-backup when
        # home is /Users/bob. A separator boundary is required, not a bare
        # startswith(home).
        sibling = str(sandbox) + "-backup"
        # tilde() always normalizes separators for display, even for a path
        # outside $HOME — only the *contraction* is being asserted here.
        assert paths.tilde(sibling) == sibling.replace(os.sep, "/")

    def test_path_outside_home_unchanged(self, sandbox):
        assert paths.tilde("/etc/hosts") == "/etc/hosts"

    def test_accepts_path_object(self, sandbox):
        assert paths.tilde(sandbox / "cache") == "~/cache"

    def test_resolved_home_contracts_through_symlink(self, tmp_path, monkeypatch):
        # HOME is a symlink; a path expressed against the *resolved* home must
        # still contract (the helper tries both raw and resolved home).
        real = tmp_path / "real_home"
        real.mkdir()
        link = tmp_path / "link_home"
        link.symlink_to(real)
        monkeypatch.setenv("HOME", str(link))
        monkeypatch.delenv("BOOST_HOME", raising=False)
        resolved = str(paths.home().resolve())
        assert paths.tilde(resolved + os.sep + "sub") == "~/sub"


class TestEnsureDirs:
    EXPECTED = ("repos", "cache", "logs", "state", "state/snapshots",
                "state/lock-history", "state/profiles")

    def test_creates_full_set(self, sandbox):
        assert not (sandbox / ".boost").exists()
        paths.ensure_dirs()
        for rel in self.EXPECTED:
            assert (sandbox / ".boost" / rel).is_dir(), rel
        assert (sandbox / ".agents" / "skills").is_dir()

    def test_idempotent(self, sandbox):
        paths.ensure_dirs()
        paths.ensure_dirs()  # must not raise
        assert (sandbox / ".boost" / "state" / "profiles").is_dir()


class TestRepoRoot:
    def test_points_at_checkout(self):
        root = paths.repo_root()
        assert (root / "boost_cli" / "cli.py").is_file()
        assert (root / "boost_cli" / "core" / "paths.py").is_file()
        assert root == Path(paths.__file__).resolve().parent.parent.parent


class TestPackageAndStatePaths:
    def test_package_root_is_the_boost_cli_dir(self):
        root = paths.package_root()
        assert root.name == "boost_cli"
        assert (root / "core" / "paths.py").is_file()
        assert root == Path(paths.__file__).resolve().parent.parent

    def test_trusted_keys_path_name_and_location(self, sandbox):
        p = paths.trusted_keys_path()
        assert p.name == "trusted_keys.json"
        assert p.parent == paths.state_dir()


class TestLauncher:
    def test_prefers_console_script_on_path(self, monkeypatch):
        monkeypatch.setattr("boost_cli.core.paths.shutil.which",
                            lambda c: "/opt/homebrew/bin/boost")
        assert paths.launcher() == Path("/opt/homebrew/bin/boost")

    def test_falls_back_to_checkout_shim(self, monkeypatch):
        monkeypatch.setattr("boost_cli.core.paths.shutil.which",
                            lambda c: None)
        assert paths.launcher() == paths.repo_root() / "boost"


_NO_MODE_BITS = (
    pytest.mark.skipif(sys.platform == "win32",
                       reason="chmod can't make a directory unwritable on Windows"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="root ignores mode bits"),
)


def _mode_bits(fn):
    for mark in _NO_MODE_BITS:
        fn = mark(fn)
    return fn


@pytest.fixture()
def locked(tmp_path):
    """A directory whose mode the test sets; made writable again after."""
    d = tmp_path / "locked"
    d.mkdir()
    yield d
    d.chmod(0o700)


class TestNearestExisting:
    def test_an_existing_path_is_its_own_answer(self, tmp_path):
        assert paths.nearest_existing(tmp_path) == tmp_path

    def test_a_missing_path_walks_up_to_the_first_that_exists(self, tmp_path):
        assert paths.nearest_existing(tmp_path / "a" / "b" / "c") == tmp_path

    def test_stops_at_the_filesystem_root(self):
        root = Path(Path.cwd().anchor)
        assert paths.nearest_existing(root) == root


class TestRefusesWrites:
    def test_a_writable_existing_dir_refuses_nothing(self, tmp_path):
        assert paths.refuses_writes(tmp_path) is None

    def test_a_missing_dir_under_a_writable_parent_refuses_nothing(
            self, tmp_path):
        assert paths.refuses_writes(tmp_path / "cache" / "deeper") is None

    @_mode_bits
    def test_an_existing_read_only_dir_names_itself(self, locked):
        locked.chmod(0o500)
        assert paths.refuses_writes(locked) == locked

    @_mode_bits
    def test_a_missing_dir_names_the_parent_that_refuses_the_mkdir(
            self, locked):
        # The card's shape: no cache dir under a read-only ~/.boost. Checking
        # the cache dir alone saw a missing dir and called it fine.
        locked.chmod(0o500)
        assert paths.refuses_writes(locked / "cache") == locked
        assert paths.refuses_writes(locked / "cache" / "x") == locked

    @_mode_bits
    def test_a_dir_without_search_permission_refuses_too(self, locked):
        # Writable but not searchable: mkdir inside it still fails.
        locked.chmod(0o600)
        assert paths.refuses_writes(locked / "cache") == locked


    def test_a_file_where_a_dir_belongs_refuses(self, tmp_path):
        # Even an executable one: os.access alone would call it writable, and
        # heal would preview a mkdir its run then fails.
        f = tmp_path / "skills"
        f.write_text("x", encoding="utf-8")
        f.chmod(0o755)
        assert paths.refuses_writes(f) == f
        assert paths.refuses_writes(f / "deeper") == f


@pytest.mark.skipif(sys.platform == "win32",
                    reason="creating a symlink needs a privilege on Windows")
class TestADanglingSymlinkIsInTheWay:
    """Following the link called ``~/.claude/skills -> /nowhere`` missing and
    creatable, so heal's preview promised a mkdir its run then failed."""

    def test_the_link_is_its_own_nearest_existing_path(self, tmp_path):
        link = tmp_path / "skills"
        link.symlink_to(tmp_path / "nowhere")
        assert paths.nearest_existing(link) == link
        assert paths.nearest_existing(link / "x") == link

    def test_the_link_refuses_writes(self, tmp_path):
        link = tmp_path / "skills"
        link.symlink_to(tmp_path / "nowhere")
        assert paths.refuses_writes(link) == link
        assert paths.refuses_writes(link / "x") == link

    def test_a_link_to_a_writable_dir_refuses_nothing(self, tmp_path):
        (tmp_path / "real").mkdir()
        link = tmp_path / "skills"
        link.symlink_to(tmp_path / "real")
        assert paths.refuses_writes(link) is None
        assert not paths.in_the_way(link)

    def test_the_link_is_named_as_in_the_way_with_a_remedy_that_works(
            self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        link = tmp_path / "skills"
        link.symlink_to(tmp_path / "nowhere")
        assert paths.in_the_way(link)
        assert paths.not_writable(link, link) == "~/skills is not a directory"
        assert paths.write_remedy(link) == "move ~/skills aside"


class TestNotWritableWording:
    @pytest.fixture(autouse=True)
    def _home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

    def test_a_dir_that_refuses_names_itself(self, tmp_path):
        assert (paths.not_writable(tmp_path / "c", tmp_path / "c")
                == "~/c is not writable")

    def test_a_missing_dir_names_the_parent_that_refuses(self, tmp_path):
        assert (paths.not_writable(tmp_path / "b" / "c", tmp_path)
                == "~/b/c cannot be created: ~ is not writable")
        assert paths.write_remedy(tmp_path) == "run `chmod u+w ~`"

    def test_a_file_where_a_dir_belongs_is_not_a_directory(self, tmp_path):
        f = tmp_path / "b"
        f.write_text("x", encoding="utf-8")
        assert (paths.not_writable(f / "c", f)
                == "~/b/c cannot be created: ~/b is not a directory")
        assert paths.in_the_way(f)
        assert paths.write_remedy(f) == "move ~/b aside"

    def test_a_block_that_is_not_there_is_not_in_the_way(self, tmp_path):
        # heal's fallback when a mkdir fails that refuses_writes called fine.
        gone = tmp_path / "gone"
        assert not paths.in_the_way(gone)
        assert paths.not_writable(gone, gone) == "~/gone is not writable"
        assert paths.write_remedy(gone) == "run `chmod u+w ~/gone`"


class TestCreateDirs:
    def test_creates_every_dir_and_refuses_none(self, tmp_path):
        want = [tmp_path / "a", tmp_path / "b" / "c"]
        assert paths.create_dirs(want) == []
        assert all(d.is_dir() for d in want)

    @_mode_bits
    def test_a_refused_dir_does_not_stop_the_ones_after_it(self, tmp_path,
                                                           locked):
        locked.chmod(0o500)
        later = tmp_path / "later"
        assert paths.create_dirs([locked / "cache", later]) == [locked / "cache"]
        assert later.is_dir()
        assert not (locked / "cache").exists()

    def test_a_file_in_the_way_is_refused_not_raised(self, tmp_path):
        (tmp_path / "f").write_text("x", encoding="utf-8")
        assert paths.create_dirs([tmp_path / "f"]) == [tmp_path / "f"]
