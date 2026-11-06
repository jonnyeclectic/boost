# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Whose a skill is: vendor built-ins, enabled Claude Code plugins, agent dirs.

`boost sync` deletes what this module calls a copy (behind `--prune`) and
drops a Claude Code link to what it calls a plugin's skill, so both directions
are pinned: what counts, and — just as much — what must not.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from boost_cli.core import config, foreign, paths

#: The real function: the sandbox fixture points the module's name at a dir
#: that does not exist, so a machine's own policy never reaches a test.
REAL_MANAGED_DIR = foreign.managed_settings_dir

#: ``_plugin(enabled=NO_ROW)`` writes no ``enabledPlugins`` row at all.
NO_ROW = object()


def _skill(d: Path, body: str = "# s\n") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _plugins_root() -> Path:
    return paths.home() / ".claude" / "plugins"


def _plugin(pid: str = "eight-backend@eight", skills=("eight-adr",), *,
            entry=None, manifest=None, enabled=True, scope="user") -> Path:
    """Install one plugin the way Claude Code records it; return its dir.

    ``entry`` is the marketplace entry's extra keys (``{"skills": [...]}``);
    None leaves the entry with no ``skills`` key. ``manifest`` is the
    plugin's own ``.claude-plugin/plugin.json``; None writes none. ``enabled``
    is the user's ``enabledPlugins`` value, and :data:`NO_ROW` writes none.
    """
    name, market = pid.split("@")
    inst = _plugins_root() / "cache" / market / name / "abc123"
    for s in skills:
        _skill(inst / "skills" / s, "# %s from %s\n" % (s, name))
    settings = paths.home() / ".claude" / "settings.json"
    cur = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
    rows = cur.setdefault("enabledPlugins", {})
    if enabled is not NO_ROW:
        rows[pid] = enabled
    _write(settings, cur)
    rec = _plugins_root() / "installed_plugins.json"
    cur = json.loads(rec.read_text(encoding="utf-8")) if rec.exists() else {"version": 2, "plugins": {}}
    cur["plugins"][pid] = [{"scope": scope, "installPath": str(inst),
                            "version": "abc123"}]
    _write(rec, cur)
    mroot = _plugins_root() / "marketplaces" / market
    mfile = mroot / ".claude-plugin" / "marketplace.json"
    cur = json.loads(mfile.read_text(encoding="utf-8")) if mfile.exists() else {"name": market,
                                                                 "plugins": []}
    cur["plugins"].append({"name": name, "source": "./", **(entry or {})})
    _write(mfile, cur)
    _write(_plugins_root() / "known_marketplaces.json",
           {market: {"installLocation": str(mroot)}})
    if manifest is not None:
        _write(inst / ".claude-plugin" / "plugin.json", manifest)
    return inst


class TestSkillsIn:
    def test_lists_skill_dirs_by_name_and_skips_the_rest(self, sandbox):
        root = paths.home() / "d"
        _skill(root / "b")
        _skill(root / "a")
        (root / "not-a-skill").mkdir()
        _skill(root / ".system" / "hidden")
        _skill(root / ".dot")
        (root / "file.md").write_text("x", encoding="utf-8")
        assert foreign._skills_in(root) == [("a", root / "a"), ("b", root / "b")]

    def test_a_missing_root_holds_nothing(self, sandbox):
        assert foreign._skills_in(paths.home() / "nope") == []


class TestVendorDirs:
    def test_none_until_a_vendor_dir_exists(self, sandbox):
        assert foreign.vendor_dirs() == []

    def test_cursor_beside_its_skills_dir_and_codex_inside_its_own(self, sandbox):
        cursor = paths.home() / ".cursor" / "skills-cursor"
        codex = paths.home() / ".codex" / "skills" / ".system"
        cursor.mkdir(parents=True)
        codex.mkdir(parents=True)
        assert foreign.vendor_dirs() == [("Cursor's built-ins", cursor),
                                         ("Codex's built-ins", codex)]

    def test_a_relocated_agent_dir_moves_its_vendor_dir(self, sandbox):
        cfg = config.load()
        cfg["agents"]["cursor"]["dir"] = str(paths.home() / "elsewhere" / "skills")
        config.save(cfg)
        (paths.home() / ".cursor" / "skills-cursor").mkdir(parents=True)
        moved = paths.home() / "elsewhere" / "skills-cursor"
        moved.mkdir(parents=True)
        assert foreign.vendor_dirs() == [("Cursor's built-ins", moved)]

    def test_an_agent_with_no_row_has_no_vendor_dir(self, sandbox, monkeypatch):
        (paths.home() / ".cursor" / "skills-cursor").mkdir(parents=True)
        (paths.home() / ".codex" / "skills" / ".system").mkdir(parents=True)
        monkeypatch.setattr(foreign.agents, "known_agents", dict)
        assert foreign.vendor_dirs() == []


def _agent_dir(row, monkeypatch=None):
    """Replace the claude-code agent row, or, given None, hide it.

    Hidden rather than deleted: config merges its defaults back in, so a row
    removed from the file is still there on the next read.
    """
    if row is None:
        rows = foreign.agents.known_agents()
        rows.pop("claude-code")
        monkeypatch.setattr(foreign.agents, "known_agents", lambda: rows)
        return
    cfg = config.load()
    cfg["agents"]["claude-code"] = {"enabled": True, **(
        row if isinstance(row, dict) else {"dir": row})}
    config.save(cfg)


class TestHomes:
    def test_defaults_under_home(self, sandbox):
        assert foreign.claude_home() == paths.home() / ".claude"
        assert foreign.plugins_root() == paths.home() / ".claude" / "plugins"

    def test_the_profile_that_reads_boosts_links_wins_over_the_env(
            self, sandbox, monkeypatch, tmp_path):
        # The shell's CLAUDE_CONFIG_DIR names whichever profile launched it;
        # the plugins that load beside ~/.claude/skills are ~/.claude's.
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "personal"))
        assert foreign.claude_home() == paths.home() / ".claude"
        assert foreign.plugins_root() == paths.home() / ".claude" / "plugins"

    def test_a_relocated_agent_dir_moves_the_home(self, sandbox, tmp_path):
        _agent_dir(str(tmp_path / "work" / "skills"))
        assert foreign.claude_home() == tmp_path / "work"

    @pytest.mark.parametrize("row", [None, {"dir": "~/.claude/my-skills"},
                                     {"dir": "${BOOST_NO_SUCH_VAR}/skills"}])
    def test_without_a_usable_agent_row_the_env_answers(
            self, sandbox, monkeypatch, tmp_path, row):
        _agent_dir(row, monkeypatch)
        assert foreign.claude_home() == paths.home() / ".claude"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cc"))
        assert foreign.claude_home() == tmp_path / "cc"
        assert foreign.plugins_root() == tmp_path / "cc" / "plugins"

    def test_an_absolute_plugin_cache_override_is_honoured(
            self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "pc"))
        assert foreign.plugins_root() == tmp_path / "pc"

    def test_relative_overrides_are_ignored(self, sandbox, monkeypatch):
        _agent_dir(None, monkeypatch)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "rel/cc")
        monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", "rel/pc")
        assert foreign.claude_home() == paths.home() / ".claude"
        assert foreign.plugins_root() == paths.home() / ".claude" / "plugins"


