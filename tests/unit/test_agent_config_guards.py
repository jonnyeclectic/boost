# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit: three agent rows boost used to read wrongly.

An agent dir that *is* the canonical store (``~/.cursor/skills ->
~/.agents/skills``) was treated as a linking agent, so every store skill read
as a stranger's directory "in the way" and boost told the user to delete it. A
relative ``dir`` resolved against the cwd, so each working directory grew its
own skills tree. And a hand-written ``"enabled": "false"`` was ``bool()``-ed
to True.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

from boost_cli.core import (
    agents,
    catalog,
    config,
    paths,
    registry,
    store,
    typedvalue,
    util,
)
from boost_cli.errors import BoostError

needs_symlinks = pytest.mark.skipif(sys.platform == "win32",
                                    reason="symlink semantics differ on Windows")


@pytest.fixture(autouse=True)
def _fresh_warnings():
    saved = (set(agents._WARNED_DIRLESS), set(agents._WARNED_FLAGS))
    agents._WARNED_DIRLESS.clear()
    agents._WARNED_FLAGS.clear()
    yield
    agents._WARNED_DIRLESS.clear()
    agents._WARNED_DIRLESS.update(saved[0])
    agents._WARNED_FLAGS.clear()
    agents._WARNED_FLAGS.update(saved[1])


def _tap(src, dest):
    shutil.copytree(src, dest)
    registry.add(str(dest))


def _patch_row(name, **fields):
    cfg = config.load()
    cfg["agents"].setdefault(name, {}).update(fields)
    config.save(cfg)


class TestStringBooleans:
    @pytest.mark.parametrize("raw", ["false", "False", " no ", "0", "off", 0])
    def test_false_words_disable_the_agent(self, sandbox, raw):
        _patch_row("cursor", enabled=raw)
        assert agents.known_agents()["cursor"]["enabled"] is False
        assert "cursor" not in agents.enabled_agents()
        assert "cursor" not in agents.linking_agents()
        assert agents.bad_flags() == []

    @pytest.mark.parametrize("raw", ["true", "YES", "1", "on", 1, True])
    def test_true_words_enable_it(self, sandbox, raw):
        _patch_row("cursor", enabled=raw)
        assert agents.known_agents()["cursor"]["enabled"] is True
        assert "cursor" in agents.linking_agents()

    def test_links_skills_string_false_keeps_gemini_native(self, sandbox):
        _patch_row("gemini", links_skills="true")
        assert "gemini" in agents.linking_agents()
        _patch_row("gemini", links_skills="false")
        assert "gemini" in agents.native_store_agents()
        assert "gemini" not in agents.linking_agents()
        assert "gemini" not in agents.unlinking_agents()

    @pytest.mark.parametrize("key", sorted(agents.FLAG_DEFAULTS))
    def test_every_flag_reads_the_word(self, sandbox, key):
        _patch_row("zed", dir="~/.zed/skills", **{key: "no"})
        assert agents.known_agents()["zed"][key] is False
        _patch_row("zed", **{key: "yes"})
        assert agents.known_agents()["zed"][key] is True

    def test_junk_reads_as_the_agent_s_own_default(self, sandbox):
        _patch_row("gemini", links_skills="nope")
        _patch_row("cursor", enabled=[1])
        known = agents.known_agents()
        # gemini's DEFAULTS row says False, so junk must not start linking.
        assert known["gemini"]["links_skills"] is False
        assert known["cursor"]["enabled"] is True
        assert agents.bad_flags() == [("cursor", "enabled", [1]),
                                      ("gemini", "links_skills", "nope")]

    def test_junk_warns_once_naming_the_key(self, sandbox, capsys):
        _patch_row("gemini", links_skills="nope")
        agents.known_agents()
        agents.known_agents()
        err = capsys.readouterr().err
        assert err.count("agents.gemini.links_skills expects") == 1
        assert "got 'nope'" in err
        assert "boost reads it as false" in err
        assert ("boost config set agents.gemini.links_skills <true|false>"
                in " ".join(err.split()))

    def test_claim_silences_the_warning(self, sandbox, capsys):
        _patch_row("gemini", links_skills="nope")
        assert agents.bad_flags(claim=True) == [("gemini", "links_skills",
                                                 "nope")]
        agents.known_agents()
        assert "links_skills" not in capsys.readouterr().err

    def test_unclaimed_bad_flags_keeps_the_warning(self, sandbox, capsys):
        _patch_row("gemini", links_skills="nope")
        agents.bad_flags()
        agents.known_agents()
        assert "agents.gemini.links_skills" in capsys.readouterr().err

    def test_flag_default(self):
        assert agents.flag_default("gemini", "links_skills") is False
        assert agents.flag_default("cursor", "links_skills") is True
        assert agents.flag_default("antigravity", "skills_only") is True
        assert agents.flag_default("zed", "enabled") is True
        assert agents.flag_default("zed", "dedupes_by_path") is False

    def test_bad_flags_skips_a_non_dict_row(self, sandbox):
        cfg = config.load()
        cfg["agents"]["zed"] = "oops"
        config.save(cfg)
        assert agents.bad_flags() == []

    def test_read_flag_reads_an_int_as_its_digit(self):
        assert agents._read_flag("x", "enabled", 0) is False
        assert agents._read_flag("x", "enabled", 1) is True
        with pytest.raises(typedvalue.ValueTypeError) as e:
            agents._read_flag("x", "enabled", 2)
        assert e.value.key == "agents.x.enabled"


