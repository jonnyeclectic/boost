# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Which of two same-named skills is newer: boost's copy or a plugin's.

Boost's date is exact: the tap clone has its whole history, so it is the
newest commit touching the skill's dir. A plugin's usually is not. Claude
Code's marketplace and cache checkouts are shallow or not git at all, so the
date found there is the HEAD's or the file times of the install, and either
is *at least* when the skill really last changed. Such a date can show
boost's copy is newer and never that the plugin's is; reading it the other
way would call nearly every plugin newer, since Claude Code installed it
after boost's commit. These tests pin that asymmetry.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import foreign, paths, util

PID = "eight-backend@eight"
OLD, NEW = 1577836800, 1609459200          # 2020-01-01, 2021-01-01


def _skill(d: Path, body: str = "# s\n", when: float | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    if when is not None:
        os.utime(d / "SKILL.md", (when, when))
    return d


def _git(*args, cwd, when=None):
    env = os.environ.copy()
    if when is not None:
        env |= {"GIT_AUTHOR_DATE": "@%d +0000" % when,
                "GIT_COMMITTER_DATE": "@%d +0000" % when}
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, env=env)


def _repo(root: Path, when: int = OLD) -> Path:
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@test", cwd=root)
    _git("config", "user.name", "T", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-qm", "c", cwd=root, when=when)
    return root


def _cache_skill(when: float = NEW) -> tuple[foreign.Plugin, Path]:
    """A plugin installed in Claude Code's cache, as most are."""
    inst = paths.home() / ".claude" / "plugins" / "cache" / "eight" / "eight-backend" / "v1"
    return foreign.Plugin(PID, inst), _skill(inst / "skills" / "x", when=when)


def _folder_skill(when: float = NEW) -> tuple[foreign.Plugin, Path]:
    """A plugin from a marketplace added as a local folder."""
    mdir = paths.home() / "src" / "eight"
    plugins = paths.home() / ".claude" / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    (plugins / "known_marketplaces.json").write_text(json.dumps({"eight": {
        "source": {"source": "directory", "path": str(mdir)},
        "installLocation": str(mdir)}}), encoding="utf-8")
    (mdir / ".claude-plugin").mkdir(parents=True)
    (mdir / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": "eight", "plugins": [{"name": "eight-backend",
                                      "source": "./plugins/eight-backend"}]}),
        encoding="utf-8")
    where = mdir / "plugins" / "eight-backend"
    return foreign.Plugin(PID, where), _skill(where / "skills" / "x", when=when)


class TestNewestCopy:
    @pytest.mark.parametrize("source", [foreign.DATE_GIT, foreign.DATE_FILES,
                                        foreign.DATE_BOUND])
    def test_boost_newer_than_any_plugin_date(self, source):
        assert foreign.newest_copy(NEW, OLD, source) == foreign.NEWER_IN_BOOST

    @pytest.mark.parametrize("source", [foreign.DATE_GIT, foreign.DATE_FILES])
    def test_plugin_newer_by_a_date_that_means_it(self, source):
        assert foreign.newest_copy(OLD, NEW, source) == foreign.NEWER_IN_PLUGIN

    def test_plugin_newer_by_an_upper_bound_proves_nothing(self):
        assert foreign.newest_copy(OLD, NEW, foreign.DATE_BOUND) == foreign.DIFFERS

    @pytest.mark.parametrize("source", [foreign.DATE_GIT, foreign.DATE_FILES,
                                        foreign.DATE_BOUND])
    def test_equal_dates_decide_nothing(self, source):
        assert foreign.newest_copy(OLD, OLD, source) == foreign.DIFFERS

    def test_by_one_second_either_way(self):
        assert foreign.newest_copy(OLD + 1, OLD, foreign.DATE_GIT) == foreign.NEWER_IN_BOOST
        assert foreign.newest_copy(OLD, OLD + 1, foreign.DATE_GIT) == foreign.NEWER_IN_PLUGIN

    @pytest.mark.parametrize("boost,plugin", [(None, OLD), (OLD, None), (None, None)])
    def test_a_missing_date_decides_nothing(self, boost, plugin):
        assert foreign.newest_copy(boost, plugin, foreign.DATE_GIT) == foreign.DIFFERS

    def test_an_unknown_source_decides_nothing_for_the_plugin(self):
        assert foreign.newest_copy(OLD, NEW, foreign.DATE_UNKNOWN) == foreign.DIFFERS

    def test_zero_is_a_date(self):
        assert foreign.newest_copy(1, 0, foreign.DATE_GIT) == foreign.NEWER_IN_BOOST