class TestHiddenVendorSkill:
    @pytest.fixture
    def cursor(self, sandbox) -> Path:
        d = paths.home() / ".cursor" / "skills-cursor"
        _skill(d / "automate")
        return d

    def test_none_without_a_vendor_dir(self, sandbox):
        assert foreign.hidden_vendor_skill("automate") is None

    @pytest.mark.parametrize("name", ["automate", "absent"])
    def test_none_where_it_can_look(self, cursor, name):
        assert foreign.hidden_vendor_skill(name) is None

    def test_none_for_what_is_not_a_skill(self, cursor):
        (cursor / "empty").mkdir()
        (cursor / "file").write_text("x", encoding="utf-8")
        assert foreign.hidden_vendor_skill("empty") is None
        assert foreign.hidden_vendor_skill("file") is None

    def test_the_skill_dir_it_cannot_look_in(self, cursor, locked):
        locked(cursor / "automate")
        assert foreign.hidden_vendor_skill("automate") == cursor / "automate"
        assert foreign.hidden_vendor_skill("absent") is None

    @pytest.mark.parametrize("name", ["automate", "absent"])
    def test_the_vendor_dir_when_it_cannot_be_searched(self, cursor, locked, name):
        locked(cursor)
        assert foreign.hidden_vendor_skill(name) == cursor

    def test_every_vendor_dir_is_asked(self, cursor, locked):
        codex = paths.home() / ".codex" / "skills" / ".system"
        _skill(codex / "automate")
        locked(codex / "automate")
        assert foreign.hidden_vendor_skill("automate") == codex / "automate"


class TestEnabledPlugins:
    def test_none_without_records(self, sandbox):
        assert foreign.enabled_plugins() == []

    def test_an_enabled_user_install(self, sandbox):
        inst = _plugin()
        assert foreign.enabled_plugins() == [foreign.Plugin("eight-backend@eight", inst)]
        assert foreign.enabled_plugins()[0].name == "eight-backend"

    def test_sorted_by_id(self, sandbox):
        b = _plugin("b-plugin@m")
        a = _plugin("a-plugin@m")
        assert [p.path for p in foreign.enabled_plugins()] == [a, b]

    def test_false_disables(self, sandbox):
        _plugin(enabled=False)
        assert foreign.enabled_plugins() == []

    def test_a_disabled_plugin_does_not_hide_the_next_one(self, sandbox):
        _plugin("a-off@m", enabled=False)
        inst = _plugin("b-on@m")
        assert foreign.enabled_plugins() == [foreign.Plugin("b-on@m", inst)]

    def test_an_install_with_no_row_starts_enabled(self, sandbox):
        # "A plugin with no entry at any scope falls back to its
        # defaultEnabled value", and that defaults to true.
        inst = _plugin(enabled=NO_ROW)
        assert foreign.enabled_plugins() == [foreign.Plugin("eight-backend@eight", inst)]

    @pytest.mark.parametrize("enabled", ["false", "true", 0, 1, None, ["^1.0.0"], {}])
    def test_any_value_but_true_is_a_no(self, sandbox, enabled):
        # Claude Code 2.1.300 lists the plugin as disabled for the
        # version-constraint form, which read here as no answer, and so as
        # enabled by default.
        _plugin(enabled=enabled)
        assert foreign.enabled_plugins() == []

    @pytest.mark.parametrize("key,value,expected", [
        ("EIGHT-BACKEND@EIGHT", False, False),
        ("Eight-Backend@Eight", True, True),
    ])
    def test_the_id_matches_whatever_its_case(self, sandbox, key, value, expected):
        _plugin(enabled=NO_ROW, entry={"defaultEnabled": not expected})
        settings = paths.home() / ".claude" / "settings.json"
        _write(settings, {"enabledPlugins": {key: value}})
        assert bool(foreign.enabled_plugins()) is expected

    def test_two_spellings_say_yes_only_together(self, sandbox):
        _plugin()
        settings = paths.home() / ".claude" / "settings.json"
        _write(settings, {"enabledPlugins": {"eight-backend@eight": True,
                                             "EIGHT-backend@eight": False}})
        assert foreign.enabled_plugins() == []
        _write(settings, {"enabledPlugins": {"eight-backend@eight": True,
                                             "EIGHT-backend@eight": True}})
        assert len(foreign.enabled_plugins()) == 1

    def test_the_users_row_outranks_default_enabled(self, sandbox):
        _plugin(entry={"defaultEnabled": False})
        assert len(foreign.enabled_plugins()) == 1

    @pytest.mark.parametrize("entry,manifest,expected", [
        ({"defaultEnabled": False}, None, False),
        (None, {"defaultEnabled": False}, False),
        ({"defaultEnabled": True}, {"defaultEnabled": False}, True),
        ({"defaultEnabled": "no"}, {"defaultEnabled": False}, False),
        (None, {"defaultEnabled": True}, True),
    ])
    def test_default_enabled_the_entrys_over_the_manifests(self, sandbox, entry,
                                                          manifest, expected):
        _plugin(enabled=NO_ROW, entry=entry, manifest=manifest)
        assert bool(foreign.enabled_plugins()) is expected

    def test_an_unreadable_manifest_leaves_the_default(self, sandbox):
        inst = _plugin(enabled=NO_ROW)
        (inst / ".claude-plugin").mkdir()
        (inst / ".claude-plugin" / "plugin.json").write_text("{nope", encoding="utf-8")
        assert len(foreign.enabled_plugins()) == 1

    @pytest.mark.parametrize("managed,user,expected", [
        (False, True, False),
        (True, False, True),
        ("off", False, False),
        ("off", True, False),
        (["^1.0.0"], True, False),
    ])
    def test_managed_settings_outrank_the_users(self, sandbox, monkeypatch, tmp_path,
                                                managed, user, expected):
        monkeypatch.setattr(foreign, "managed_settings_dir", lambda: tmp_path / "m")
        _write(tmp_path / "m" / "managed-settings.json",
               {"enabledPlugins": {"eight-backend@eight": managed}})
        _plugin(enabled=user)
        assert bool(foreign.enabled_plugins()) is expected

    def test_a_managed_id_matches_whatever_its_case(self, sandbox, monkeypatch,
                                                    tmp_path):
        monkeypatch.setattr(foreign, "managed_settings_dir", lambda: tmp_path / "m")
        _write(tmp_path / "m" / "managed-settings.json",
               {"enabledPlugins": {"Eight-Backend@EIGHT": False}})
        _plugin()
        assert foreign.enabled_plugins() == []

    def test_a_project_scope_install_is_not_counted(self, sandbox):
        _plugin(scope="project")
        assert foreign.enabled_plugins() == []

    def test_one_with_no_user_install_does_not_hide_the_next(self, sandbox):
        _plugin("a-project@m", scope="project")
        inst = _plugin("b-user@m")
        assert foreign.enabled_plugins() == [foreign.Plugin("b-user@m", inst)]

    def test_a_relative_install_path_is_not_counted(self, sandbox):
        # It would be read against the working directory, where a tap
        # checkout's skills/ could pass for a plugin's.
        _plugin()
        os.mkdir("rel")
        rec = _plugins_root() / "installed_plugins.json"
        _write(rec, {"version": 2, "plugins": {"eight-backend@eight": [
            {"scope": "user", "installPath": "rel"}]}})
        assert foreign.enabled_plugins() == []

    def test_an_install_path_that_is_gone_is_not_counted(self, sandbox):
        inst = _plugin()
        os.rename(inst, inst.with_name("moved"))
        assert foreign.enabled_plugins() == []

    def test_first_usable_row_wins(self, sandbox):
        inst = _plugin()
        rec = _plugins_root() / "installed_plugins.json"
        data = json.loads(rec.read_text(encoding="utf-8"))
        good = data["plugins"]["eight-backend@eight"][0]
        other = _plugins_root() / "other"
        other.mkdir()
        data["plugins"]["eight-backend@eight"] = [
            "junk", {"scope": "project", "installPath": str(other)},
            {"scope": "user", "installPath": 7}, good,
            {"scope": "user", "installPath": str(other)}]
        _write(rec, data)
        assert foreign.enabled_plugins() == [foreign.Plugin("eight-backend@eight", inst)]

    @pytest.mark.parametrize("records", [{"plugins": ["x"]},
                                         {"plugins": {"eight-backend@eight": "x"}},
                                         {"plugins": {"eight-backend@eight": None}},
                                         {"plugins": {"eight-backend@eight": [None]}}])
    def test_misshapen_records_yield_nothing(self, sandbox, records):
        _plugin()
        _write(_plugins_root() / "installed_plugins.json", records)
        assert foreign.enabled_plugins() == []

    def test_a_corrupt_record_yields_nothing(self, sandbox):
        _plugin()
        (_plugins_root() / "installed_plugins.json").write_text("{nope", encoding="utf-8")
        assert foreign.enabled_plugins() == []

    @pytest.mark.parametrize("text", ['{"enabledPlugins": ["x"]}', "{nope"])
    def test_settings_that_cannot_be_read_answer_nothing(self, sandbox, text):
        # Claude Code skips a broken value and goes on, so the default stands.
        _plugin(entry={"defaultEnabled": False})
        _plugin("p@m")
        (paths.home() / ".claude" / "settings.json").write_text(text, encoding="utf-8")
        assert [p.id for p in foreign.enabled_plugins()] == ["p@m"]

    def test_an_unsearchable_plugins_dir_yields_nothing(self, sandbox, monkeypatch):
        # Python 3.12/3.13: Path.exists raises under a dir with no search bit.
        _plugin()
        claude = paths.home() / ".claude"
        real = foreign.jsonstate.read_object

        def boom(path):
            if claude in path.parents:
                raise PermissionError("no search bit")
            return real(path)
        monkeypatch.setattr(foreign.jsonstate, "read_object", boom)
        assert foreign.enabled_plugins() == []
        assert foreign.plugin_index() == {}