class TestRelativeDir:
    def test_config_set_refuses_it(self, sandbox):
        with pytest.raises(typedvalue.ValueTypeError) as e:
            config.set_value("agents.cursor.dir", "cursor-rel/skills")
        assert str(e.value) == (
            "agents.cursor.dir expects an absolute path, or one starting with "
            "~ or ${VAR} — a relative dir resolves against the working "
            "directory, got 'cursor-rel/skills'")
        assert config.get("agents.cursor.dir") == "~/.cursor/skills"

    @pytest.mark.parametrize("raw", ["~/.zed/skills", "${BOOST_TEST_REL_NOPE}/s",
                                     "${BOOST_TEST_REL_NOPE:-~/.z}/s"])
    def test_config_set_takes_home_var_and_absolute(self, sandbox, monkeypatch,
                                                    raw):
        monkeypatch.delenv("BOOST_TEST_REL_NOPE", raising=False)
        config.set_value("agents.zed.dir", raw)
        assert config.get("agents.zed.dir") == raw
        config.set_value("agents.zed.dir", str(sandbox / "abs" / "skills"))

    def test_only_the_dir_key_is_checked(self, sandbox):
        config.set_value("agents.cursor.project_dir", "rel")
        assert config.get("agents.cursor.project_dir") == "rel"

    @pytest.mark.parametrize("raw", [None, 3, "", "  ", "~/x",
                                     "${BOOST_TEST_REL_NOPE}/x"])
    def test_check_dir_passes(self, monkeypatch, raw):
        monkeypatch.delenv("BOOST_TEST_REL_NOPE", raising=False)
        assert agents.check_dir(raw) is None

    def test_check_dir_passes_an_absolute_path(self, tmp_path):
        assert agents.check_dir(str(tmp_path / "x")) is None

    @pytest.mark.parametrize("raw", ["rel", "./rel/skills", "../up/skills",
                                     "${BOOST_TEST_REL_NOPE:-rel}/skills"])
    def test_check_dir_refuses(self, monkeypatch, raw):
        monkeypatch.delenv("BOOST_TEST_REL_NOPE", raising=False)
        assert agents.check_dir(raw) == (
            "an absolute path, or one starting with ~ or ${VAR} — a relative "
            "dir resolves against the working directory")

    def test_hand_edited_row_is_named_and_refused(self, sandbox):
        _patch_row("cursor", dir="cursor-rel/skills")
        [(name, err)] = agents.check()
        assert name == "cursor"
        assert isinstance(err, agents.RelativeAgentDir)
        assert err.message == ("'cursor-rel/skills' is a relative path, which "
                               "would resolve against whatever directory "
                               "boost runs from")
        assert err.hint == ("use an absolute path, or one starting with ~ or "
                            "${VAR}")
        assert agents.dirless() == []
        with pytest.raises(BoostError) as e:
            agents.known_agents()
        assert e.value.message.startswith(
            "agents.cursor.dir: 'cursor-rel/skills' is a relative path")
        assert e.value.hint == err.hint

    @needs_symlinks
    def test_install_writes_nothing_under_any_cwd(self, sandbox,
                                                  fixture_tap_src, tmp_path):
        _tap(fixture_tap_src, tmp_path / "rel-dir-tap")
        _patch_row("cursor", dir="cursor-rel/skills")
        for w in ("w1", "w2"):
            cwd = tmp_path / w
            cwd.mkdir()
            os.chdir(cwd)
            with pytest.raises(BoostError):
                store.install(catalog.resolve_one("brainstorming"))
            assert list(cwd.iterdir()) == []
        assert not (paths.store_dir() / "brainstorming").exists()


