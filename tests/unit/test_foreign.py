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
from pathlib import Path

import pytest

from boost_cli.core import config, foreign, paths


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
    plugin's own ``.claude-plugin/plugin.json``; None writes none.
    """
    name, market = pid.split("@")
    inst = _plugins_root() / "cache" / market / name / "abc123"
    for s in skills:
        _skill(inst / "skills" / s, "# %s from %s\n" % (s, name))
    settings = paths.home() / ".claude" / "settings.json"
    cur = json.loads(settings.read_text()) if settings.exists() else {}
    cur.setdefault("enabledPlugins", {})[pid] = enabled
    _write(settings, cur)
    rec = _plugins_root() / "installed_plugins.json"
    cur = json.loads(rec.read_text()) if rec.exists() else {"version": 2, "plugins": {}}
    cur["plugins"][pid] = [{"scope": scope, "installPath": str(inst),
                            "version": "abc123"}]
    _write(rec, cur)
    mroot = _plugins_root() / "marketplaces" / market
    mfile = mroot / ".claude-plugin" / "marketplace.json"
    cur = json.loads(mfile.read_text()) if mfile.exists() else {"name": market,
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

    @pytest.mark.parametrize("enabled", [False, "true", 1, None])
    def test_only_a_literal_true_enables(self, sandbox, enabled):
        _plugin(enabled=enabled)
        assert foreign.enabled_plugins() == []

    def test_a_project_scope_install_is_not_counted(self, sandbox):
        _plugin(scope="project")
        assert foreign.enabled_plugins() == []

    def test_an_install_path_that_is_gone_is_not_counted(self, sandbox):
        inst = _plugin()
        os.rename(inst, inst.with_name("moved"))
        assert foreign.enabled_plugins() == []

    def test_first_usable_row_wins(self, sandbox):
        inst = _plugin()
        rec = _plugins_root() / "installed_plugins.json"
        data = json.loads(rec.read_text())
        good = data["plugins"]["eight-backend@eight"][0]
        other = _plugins_root() / "other"
        other.mkdir()
        data["plugins"]["eight-backend@eight"] = [
            "junk", {"scope": "project", "installPath": str(other)},
            {"scope": "user", "installPath": 7}, good,
            {"scope": "user", "installPath": str(other)}]
        _write(rec, data)
        assert foreign.enabled_plugins() == [foreign.Plugin("eight-backend@eight", inst)]

    @pytest.mark.parametrize("settings,records", [
        ({"enabledPlugins": ["x"]}, None),
        (None, {"plugins": ["x"]}),
        (None, {"plugins": {"eight-backend@eight": "x"}}),
    ])
    def test_misshapen_records_yield_nothing(self, sandbox, settings, records):
        _plugin()
        if settings is not None:
            _write(paths.home() / ".claude" / "settings.json", settings)
        if records is not None:
            _write(_plugins_root() / "installed_plugins.json", records)
        assert foreign.enabled_plugins() == []

    def test_a_corrupt_file_yields_nothing(self, sandbox):
        _plugin()
        (_plugins_root() / "installed_plugins.json").write_text("{nope", encoding="utf-8")
        assert foreign.enabled_plugins() == []


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

    @pytest.mark.parametrize("plugins", [[], [{"name": "other"}], ["junk"], "x"])
    def test_no_matching_entry(self, sandbox, plugins):
        _plugin()
        _write(_plugins_root() / "marketplaces" / "eight" / ".claude-plugin"
               / "marketplace.json", {"plugins": plugins})
        assert foreign._marketplace_entry(foreign.enabled_plugins()[0]) is None

    def test_an_id_without_a_marketplace_has_no_entry(self, sandbox):
        assert foreign._marketplace_entry(foreign.Plugin("p", Path("/x"))) is None


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
        got = foreign._resolve_listed(root, ["./skills/one/", "more"])
        assert got == [("one", root / "./skills/one/"), ("three", three),
                       ("two", two)]
        assert got[0][1].resolve() == one.resolve()

    def test_a_path_that_leaves_the_plugin_is_ignored(self, sandbox):
        root = paths.home() / "plug"
        root.mkdir()
        _skill(paths.home() / "outside" / "evil")
        (root / "link").symlink_to(paths.home() / "outside")
        assert foreign._resolve_listed(root, ["../outside", "link",
                                              "../outside/evil"]) == []

    def test_a_path_on_another_drive_is_ignored(self, sandbox, monkeypatch):
        def boom(_paths):
            raise ValueError("different drives")
        monkeypatch.setattr(foreign.os.path, "commonpath", boom)
        root = paths.home() / "plug"
        _skill(root / "skills" / "one")
        assert foreign._resolve_listed(root, ["skills/one"]) == []


class TestPluginSkills:
    def test_an_entry_list_loads_only_what_it_lists(self, sandbox):
        # The marketplace in use: every plugin's source is the repo root, so
        # the cached copy holds every skill and loads only the listed ones.
        inst = _plugin(skills=("eight-adr", "eight-twins", "eight-core-only"),
                       entry={"skills": ["./skills/eight-adr", "./skills/eight-twins"]})
        plugin = foreign.enabled_plugins()[0]
        assert foreign.plugin_skills(plugin) == {
            "eight-adr": inst / "./skills/eight-adr",
            "eight-twins": inst / "./skills/eight-twins"}

    def test_an_entry_with_no_skills_key_keeps_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a", "b"))
        plugin = foreign.enabled_plugins()[0]
        assert foreign.plugin_skills(plugin) == {"a": inst / "skills" / "a",
                                                 "b": inst / "skills" / "b"}

    def test_an_empty_entry_list_loads_nothing(self, sandbox):
        _plugin(skills=("a",), entry={"skills": []})
        assert foreign.plugin_skills(foreign.enabled_plugins()[0]) == {}

    def test_no_marketplace_entry_keeps_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a",))
        _write(_plugins_root() / "marketplaces" / "eight" / ".claude-plugin"
               / "marketplace.json", {"plugins": []})
        assert foreign.plugin_skills(foreign.enabled_plugins()[0]) == {
            "a": inst / "skills" / "a"}

    def test_a_plugin_json_adds_to_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a",), manifest={"skills": ["./extra"]},
                       entry={"skills": ["./skills/none"]})
        _skill(inst / "extra" / "x")
        # The entry's list is not the manifest once a plugin.json exists.
        assert foreign.plugin_skills(foreign.enabled_plugins()[0]) == {
            "a": inst / "skills" / "a", "x": inst / "extra" / "x"}

    def test_a_plugin_json_without_skills_is_the_default_scan(self, sandbox):
        inst = _plugin(skills=("a",), manifest={"name": "eight-backend"},
                       entry={"skills": []})
        assert foreign.plugin_skills(foreign.enabled_plugins()[0]) == {
            "a": inst / "skills" / "a"}


class TestPluginIndex:
    def test_first_plugin_by_id_wins_a_shared_name(self, sandbox):
        a = _plugin("a-plugin@m", skills=("shared", "only-a"))
        _plugin("b-plugin@m", skills=("shared",))
        index = foreign.plugin_index()
        assert sorted(index) == ["only-a", "shared"]
        plugin, where = index["shared"]
        assert (plugin.id, where) == ("a-plugin@m", a / "skills" / "shared")


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

    def test_a_file_that_vanishes_mid_walk_is_skipped(self, sandbox, monkeypatch):
        d = _skill(paths.home() / "s")
        (d / "a.md").write_text("a", encoding="utf-8")
        (d / "b.md").write_text("b", encoding="utf-8")
        for f, t in (("SKILL.md", 100), ("a.md", 300), ("b.md", 200)):
            os.utime(d / f, (t, t))
        real = os.lstat

        def flaky(p, *a, **kw):
            if str(p).endswith("a.md"):
                raise FileNotFoundError(p)
            return real(p, *a, **kw)
        monkeypatch.setattr(foreign.os, "lstat", flaky)
        assert foreign.newest_mtime(d) == 200