class TestManagedSettings:
    @pytest.mark.parametrize("platform,expected", [
        ("darwin", Path("/Library/Application Support/ClaudeCode")),
        ("win32", Path(r"C:\Program Files\ClaudeCode")),
        ("linux", Path("/etc/claude-code")),
    ])
    def test_where_each_platform_keeps_them(self, monkeypatch, platform, expected):
        monkeypatch.setattr(foreign.sys, "platform", platform)
        assert REAL_MANAGED_DIR() == expected

    def test_none_where_there_are_none(self, sandbox):
        assert foreign.managed_plugin_states() == {}

    def test_the_file_then_its_drop_ins_in_order(self, sandbox, monkeypatch, tmp_path):
        root = tmp_path / "m"
        monkeypatch.setattr(foreign, "managed_settings_dir", lambda: root)
        _write(root / "managed-settings.json",
               {"enabledPlugins": {"a@m": False, "b@m": False, "bad@m": "yes"}})
        drop = root / "managed-settings.d"
        _write(drop / "20-second.json", {"enabledPlugins": {"c@m": True, "a@m": True}})
        _write(drop / "10-first.json", {"enabledPlugins": {"c@m": False, "b@m": 1}})
        _write(drop / ".30-hidden.json", {"enabledPlugins": {"a@m": False,
                                                             "h@m": True}})
        _write(drop / "40-notes.txt", {"enabledPlugins": {"b@m": True}})
        _write(drop / "50-other.json", {"enabledPlugins": ["x"]})
        # Every value is kept, for the reader to call anything but true a no.
        assert foreign.managed_plugin_states() == {"a@m": True, "b@m": 1,
                                                   "bad@m": "yes", "c@m": True}

    def test_an_unreadable_drop_in_dir_leaves_the_file(self, sandbox, monkeypatch,
                                                       tmp_path):
        root = tmp_path / "m"
        monkeypatch.setattr(foreign, "managed_settings_dir", lambda: root)
        _write(root / "managed-settings.json", {"enabledPlugins": {"a@m": False}})
        _write(root / "managed-settings.d" / "x.json", {"enabledPlugins": {"a@m": True}})
        real = os.listdir

        def boom(path):
            if str(path).endswith("managed-settings.d"):
                raise PermissionError("no")
            return real(path)
        monkeypatch.setattr(foreign.os, "listdir", boom)
        assert foreign.managed_plugin_states() == {"a@m": False}


class TestPluginName:
    def test_strips_the_marketplace(self):
        assert foreign.Plugin("p@m", Path("/x")).name == "p"

    def test_an_id_without_a_marketplace_is_its_own_name(self):
        assert foreign.Plugin("p", Path("/x")).name == "p"