class TestPluginSkillUpdatedAt:
    def test_a_cache_dir_that_is_no_repo_is_bounded_by_its_file_times(self, sandbox):
        plugin, d = _cache_skill(when=NEW)
        assert foreign.plugin_skill_updated_at(plugin, d) == (NEW, foreign.DATE_BOUND)

    def test_a_cache_checkout_with_history_is_exact(self, sandbox):
        plugin, d = _cache_skill(when=NEW + 500)
        _repo(plugin.path, when=OLD)
        assert foreign.plugin_skill_updated_at(plugin, d) == (OLD, foreign.DATE_GIT)

    def test_a_shallow_checkout_is_bounded_by_its_head(self, sandbox, tmp_path):
        src = tmp_path / "upstream"
        _skill(src / "skills" / "x")
        _repo(src, when=OLD)
        (src / "other.md").write_text("x", encoding="utf-8")
        _git("add", "-A", cwd=src)
        _git("commit", "-qm", "later", cwd=src, when=NEW)
        inst = paths.home() / ".claude" / "plugins" / "marketplaces" / "eight"
        inst.parent.mkdir(parents=True)
        _git("clone", "-q", "--depth", "1", src.as_uri(), str(inst), cwd=tmp_path)
        os.utime(inst / "skills" / "x" / "SKILL.md", (NEW + 900, NEW + 900))
        got = foreign.plugin_skill_updated_at(foreign.Plugin(PID, inst),
                                              inst / "skills" / "x")
        assert got == (NEW, foreign.DATE_BOUND)

    def test_file_times_bound_it_when_they_are_older_than_the_head(self, sandbox,
                                                                   tmp_path):
        src = tmp_path / "upstream"
        _skill(src / "skills" / "x")
        _repo(src, when=NEW)
        inst = paths.home() / ".claude" / "plugins" / "marketplaces" / "eight"
        inst.parent.mkdir(parents=True)
        _git("clone", "-q", "--depth", "1", src.as_uri(), str(inst), cwd=tmp_path)
        os.utime(inst / "skills" / "x" / "SKILL.md", (OLD, OLD))
        got = foreign.plugin_skill_updated_at(foreign.Plugin(PID, inst),
                                              inst / "skills" / "x")
        assert got == (OLD, foreign.DATE_BOUND)

    def test_a_repo_outside_claude_codes_plugins_is_not_the_plugins_history(
            self, sandbox):
        # A dotfiles repo at $HOME that tracks ~/.claude dates the user's
        # commit, not the plugin's change.
        plugin, d = _cache_skill(when=NEW)
        _repo(paths.home(), when=OLD)
        assert foreign.plugin_skill_updated_at(plugin, d) == (NEW, foreign.DATE_BOUND)

    def test_a_folder_marketplace_is_dated_by_its_file_times(self, sandbox):
        plugin, d = _folder_skill(when=OLD)
        assert foreign.plugin_skill_updated_at(plugin, d) == (OLD, foreign.DATE_FILES)

    def test_a_clean_folder_repo_is_dated_by_its_commits(self, sandbox):
        plugin, d = _folder_skill(when=NEW)
        _repo(paths.home() / "src" / "eight", when=OLD)
        assert foreign.plugin_skill_updated_at(plugin, d) == (OLD, foreign.DATE_GIT)

    def test_an_edited_folder_repo_is_dated_by_its_file_times(self, sandbox):
        plugin, d = _folder_skill()
        _repo(paths.home() / "src" / "eight", when=OLD)
        (d / "SKILL.md").write_text("# edited\n", encoding="utf-8")
        os.utime(d / "SKILL.md", (NEW, NEW))
        assert foreign.plugin_skill_updated_at(plugin, d) == (NEW, foreign.DATE_FILES)

    def test_a_dir_with_no_files_has_no_date(self, sandbox):
        plugin, d = _cache_skill()
        (d / "SKILL.md").unlink()
        assert foreign.plugin_skill_updated_at(plugin, d) == (None, foreign.DATE_UNKNOWN)

    def test_without_git_it_still_answers(self, sandbox, monkeypatch):
        plugin, d = _cache_skill(when=NEW)
        monkeypatch.setattr(foreign.gitutil, "has_git", lambda: False)
        assert foreign.plugin_skill_updated_at(plugin, d) == (NEW, foreign.DATE_BOUND)


class TestReadsFolder:
    def test_a_folder_marketplace(self, sandbox):
        assert foreign.reads_folder(_folder_skill()[0])

    def test_a_cache_install(self, sandbox):
        assert not foreign.reads_folder(_cache_skill()[0])

    def test_an_id_without_a_marketplace(self, sandbox):
        assert not foreign.reads_folder(foreign.Plugin("loose", paths.home()))


class TestIsoTimes:
    def test_round_trip(self):
        assert util.iso_from_epoch(NEW) == "2021-01-01T00:00:00Z"
        assert util.epoch_from_iso("2021-01-01T00:00:00Z") == NEW

    def test_the_format_now_iso_writes(self):
        assert util.epoch_from_iso(util.now_iso()) is not None

    @pytest.mark.parametrize("bad", [None, "", "yesterday", 5, "2021-01-01"])
    def test_anything_else_is_no_time(self, bad):
        assert util.epoch_from_iso(bad) is None
