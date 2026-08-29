# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/paths.py — all locations derive from $HOME."""
from __future__ import annotations

import os
from pathlib import Path

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