class TestMarketplaceEntry:
    def test_found_through_known_marketplaces(self, sandbox):
        _plugin(entry={"skills": ["./skills/eight-adr"]})
        plugin = foreign.enabled_plugins()[0]
        assert foreign._marketplace_entry(plugin) == {
            "name": "eight-backend", "source": "./", "skills": ["./skills/eight-adr"]}

    def test_falls_back_to_the_default_marketplace_dir(self, sandbox):
        _plugin(entry={"skills": []})
        _write(_plugins_root() / "known_marketplaces.json", {})
        plugin = foreign.enabled_plugins()[0]
        assert foreign._marketplace_entry(plugin)["skills"] == []

    def test_a_relocated_marketplace_is_read_where_it_is(self, sandbox, tmp_path):
        _plugin()
        moved = tmp_path / "market"
        _write(moved / ".claude-plugin" / "marketplace.json",
               {"plugins": [{"name": "eight-backend", "skills": ["x"]}]})
        _write(_plugins_root() / "known_marketplaces.json",
               {"eight": {"installLocation": str(moved)}})
        plugin = foreign.enabled_plugins()[0]
        assert foreign._marketplace_entry(plugin) == {"name": "eight-backend",
                                                      "skills": ["x"]}

    def test_a_relative_install_location_is_not_followed(self, sandbox):
        _plugin(entry={"skills": ["./skills/eight-adr"]})
        os.mkdir("rel")
        _write(Path("rel") / ".claude-plugin" / "marketplace.json",
               {"plugins": [{"name": "eight-backend", "skills": ["x"]}]})
        _write(_plugins_root() / "known_marketplaces.json",
               {"eight": {"installLocation": "rel"}})
        plugin = foreign.enabled_plugins()[0]
        assert foreign._marketplace_entry(plugin)["skills"] == ["./skills/eight-adr"]

    @pytest.mark.parametrize("plugins", [[], [{"name": "other"}], ["junk"], "x"])
    def test_no_matching_entry(self, sandbox, plugins):
        _plugin()
        _write(_plugins_root() / "marketplaces" / "eight" / ".claude-plugin"
               / "marketplace.json", {"plugins": plugins})
        assert foreign._marketplace_entry(foreign.enabled_plugins()[0]) is None

    def test_an_id_without_a_marketplace_has_no_entry(self, sandbox):
        assert foreign._marketplace_entry(foreign.Plugin("p", Path("/x"))) is None


def _dir_market(source="./plugins/eight-backend", *, kind="directory", entry=None):
    """Re-home the default plugin's marketplace in a folder of the user's.

    ``claude plugin marketplace add <dir>`` records it as ``{"source":
    "directory"}`` with that dir as ``installLocation``, and Claude Code then
    reads a plugin from ``<dir>/<source>``, not from its ``installPath``.
    The folder's ``eight-adr`` differs from the cached one. Returns
    ``(cache, folder)``.
    """
    inst = _plugin()
    mdir = paths.home() / "src" / "eight"
    record = {"source": {"source": kind, "path": str(mdir)},
              "installLocation": str(mdir)}
    if kind is None:
        del record["source"]
    _write(_plugins_root() / "known_marketplaces.json", {"eight": record})
    _write(mdir / ".claude-plugin" / "marketplace.json",
           {"name": "eight", "plugins": [entry or {"name": "eight-backend",
                                                   "source": source}]})
    folder = mdir / source
    _skill(folder / "skills" / "eight-adr", "# edited in the folder\n")
    return inst, folder


class TestDirectoryMarketplace:
    def test_the_folder_is_read_not_the_cache(self, sandbox):
        _inst, folder = _dir_market()
        assert [p.path for p in foreign.enabled_plugins()] == [folder]
        assert _skills() == {"eight-adr": folder / "skills" / "eight-adr"}

    def test_the_folders_plugin_json_is_read(self, sandbox):
        inst, folder = _dir_market()
        _write(inst / ".claude-plugin" / "plugin.json", {"skills": ["./old"]})
        _skill(inst / "old" / "old")
        _write(folder / ".claude-plugin" / "plugin.json", {"skills": ["./extra"]})
        _skill(folder / "extra" / "x")
        assert sorted(_skills()) == ["eight-adr", "x"]

    @pytest.mark.parametrize("source", ["./", ".", "././"])
    def test_its_own_root(self, sandbox, source):
        _dir_market(source)
        assert [p.path for p in foreign.enabled_plugins()] == [paths.home() / "src" / "eight"]

    def test_a_source_that_leaves_it_loads_nothing(self, sandbox):
        # Claude Code refuses it and does not fall back to the installPath.
        _dir_market("../outside")
        assert foreign.enabled_plugins() == []

    def test_an_absolute_source_loads_nothing(self, sandbox):
        _dir_market(entry={"name": "eight-backend",
                           "source": str(paths.home() / "src" / "eight")})
        assert foreign.enabled_plugins() == []

    @pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges")
    def test_a_link_that_leaves_it_loads_nothing(self, sandbox):
        outside = _skill(paths.home() / "outside" / "skills" / "eight-adr").parent.parent
        mdir = paths.home() / "src" / "eight"
        _dir_market("./plugins/eight-backend")
        target = mdir / "plugins" / "linked"
        target.symlink_to(outside, target_is_directory=True)
        _write(mdir / ".claude-plugin" / "marketplace.json",
               {"plugins": [{"name": "eight-backend", "source": "./plugins/linked"}]})
        assert foreign.enabled_plugins() == []

    def test_a_missing_folder_loads_nothing(self, sandbox):
        _inst, folder = _dir_market()
        shutil.rmtree(folder)
        assert foreign.plugin_index() == {}

    @pytest.mark.parametrize("kind", ["github", "git", "url", "file", None])
    def test_another_kind_of_marketplace_keeps_the_install_path(self, sandbox, kind):
        inst, _folder = _dir_market(kind=kind)
        assert [p.path for p in foreign.enabled_plugins()] == [inst]

    @pytest.mark.parametrize("record", ["directory", {}, [], None])
    def test_a_record_that_is_not_a_source_object_keeps_it(self, sandbox, record):
        inst, _folder = _dir_market()
        mdir = paths.home() / "src" / "eight"
        _write(_plugins_root() / "known_marketplaces.json",
               {"eight": {"source": record, "installLocation": str(mdir)}})
        assert [p.path for p in foreign.enabled_plugins()] == [inst]

    @pytest.mark.parametrize("source", [{"source": "github", "repo": "o/r"}, None, 3])
    def test_an_entry_source_that_is_not_a_path_keeps_it(self, sandbox, source):
        inst, _folder = _dir_market(entry={"name": "eight-backend", "source": source})
        assert [p.path for p in foreign.enabled_plugins()] == [inst]

    def test_no_entry_keeps_it(self, sandbox):
        inst, _folder = _dir_market(entry={"name": "someone-else", "source": "./x"})
        assert [p.path for p in foreign.enabled_plugins()] == [inst]