@needs_symlinks
class TestDirAliasesTheStore:
    @pytest.fixture()
    def aliased(self, sandbox, fixture_tap_src, tmp_path):
        _tap(fixture_tap_src, tmp_path / "alias-tap")
        store.install(catalog.resolve_one("brainstorming"))
        cursor = sandbox / ".cursor" / "skills"
        util.rmtree(cursor)
        cursor.symlink_to(paths.store_dir())
        return cursor

    def test_aliases_store(self, sandbox, aliased, tmp_path):
        assert agents.aliases_store(aliased) is True
        assert agents.aliases_store(sandbox / ".agents" / "skills") is True
        assert agents.aliases_store(sandbox / ".claude" / "skills") is False
        assert agents.aliases_store(tmp_path / "nowhere" / "skills") is False

    def test_aliases_store_asks_by_inode(self, sandbox, tmp_path,
                                         monkeypatch):
        other = tmp_path / "Other"
        other.mkdir()
        monkeypatch.setattr(agents.os.path, "samefile", lambda a, b: True)
        assert agents.aliases_store(other) is True

    def test_aliases_store_samefile_error_is_false(self, sandbox, tmp_path,
                                                   monkeypatch):
        def boom(a, b):
            raise OSError("gone")
        monkeypatch.setattr(agents.os.path, "samefile", boom)
        assert agents.aliases_store(tmp_path) is False

    def test_aliases_store_resolve_error_is_false(self, sandbox, tmp_path,
                                                  monkeypatch):
        def boom(self, strict=False):
            raise RuntimeError("loop")
        monkeypatch.setattr(agents.Path, "resolve", boom)
        assert agents.aliases_store(tmp_path) is False

    def test_aliases_store_fails_closed(self, sandbox, tmp_path):
        loop = tmp_path / "loop"
        loop.symlink_to(loop)
        assert agents.aliases_store(loop) is False

    def test_reads_as_native_store(self, aliased):
        spec = agents.known_agents()["cursor"]
        assert spec["store_alias"] is True
        assert spec["links_skills"] is False
        assert agents.known_agents()["claude-code"]["store_alias"] is False
        assert "cursor" not in agents.linking_agents()
        assert "cursor" not in agents.unlinking_agents()
        assert "cursor" in agents.native_store_agents()
        assert aliased not in agents.sweep_dirs()

    def test_former_dir_that_is_the_store_is_not_swept(self, sandbox, aliased):
        _patch_row("cursor", dir=str(sandbox / "elsewhere" / "skills"))
        assert agents.known_agents()["cursor"]["store_alias"] is False
        assert all(d != aliased for _a, d in agents.former_link_dirs())
        assert aliased not in agents.sweep_dirs()

    def test_install_sync_uninstall_leave_the_store_intact(self, sandbox,
                                                           aliased):
        res = store.install(catalog.resolve_one("tdd-workflow"))
        assert "cursor" not in (res.linked or [])
        assert "cursor" in res.native
        assert store.plan_issues(store.sync_plan()) == 0
        assert store.duplicate_discovery() == []
        store.uninstall("tdd-workflow")
        assert (sandbox / ".agents" / "skills" / "brainstorming").is_dir()
        assert not (sandbox / ".agents" / "skills" / "tdd-workflow").exists()
        assert (sandbox / ".claude" / "skills" / "brainstorming").is_symlink()
        assert store.plan_issues(store.sync_plan()) == 0