class TestListed:
    def test_a_string_is_one_path(self):
        assert foreign._listed("./skills/a") == ["./skills/a"]

    def test_a_list_keeps_its_strings(self):
        assert foreign._listed(["a", 1, None, "b"]) == ["a", "b"]

    @pytest.mark.parametrize("value", [None, 3, {"a": 1}])
    def test_anything_else_is_no_list(self, value):
        assert foreign._listed(value) is None


class TestResolveListed:
    def test_a_skill_path_and_a_dir_of_skills(self, sandbox):
        root = paths.home() / "plug"
        one = _skill(root / "skills" / "one")
        two = _skill(root / "more" / "two")
        three = _skill(root / "more" / "three")
        got = foreign._resolve_listed(root, ["./skills/one/", "./more"])
        assert got == [root / "./skills/one/", three, two]
        assert got[0].resolve() == one.resolve()

    def test_a_path_that_leaves_the_plugin_is_ignored(self, sandbox):
        root = paths.home() / "plug"
        root.mkdir()
        _skill(paths.home() / "outside" / "evil")
        (root / "link").symlink_to(paths.home() / "outside")
        assert foreign._resolve_listed(root, ["../outside", "./link",
                                              "../outside/evil"]) == []

    def test_a_path_that_leaves_does_not_end_the_list(self, sandbox):
        root = paths.home() / "plug"
        one = _skill(root / "skills" / "one")
        _skill(paths.home() / "outside" / "evil")
        assert foreign._resolve_listed(root, ["../outside/evil", "./skills/one"]) == [
            root / "./skills/one"]
        assert one.is_dir()

    def test_a_path_on_another_drive_is_ignored(self, sandbox, monkeypatch):
        def boom(_paths):
            raise ValueError("different drives")
        monkeypatch.setattr(foreign.os.path, "commonpath", boom)
        root = paths.home() / "plug"
        _skill(root / "skills" / "one")
        assert foreign._resolve_listed(root, ["./skills/one"]) == []


class TestSourceIsRoot:
    @pytest.mark.parametrize("source", [".", "./", "./.", "././"])
    def test_the_marketplace_root(self, source):
        assert foreign._source_is_root({"source": source}) is True

    @pytest.mark.parametrize("source", ["./plugins/x", "plugins", "", "/abs", "..",
                                        None, {"source": "github"}])
    def test_anything_else(self, source):
        assert foreign._source_is_root({"source": source}) is False

    def test_no_source(self):
        assert foreign._source_is_root({}) is False


class TestSkillName:
    def test_the_frontmatter_name(self, sandbox):
        d = _skill(paths.home() / "secret-management",
                   "---\nname: managing-secrets\n---\n# s\n")
        assert foreign.skill_name(d, "fallback") == "managing-secrets"

    def test_surrounding_space_is_not_part_of_it(self, sandbox):
        d = _skill(paths.home() / "s", "---\nname: '  spaced  '\n---\n")
        assert foreign.skill_name(d, "fallback") == "spaced"

    @pytest.mark.parametrize("body", [
        "# no frontmatter\n",
        "---\nname: never-closed\n# s\n",
        "---\ndescription: d\n---\n",
        "---\nname: ''\n---\n",
        "---\nname: '   '\n---\n",
        "---\nname: [a, b]\n---\n",
    ])
    def test_otherwise_the_fallback(self, sandbox, body):
        assert foreign.skill_name(_skill(paths.home() / "s", body), "fb") == "fb"

    def test_a_file_that_is_not_utf8_still_declares_its_name(self, sandbox):
        d = paths.home() / "s"
        d.mkdir()
        (d / "SKILL.md").write_bytes(b"---\nname: managing-secrets\n---\n# caf\xe9\n")
        assert foreign.skill_name(d, "fb") == "managing-secrets"

    def test_an_unreadable_file_declares_nothing(self, sandbox):
        assert foreign.skill_name(paths.home() / "missing", "fb") == "fb"


def _skills() -> dict:
    return foreign.plugin_skills(foreign.enabled_plugins()[0])


class TestPluginSkills:
    def test_an_entry_list_loads_only_what_it_lists(self, sandbox):
        # The marketplace in use: every plugin's source is the repo root, so
        # the cached copy holds every skill and loads only the listed ones.
        inst = _plugin(skills=("eight-adr", "eight-twins", "eight-core-only"),
                       entry={"skills": ["./skills/eight-adr", "./skills/eight-twins"]})
        assert _skills() == {
            "eight-adr": inst / "./skills/eight-adr",
            "eight-twins": inst / "./skills/eight-twins"}

    def test_an_entry_with_no_skills_key_keeps_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a", "b"))
        assert _skills() == {"a": inst / "skills" / "a", "b": inst / "skills" / "b"}

    def test_an_empty_entry_list_loads_nothing(self, sandbox):
        _plugin(skills=("a",), entry={"skills": []})
        assert _skills() == {}

    def test_no_marketplace_entry_keeps_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a",))
        _write(_plugins_root() / "marketplaces" / "eight" / ".claude-plugin"
               / "marketplace.json", {"plugins": []})
        assert _skills() == {"a": inst / "skills" / "a"}

    def test_an_entry_below_the_root_adds_to_the_default_scan(self, sandbox):
        # With no plugin.json the entry is the manifest, and a manifest's
        # skills key adds to the default scan rather than replacing it.
        inst = _plugin(skills=("a",), entry={"source": "./plugins/eight-backend",
                                             "skills": ["./more"]})
        _skill(inst / "more" / "m")
        assert _skills() == {"a": inst / "skills" / "a", "m": inst / "more" / "m"}

    def test_a_plugin_json_adds_to_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a",), manifest={"skills": ["./extra"]})
        _skill(inst / "extra" / "x")
        assert _skills() == {"a": inst / "skills" / "a", "x": inst / "extra" / "x"}

    def test_the_entrys_skills_are_appended_to_a_plugin_json(self, sandbox):
        inst = _plugin(skills=("a",), manifest={"skills": ["./extra"]},
                       entry={"source": "./plugins/eight-backend",
                              "skills": ["./more"]})
        _skill(inst / "extra" / "x")
        _skill(inst / "more" / "m")
        assert _skills() == {"a": inst / "skills" / "a", "x": inst / "extra" / "x",
                             "m": inst / "more" / "m"}

    @pytest.mark.parametrize("own", [["./extra"], "./extra", ["./skills"],
                                     ["./skills/a"]])
    def test_a_root_source_list_replaces_a_plugin_jsons_skills_too(self, sandbox, own):
        # Claude Code 2.1.300 lists only the entry's skills. Counting the
        # manifest's too called `a` the plugin's, so a store copy of it got no
        # Claude Code link while Claude Code loaded no `a` from the plugin.
        inst = _plugin(skills=("a", "b"), manifest={"skills": own},
                       entry={"skills": ["./skills/b"]})
        _skill(inst / "extra" / "x")
        assert _skills() == {"b": inst / "skills" / "b"}

    def test_a_plugin_json_without_skills_is_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a",), manifest={"name": "eight-backend"})
        assert _skills() == {"a": inst / "skills" / "a"}

    @pytest.mark.parametrize("key", foreign.COMPONENTS)
    def test_strict_false_and_a_component_beside_a_plugin_json_loads_nothing(
            self, sandbox, key):
        # "Plugin <name> has conflicting manifests": it does not load at all.
        _plugin(skills=("a",), manifest={"name": "eight-backend"},
                entry={"strict": False, key: "./x"})
        assert _skills() == {}

    def test_strict_false_with_no_component_is_no_conflict(self, sandbox):
        inst = _plugin(skills=("a",), manifest={"name": "eight-backend"},
                       entry={"strict": False, "description": "d"})
        assert _skills() == {"a": inst / "skills" / "a"}

    @pytest.mark.parametrize("strict", [True, "false", None])
    def test_only_a_literal_false_is_strict_false(self, sandbox, strict):
        inst = _plugin(skills=("a",), manifest={"name": "eight-backend"},
                       entry={"strict": strict, "source": "./plugins/eight-backend",
                              "skills": ["./more"]})
        _skill(inst / "more" / "m")
        assert sorted(_skills()) == ["a", "m"]

    def test_strict_false_without_a_plugin_json_is_the_manifest(self, sandbox):
        inst = _plugin(skills=("a", "b"), entry={"strict": False,
                                                 "skills": ["./skills/a"]})
        assert _skills() == {"a": inst / "./skills/a"}

    def test_a_plugin_json_that_does_not_parse_loads_nothing(self, sandbox):
        inst = _plugin(skills=("a",))
        (inst / ".claude-plugin").mkdir()
        (inst / ".claude-plugin" / "plugin.json").write_text("{nope", encoding="utf-8")
        assert _skills() == {}

    def test_an_unreadable_plugin_json_loads_nothing(self, sandbox, monkeypatch):
        inst = _plugin(skills=("a",), manifest={"name": "eight-backend"})
        real = foreign.jsonstate.read_object

        def boom(path):
            if path.name == "plugin.json":
                raise PermissionError("no")
            return real(path)
        monkeypatch.setattr(foreign.jsonstate, "read_object", boom)
        assert foreign.plugin_skills(foreign.Plugin("eight-backend@eight", inst)) == {}

    def test_a_root_skill_md_is_one_skill_named_for_the_plugin(self, sandbox):
        inst = _plugin(skills=())
        _skill(inst, "# root\n")
        assert _skills() == {"eight-backend": inst}

    def test_a_root_skill_is_named_by_its_frontmatter_first(self, sandbox):
        inst = _plugin(skills=())
        _skill(inst, "---\nname: adr\n---\n")
        assert _skills() == {"adr": inst}

    @pytest.mark.parametrize("layout", ["skills-dir", "manifest-key", "entry-key"])
    def test_a_root_skill_md_is_not_one_skill_beside_any_other_layout(self, sandbox,
                                                                     layout):
        inst = _plugin(skills=(), manifest={"skills": []} if layout == "manifest-key"
                       else None,
                       entry={"source": "./plugins/eight-backend", "skills": []}
                       if layout == "entry-key" else None)
        _skill(inst, "# root\n")
        if layout == "skills-dir":
            (inst / "skills").mkdir()
        assert _skills() == {}

    def test_a_listed_plugin_root_is_named_for_the_plugin(self, sandbox):
        inst = _plugin(skills=("a",), entry={"skills": ["./"]})
        _skill(inst, "# root\n")
        assert _skills() == {"eight-backend": inst / "./"}

    def test_skills_are_keyed_by_their_frontmatter_name(self, sandbox):
        # Claude Code lists /p:managing-secrets, not /p:secret-management.
        inst = _plugin(skills=())
        d = _skill(inst / "skills" / "secret-management",
                   "---\nname: managing-secrets\n---\n")
        assert _skills() == {"managing-secrets": d}

    def test_a_name_already_under_the_plugin_loses_the_prefix(self, sandbox):
        inst = _plugin(skills=())
        d = _skill(inst / "skills" / "x", "---\nname: eight-backend:adr\n---\n")
        e = _skill(inst / "skills" / "y", "---\nname: other:twins\n---\n")
        assert _skills() == {"adr": d, "other:twins": e}

    def test_the_prefix_is_the_manifests_name_when_it_has_one(self, sandbox):
        # Components are namespaced under the manifest's name, which may not
        # be the one the marketplace entry lists the plugin under.
        inst = _plugin(skills=(), manifest={"name": "deploy-tools"})
        d = _skill(inst / "skills" / "x", "---\nname: deploy-tools:ship\n---\n")
        e = _skill(inst / "skills" / "y", "---\nname: eight-backend:adr\n---\n")
        assert _skills() == {"ship": d, "eight-backend:adr": e}

    def test_the_first_dir_to_claim_a_name_keeps_it(self, sandbox):
        inst = _plugin(skills=("x",))
        a = _skill(inst / "skills" / "a", "---\nname: x\n---\n")
        assert _skills() == {"x": a}
        assert (inst / "skills" / "x").is_dir()


class TestPluginIndex:
    def test_every_plugin_that_ships_a_name_is_listed_by_id(self, sandbox):
        b = _plugin("b-plugin@m", skills=("shared",))
        a = _plugin("a-plugin@m", skills=("shared", "only-a"))
        index = foreign.plugin_index()
        assert sorted(index) == ["only-a", "shared"]
        assert [(p.id, where) for p, where in index["shared"]] == [
            ("a-plugin@m", a / "skills" / "shared"),
            ("b-plugin@m", b / "skills" / "shared")]
        assert [p.id for p, _w in index["only-a"]] == ["a-plugin@m"]

    def test_the_inventory_names_each_of_them(self, sandbox):
        _plugin("a-plugin@m", skills=("shared",))
        _plugin("b-plugin@m", skills=("shared",))
        assert [c.owner for c in foreign.inventory()["shared"]] == [
            "Claude Code plugin a-plugin@m", "Claude Code plugin b-plugin@m"]


class TestInventory:
    def test_empty_machine(self, sandbox):
        assert foreign.inventory() == {}

    def test_owners_in_trust_order(self, sandbox):
        vendor = _skill(paths.home() / ".cursor" / "skills-cursor" / "x")
        inst = _plugin(skills=("x",))
        agent = _skill(paths.home() / ".codex" / "skills" / "x")
        got = foreign.inventory()["x"]
        assert [(c.kind, c.owner, c.path) for c in got] == [
            (foreign.VENDOR, "Cursor's built-ins", vendor),
            (foreign.PLUGIN, "Claude Code plugin eight-backend@eight",
             inst / "skills" / "x"),
            (foreign.AGENT, "Codex", agent)]
        assert {c.name for c in got} == {"x"}

    def test_boosts_own_links_and_store_aliases_are_not_copies(self, sandbox):
        store_copy = _skill(paths.store_dir() / "x")
        (paths.home() / ".claude" / "skills").mkdir(parents=True)
        (paths.home() / ".claude" / "skills" / "x").symlink_to(store_copy)
        (paths.home() / ".cursor" / "skills-cursor").mkdir(parents=True)
        (paths.home() / ".cursor" / "skills-cursor" / "x").symlink_to(store_copy)
        assert foreign.inventory() == {}

    def test_a_second_path_to_a_listed_dir_is_not_a_second_copy(self, sandbox):
        real = _skill(paths.home() / ".codex" / "skills" / "x")
        (paths.home() / ".cursor" / "skills").mkdir(parents=True)
        (paths.home() / ".cursor" / "skills" / "x").symlink_to(real)
        got = foreign.inventory()["x"]
        assert len(got) == 1

    def test_a_disabled_agent_still_holds_its_skills(self, sandbox):
        cfg = config.load()
        cfg["agents"]["windsurf"]["enabled"] = False
        config.save(cfg)
        theirs = _skill(paths.home() / ".windsurf" / "skills" / "w")
        got = foreign.inventory()["w"]
        assert [(c.owner, c.path) for c in got] == [("Windsurf", theirs)]

    def test_an_agent_whose_dir_is_the_store_is_skipped(self, sandbox):
        cfg = config.load()
        cfg["agents"]["windsurf"]["dir"] = str(paths.store_dir())
        config.save(cfg)
        _skill(paths.store_dir() / "s")
        assert foreign.inventory() == {}

    def test_agents_after_one_whose_dir_is_the_store_are_still_walked(self, sandbox):
        cfg = config.load()
        cfg["agents"]["windsurf"]["dir"] = str(paths.store_dir())
        config.save(cfg)
        theirs = _skill(paths.home() / ".codex" / "skills" / "t")
        got = foreign.inventory()
        assert [(c.owner, c.path) for c in got["t"]] == [("Codex", theirs)]

    def test_narrowed_to_the_names_asked_about(self, sandbox):
        x = _skill(paths.home() / ".codex" / "skills" / "x")
        _skill(paths.home() / ".codex" / "skills" / "y")
        _skill(paths.home() / ".cursor" / "skills-cursor" / "z")
        assert {n: [c.path for c in cs] for n, cs in foreign.inventory(["x", "q"]).items()} == {
            "x": [x]}
        assert foreign.inventory([]) == {}

    def test_a_dir_linking_into_the_store_file_by_file_is_not_a_copy(self, sandbox):
        # A Stow-style farm: a real dir whose files are links into the store
        # copy. It hashes as identical, and deleting "the copy" would leave
        # it a dir of dangling links.
        mine = _skill(paths.store_dir() / "shared-notes")
        (mine / "refs").mkdir()
        (mine / "refs" / "a.md").write_text("a", encoding="utf-8")
        farm = paths.home() / ".cursor" / "skills" / "shared-notes"
        (farm / "refs").mkdir(parents=True)
        (farm / "SKILL.md").symlink_to(mine / "SKILL.md")
        (farm / "refs" / "a.md").symlink_to(mine / "refs" / "a.md")
        assert foreign.inventory() == {}

    def test_a_subdir_linked_into_the_store_counts_too(self, sandbox):
        mine = _skill(paths.store_dir() / "y")
        (mine / "refs").mkdir()
        theirs = _skill(paths.home() / ".codex" / "skills" / "y")
        (theirs / "refs").symlink_to(mine / "refs")
        assert foreign.inventory() == {}

    def test_a_link_that_leads_elsewhere_does_not(self, sandbox):
        elsewhere = paths.home() / "notes.md"
        elsewhere.write_text("n", encoding="utf-8")
        theirs = _skill(paths.home() / ".codex" / "skills" / "y")
        (theirs / "notes.md").symlink_to(elsewhere)
        assert [c.path for c in foreign.inventory()["y"]] == [theirs]


class TestSameContent:
    def test_identical_and_different(self, sandbox):
        a = _skill(paths.home() / "a", "same\n")
        b = _skill(paths.home() / "b", "same\n")
        c = _skill(paths.home() / "c", "other\n")
        assert foreign.same_content(a, b) is True
        assert foreign.compare(a, b) == foreign.IDENTICAL == "identical"
        assert foreign.same_content(a, c) is False
        assert foreign.compare(a, c) == foreign.DIFFERS == "differs"

    def test_unreadable_is_not_identical(self, sandbox, monkeypatch):
        a = _skill(paths.home() / "a")

        def boom(_p):
            raise PermissionError("no")
        monkeypatch.setattr(foreign.util, "sha256_dir", boom)
        assert foreign.same_content(a, a) is False
        assert foreign.compare(a, a) == foreign.DIFFERS


    def test_a_dir_it_cannot_list_is_not_identical(self, sandbox, locked):
        # The hash skips a subdir it cannot list, so a copy whose extra files
        # sit in one hashed the same as the copy it was compared with.
        a = _skill(paths.home() / "a", "same\n")
        b = _skill(paths.home() / "b", "same\n")
        (a / "extra").mkdir()
        (a / "extra" / "x.md").write_text("x", encoding="utf-8")
        locked(a / "extra")
        assert foreign.same_content(a, b) is False
        assert foreign.same_content(b, a) is False


@pytest.fixture
def locked():
    """chmod a path to 0 for the test, and give its mode back after it.

    Skips the test where a mode cannot lock its owner out: on Windows, or as
    root.
    """
    if sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("needs POSIX permission bits, as a user other than root")
    done: list[tuple[Path, int]] = []

    def lock(p: Path) -> Path:
        done.append((p, p.stat().st_mode))
        p.chmod(0)
        return p
    yield lock
    for p, mode in reversed(done):
        p.chmod(mode)


class TestSameDir:
    def test_one_dir_by_any_path_to_it(self, sandbox):
        a = _skill(paths.home() / "a")
        alias = paths.home() / "alias"
        alias.symlink_to(a)
        assert foreign.same_dir(a, alias) is True
        assert foreign._identity(a) == foreign._identity(alias)
        assert foreign._identity(a)[0] == "inode"

    def test_two_dirs_with_the_same_bytes_are_two(self, sandbox):
        a = _skill(paths.home() / "a")
        b = _skill(paths.home() / "b")
        assert foreign.same_dir(a, b) is False
        assert foreign._identity(a) != foreign._identity(b)

    def test_a_path_that_cannot_be_looked_at_is_the_same_as_nothing(self, sandbox):
        a = _skill(paths.home() / "a")
        gone = paths.home() / "gone"
        assert foreign.same_dir(a, gone) is False
        assert foreign.same_dir(gone, gone) is False
        assert foreign._identity(gone) == ("path", os.path.realpath(gone))

    def test_inventory_lists_one_dir_once_however_it_is_spelled(
            self, sandbox, monkeypatch):
        # Two spellings of one dir on a case-insensitive volume: realpath keeps
        # each as given, so only the inode can tell they are one.
        _skill(paths.home() / ".codex" / "skills" / "x")
        _skill(paths.home() / ".cursor" / "skills" / "x")
        assert len(foreign.inventory()["x"]) == 2
        monkeypatch.setattr(foreign, "_identity", lambda _p: ("inode", 1, 2))
        assert len(foreign.inventory()["x"]) == 1


class TestHoldsRepo:
    @pytest.mark.parametrize("where", [".git", "vendor/lib/.git"])
    def test_a_git_dir_at_any_depth(self, sandbox, where):
        d = _skill(paths.home() / "s")
        (d / where).mkdir(parents=True)
        assert foreign.holds_repo(d) is True

    def test_a_git_file_too(self, sandbox):
        # What a worktree or a submodule holds in place of the dir.
        d = _skill(paths.home() / "s")
        (d / ".git").write_text("gitdir: ../x\n", encoding="utf-8")
        assert foreign.holds_repo(d) is True

    def test_names_that_only_look_like_it(self, sandbox):
        d = _skill(paths.home() / "s")
        (d / "git").mkdir()
        (d / ".gitignore").write_text("x\n", encoding="utf-8")
        assert foreign.holds_repo(d) is False


class TestUnreadable:
    @pytest.fixture
    def tree(self, sandbox) -> Path:
        d = _skill(paths.home() / "s")
        (d / "refs").mkdir()
        (d / "refs" / "a.md").write_text("a", encoding="utf-8")
        return d

    def test_a_readable_tree(self, tree):
        assert foreign.unreadable(tree) is None

    @pytest.mark.parametrize("rel", ["SKILL.md", "refs", "refs/a.md", "."])
    def test_names_what_cannot_be_read(self, tree, locked, rel):
        bad = tree / rel if rel != "." else tree
        locked(bad)
        assert foreign.unreadable(tree) == bad

    def test_the_first_by_name(self, tree, locked):
        for n in ("b.md", "a.md"):
            locked(_file(tree / n))
        assert foreign.unreadable(tree) == tree / "a.md"

    @pytest.mark.parametrize("ignored", [".git", "__pycache__"])
    def test_what_the_hash_ignores_is_not_looked_at(self, tree, locked, ignored):
        (tree / ignored).mkdir()
        locked(tree / ignored)
        assert foreign.unreadable(tree) is None

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no FIFOs here")
    def test_a_fifo_does_not_hang_the_walk(self, tree):
        os.mkfifo(tree / "pipe")
        assert foreign.unreadable(tree) is None

    def test_a_link_into_a_dir_is_not_followed(self, tree, locked):
        elsewhere = locked(_skill(paths.home() / "elsewhere"))
        (tree / "elsewhere").symlink_to(elsewhere)
        assert foreign.unreadable(tree) is None

    def test_a_link_to_a_file_is_followed_as_the_hash_follows_it(self, tree, locked):
        secret = locked(_file(paths.home() / "secret.md"))
        (tree / "secret.md").symlink_to(secret)
        assert foreign.unreadable(tree) == tree / "secret.md"


def _file(p: Path) -> Path:
    p.write_text("x", encoding="utf-8")
    return p


class TestNewestMtime:
    def test_the_newest_file_not_the_directory(self, sandbox):
        d = _skill(paths.home() / "s")
        (d / "sub").mkdir()
        (d / "sub" / "x.md").write_text("x", encoding="utf-8")
        os.utime(d / "SKILL.md", (100, 100))
        os.utime(d / "sub" / "x.md", (200, 200))
        os.utime(d / "sub", (900, 900))
        os.utime(d, (900, 900))
        assert foreign.newest_mtime(d) == 200

    def test_noise_does_not_count(self, sandbox):
        d = _skill(paths.home() / "s")
        os.utime(d / "SKILL.md", (100, 100))
        (d / ".DS_Store").write_text("x", encoding="utf-8")
        os.utime(d / ".DS_Store", (900, 900))
        (d / ".git").mkdir()
        (d / ".git" / "HEAD").write_text("x", encoding="utf-8")
        os.utime(d / ".git" / "HEAD", (900, 900))
        assert foreign.newest_mtime(d) == 100

    def test_an_empty_or_missing_dir_is_zero(self, sandbox):
        (paths.home() / "empty").mkdir()
        assert foreign.newest_mtime(paths.home() / "empty") == 0.0
        assert foreign.newest_mtime(paths.home() / "gone") == 0.0

    def test_noise_first_in_the_walk_does_not_end_it(self, sandbox, monkeypatch):
        # The order is pinned: readdir order is the filesystem's to choose,
        # and noise sorting last would let a `break` here pass unseen.
        d = _skill(paths.home() / "s")
        (d / ".DS_Store").write_text("x", encoding="utf-8")
        os.utime(d / "SKILL.md", (100, 100))
        os.utime(d / ".DS_Store", (900, 900))
        monkeypatch.setattr(foreign.os, "walk",
                            lambda _p: iter([(str(d), [], [".DS_Store", "SKILL.md"])]))
        assert foreign.newest_mtime(d) == 100

    def test_a_vanished_file_does_not_end_its_directory(self, sandbox, monkeypatch):
        d = _skill(paths.home() / "s")
        (d / "a.md").write_text("a", encoding="utf-8")
        (d / "b.md").write_text("b", encoding="utf-8")
        order = next(os.walk(d))[2]          # the order newest_mtime will see
        for f, t in zip(order, (900, 100, 200), strict=True):
            os.utime(d / f, (t, t))
        real = os.lstat

        def flaky(p, *a, **kw):
            if os.path.basename(p) == order[0]:
                raise FileNotFoundError(p)
            return real(p, *a, **kw)
        monkeypatch.setattr(foreign.os, "lstat", flaky)
        assert foreign.newest_mtime(d) == 200
