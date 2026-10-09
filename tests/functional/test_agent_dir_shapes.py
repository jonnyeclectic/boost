# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Agent-dir shapes install, doctor, heal and sync used to mishandle.

Each class is one shape from the card agent-dir-shapes-install-still-trips-on:
a dotdir with no search bit, a missing skills dir under a read-only dotdir, an
agent dropped from a skill's scope after a refusal, the commands that relink
and said nothing about a refusal, a directory where a rule's file goes, a heal
preview promising a repair its run then skipped, and a read-only store doctor
called healthy.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from boost_cli.core import catalog, lockfile, paths, registry, store

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32",
                       reason="chmod cannot remove these bits on Windows"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="root ignores mode bits"),
]


@pytest.fixture()
def strict_stat(monkeypatch):
    """Python 3.12 and 3.13's pathlib, on any interpreter.

    There ``Path.is_symlink``, ``is_dir``, ``exists`` and ``is_file`` raise
    PermissionError for a path under a dir with no search bit; 3.14 answers
    False. The crashes this file pins only happen on the first two, so without
    this they would pass on old code under the 3.14 the suite runs on.
    """
    def strict(orig):
        def check(self, *args, **kwargs):
            try:
                os.lstat(self)
            except PermissionError:
                raise
            except OSError:
                pass
            return orig(self, *args, **kwargs)
        return check

    for name in ("is_symlink", "is_dir", "exists", "is_file"):
        monkeypatch.setattr(Path, name, strict(getattr(Path, name)))


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


@pytest.fixture()
def entry(tap):
    return catalog.resolve_one("brainstorming")


@pytest.fixture()
def cursor(sandbox):
    """``~/.cursor``, restored to 0o700 whatever a test leaves it at."""
    d = paths.home() / ".cursor"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    d.chmod(0o700)
    for sub in d.iterdir():
        if sub.is_dir() and not sub.is_symlink():
            sub.chmod(0o700)


def _rule(tap, name="house", rel="rules/house.mdc"):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: house\n---\n\nUse tabs.\n", encoding="utf-8")
    catalog.rebuild_tap(tap)
    return {"name": name, "kind": "rule", "tap": tap.name, "version": "1.0.0",
            "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
            "description": "house rules", "curated": False, "meta": {}}


def _workflow(tap, name="ship-it", rel="commands/ship.md"):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: ship-it\ndescription: release\n---\n\nShip.\n",
                   encoding="utf-8")
    catalog.rebuild_tap(tap)
    return {"name": name, "kind": "workflow", "tap": tap.name,
            "version": "1.0.0",
            "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
            "description": "release", "curated": False, "meta": {}}


class TestRefusalWording:
    """``chmod u+w`` on a dir at 0o600 changes nothing: search is missing."""

    @pytest.fixture(autouse=True)
    def _home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))

    def test_an_unsearchable_dir_gets_the_search_bit_too(self, tmp_path):
        d = tmp_path / "dot"
        d.mkdir()
        d.chmod(0o600)
        try:
            assert paths.not_searchable(d)
            assert paths.chmod_command(d) == "chmod u+wx ~/dot"
            assert paths.write_remedy(d) == "run `chmod u+wx ~/dot`"
            assert paths.not_writable(d, d) == "~/dot is not searchable"
            # The dir below may exist; "cannot be created" was a guess.
            assert (paths.not_writable(d / "skills", d)
                    == "~/dot/skills cannot be reached: ~/dot is not searchable")
        finally:
            d.chmod(0o700)

    def test_a_searchable_read_only_dir_keeps_u_w(self, tmp_path):
        d = tmp_path / "dot"
        d.mkdir()
        d.chmod(0o500)
        try:
            assert not paths.not_searchable(d)
            assert paths.chmod_command(d) == "chmod u+w ~/dot"
            assert (paths.not_writable(d / "skills", d)
                    == "~/dot/skills cannot be created: ~/dot is not writable")
        finally:
            d.chmod(0o700)

    def test_a_path_that_is_not_there_is_not_unsearchable(self, tmp_path):
        assert not paths.not_searchable(tmp_path / "gone")
        assert paths.chmod_command(tmp_path / "gone") == "chmod u+w ~/gone"

    def test_unwritable_refusal_words_both_halves(self, tmp_path):
        d = tmp_path / "dot"
        d.mkdir()
        d.chmod(0o600)
        try:
            assert store.unwritable_refusal(str(d)) == (
                "~/dot is not searchable", "`chmod u+wx ~/dot`")
        finally:
            d.chmod(0o700)


class TestADotdirWithNoSearchBit:
    """``~/.cursor`` at 0o600, on Python 3.12/3.13 semantics: the install
    copied the skill into the store and then exited 70 in ``linked_agents``,
    with no lock entry; doctor, heal and sync exited 70 too."""

    def test_the_install_records_the_skill_and_names_the_dotdir(
            self, entry, cursor, strict_stat):
        (cursor / "skills").mkdir()
        cursor.chmod(0o600)
        res = store.install(entry)
        cursor.chmod(0o700)
        assert res.unwritable == [str(cursor)]
        assert res.refused == ["cursor"]
        locked = lockfile.get_skill("brainstorming")
        assert "cursor" not in locked["agents"]
        assert "claude-code" in locked["agents"]
        assert locked["refused_agents"] == ["cursor"]

    def test_the_checks_name_it_instead_of_crashing(self, entry, cursor,
                                                    strict_stat):
        store.install(entry)
        cursor.chmod(0o600)
        assert store.linked_agents("brainstorming") == [
            "claude-code", "windsurf", "antigravity"]
        plan = store.sync_plan()
        assert store.unwritable_agent_dirs() == [cursor]
        cursor.chmod(0o700)
        assert ("brainstorming", "cursor") in plan["missing_links"]

    def test_doctor_heal_and_sync_agree_on_it(self, boost, tapped, cursor,
                                              strict_stat):
        boost("install", "brainstorming")
        cursor.chmod(0o600)
        doc = boost("doctor", expect=1).out
        dry = boost("heal", "--dry-run", expect=1).out
        healed = boost("heal", expect=1).out
        synced = boost("sync").out
        cursor.chmod(0o700)
        assert "agent dir ~/.cursor is not searchable" in doc
        assert "`chmod u+wx ~/.cursor`" in doc
        for text in (dry, healed):
            assert ("~/.cursor/skills cannot be reached: ~/.cursor is not "
                    "searchable") in " ".join(text.split())
            assert "chmod u+wx ~/.cursor" in text
        # The run cannot link it, so the preview does not promise to.
        assert "would link" not in dry
        assert "everything in sync" not in synced
        assert "chmod u+wx ~/.cursor" in synced

    def test_health_and_the_rule_checks_do_not_crash(self, boost, tapped,
                                                     cursor, strict_stat):
        boost("install", "brainstorming")
        tap = registry.list_taps()[0]
        store.install(_rule(tap))
        store.install(_workflow(tap))
        cursor.chmod(0o600)
        health = boost("health", expect=None)
        doc = boost("doctor", expect=1)
        synced = boost("sync")
        cursor.chmod(0o700)
        assert health.rc in (0, 1), health.err
        assert "unexpected error" not in health.err + doc.err + synced.err
        # A link boost cannot see in a dir it cannot write is the agent-dir
        # line's to name, not "run `boost sync`", which cannot make it.
        assert "skill brainstorming not linked for cursor" not in doc.out

    def test_a_missing_link_in_a_writable_dir_still_sends_you_to_sync(
            self, boost, installed):
        (paths.home() / ".cursor" / "skills" / "brainstorming").unlink()
        doc = boost("doctor", expect=1).out
        assert ("skill brainstorming not linked for cursor — run `boost sync`"
                in doc)

    def test_unlink_skips_a_link_it_may_not_look_at(self, entry, cursor,
                                                   strict_stat):
        store.install(entry)
        cursor.chmod(0o600)
        removed = store.unlink_agents("brainstorming")
        cursor.chmod(0o700)
        assert "cursor" not in removed
        assert "claude-code" in removed


class TestAMissingSkillsDirUnderAReadOnlyDotdir:
    """The install told the user to ``chmod`` a ``~/.cursor/skills`` that did
    not exist, doctor said healthy, and sync said everything in sync."""

    def test_the_install_names_the_dotdir(self, entry, cursor):
        cursor.chmod(0o500)
        res = store.install(entry)
        found = store.unwritable_agent_dirs()
        cursor.chmod(0o700)
        assert res.unwritable == [str(cursor)]
        assert found == [cursor]

    def test_a_missing_dir_under_a_writable_dotdir_is_not_reported(
            self, entry, cursor):
        store.install(entry)
        import shutil
        shutil.rmtree(cursor / "skills")
        assert store.unwritable_agent_dirs() == []

    def test_every_surface_names_the_same_dir(self, boost, tapped, cursor):
        cursor.chmod(0o500)
        inst = " ".join(boost("install", "brainstorming").out.split())
        doc = " ".join(boost("doctor", expect=1).out.split())
        dry = " ".join(boost("heal", "--dry-run", expect=1).out.split())
        synced = " ".join(boost("sync").out.split())
        cursor.chmod(0o700)
        assert ("not linked: ~/.cursor is not writable — `chmod u+w "
                "~/.cursor`") in inst
        assert "~/.cursor/skills" not in inst
        assert ("agent dir ~/.cursor is not writable — `chmod u+w ~/.cursor`"
                in doc)
        assert ("~/.cursor/skills cannot be created: ~/.cursor is not "
                "writable") in dry
        # One line for the dotdir, not one per way of finding it.
        assert dry.count("chmod u+w ~/.cursor`") == 1
        assert "would link" not in dry
        assert "agent dir ~/.cursor is not writable" in synced
        assert "everything in sync" not in synced


class TestARefusedAgentStaysInScope:
    """After an install skipped cursor, `install --force` replayed the lock's
    ``agents`` -- which a refused agent is never in -- so it never retried
    cursor once the dir was fixed, and never said so."""

    def test_a_forced_reinstall_retries_the_refused_agent(self, entry, cursor):
        cursor.chmod(0o500)
        store.install(entry)
        cursor.chmod(0o700)
        assert lockfile.get_skill("brainstorming")["refused_agents"] == [
            "cursor"]
        res = store.install(entry, force=True)
        assert "cursor" in res.linked
        locked = lockfile.get_skill("brainstorming")
        assert "cursor" in locked["agents"]
        assert "refused_agents" not in locked

    def test_an_import_records_its_refusals_too(self, sandbox, cursor,
                                                tmp_path):
        src = tmp_path / "mine"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: mine\ndescription: d\n---\n"
                                      "\nbody\n", encoding="utf-8")
        cursor.chmod(0o500)
        res = store.install_from_path(src)
        cursor.chmod(0o700)
        assert res.refused == ["cursor"]
        assert lockfile.get_skill("mine")["refused_agents"] == ["cursor"]
        store.install_from_path(src, force=True)
        assert "refused_agents" not in lockfile.get_skill("mine")
        assert "cursor" in lockfile.get_skill("mine")["agents"]

    def test_an_agent_with_something_in_the_way_is_refused_too(self, entry,
                                                               cursor):
        (cursor / "skills").symlink_to(cursor / "nowhere")
        res = store.install(entry)
        assert res.blocked == [(str(cursor / "skills"), str(cursor / "skills"))]
        assert res.refused == ["cursor"]
        assert lockfile.get_skill("brainstorming")["refused_agents"] == [
            "cursor"]

    def test_an_entry_that_never_met_a_refusal_records_none(self, entry):
        store.install(entry)
        assert "refused_agents" not in lockfile.get_skill("brainstorming")

    def test_the_scope_replays_links_and_refusals(self):
        assert store.preserved_agent_scope(
            None, {"agents": ["claude-code"], "refused_agents": ["cursor"]}
        ) == ["claude-code", "cursor"]
        # An empty `agents` still means every agent, refusals or not.
        assert store.preserved_agent_scope(
            None, {"agents": [], "refused_agents": ["cursor"]}) is None
        assert store.preserved_agent_scope(
            None, {"agents": ["cursor"], "refused_agents": ["cursor"]}
        ) == ["cursor"]

    def test_a_sidelined_skill_reinstalls_everywhere(self, entry, cursor):
        # sideline() empties `agents` and keeps the refusals; replaying those
        # alone made the next forced reinstall link cursor and nothing else.
        cursor.chmod(0o500)
        store.install(entry)
        cursor.chmod(0o700)
        store.sideline("brainstorming", "focus")
        res = store.install(entry, force=True)
        assert {"claude-code", "windsurf", "cursor"} <= set(res.linked)

    def test_a_declaration_still_outranks_the_refusals(self):
        assert store.preserved_agent_scope(
            None, {"agents": ["claude-code"], "refused_agents": ["cursor"],
                   "only_agents": ["claude-code"]}) == ["claude-code"]

    def test_record_links_sets_and_clears_the_refusals(self):
        res = store.InstallResult(name="x", dest=Path("/x"),
                                  linked=["claude-code"], refused=["cursor"])
        entry = store.record_links({"agents": []}, res)
        assert entry == {"agents": ["claude-code"],
                         "refused_agents": ["cursor"]}
        res.refused = []
        assert store.record_links(entry, res) == {"agents": ["claude-code"]}

    def test_the_dry_run_previews_the_retry(self, boost, tapped, cursor):
        cursor.chmod(0o500)
        boost("install", "brainstorming")
        cursor.chmod(0o700)
        out = boost("install", "brainstorming", "--force", "--dry-run").out
        assert "cursor" in out


class TestRelinkingSaysWhatItSkipped:
    """focus, context, profile and `quarantine --release` relink through
    ``link_agents`` and dropped its refusals without a word."""

    def _locked(self, cursor):
        (cursor / "skills").chmod(0o500)

    def test_focus_clear(self, boost, tapped, cursor):
        boost("install", "brainstorming")
        boost("install", "commit-messages")
        boost("focus", "brainstorming")
        self._locked(cursor)
        out = " ".join(boost("focus", "--clear").out.split())
        assert ("not linked: ~/.cursor/skills is not writable — `chmod u+w "
                "~/.cursor/skills`, then `boost sync` adds the link") in out
        assert lockfile.get_skill("commit-messages")["refused_agents"] == [
            "cursor"]

    def test_focus_json_keeps_stdout_json(self, boost, tapped, cursor):
        boost("install", "brainstorming")
        boost("install", "commit-messages")
        boost("focus", "brainstorming")
        self._locked(cursor)
        res = boost("focus", "--clear", "--json")
        assert json.loads(res.out)["restored"] == 1
        assert "not linked: ~/.cursor/skills" in res.err

    def test_quarantine_release(self, boost, tapped, cursor):
        boost("install", "brainstorming")
        boost("quarantine", "brainstorming")
        self._locked(cursor)
        out = " ".join(boost("quarantine", "--release", "brainstorming")
                       .out.split())
        assert "not linked: ~/.cursor/skills is not writable" in out
        assert lockfile.get_skill("brainstorming")["refused_agents"] == [
            "cursor"]


class TestADirectoryAtARulesFilePath:
    """``~/.cursor/rules/house.mdc/`` raised IsADirectoryError, which no
    refusal shape matched: exit 70 after the other agents were written, and
    no lock entry."""

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_the_install_skips_it_as_a_conflict(self, tap, cursor, kind):
        entry = _rule(tap) if kind == "rule" else _workflow(tap)
        sub, fname = (("rules", "house.mdc") if kind == "rule"
                      else ("commands", "ship-it.md"))
        squat = cursor / sub / fname
        squat.mkdir(parents=True)
        res = store.install(entry)
        assert res.conflicts == [str(squat)]
        assert "cursor" not in res.linked
        assert "claude-code" in res.linked
        assert squat.is_dir()
        getter = lockfile.get_rule if kind == "rule" else lockfile.get_workflow
        rows = {m["agent"]: m for m in getter(entry["name"])["materializations"]}
        assert rows["cursor"]["unwritable"] is True
        assert store.occupied_targets() == [squat]
        assert store.materialization_refused(kind, entry["name"])
        # sync retries and does not claim a repair the directory still blocks.
        actions = store.sync_apply(store.sync_plan())
        assert not any("re-materialized" in a for a in actions)
        assert squat.is_dir()

    def test_once_moved_it_is_written(self, tap, cursor):
        entry = _rule(tap)
        squat = cursor / "rules" / "house.mdc"
        squat.mkdir(parents=True)
        store.install(entry)
        squat.rmdir()
        assert store.occupied_targets() == []
        assert not store.materialization_refused("rule", "house")
        actions = store.sync_apply(store.sync_plan())
        assert any("re-materialized rule house" in a for a in actions)
        assert squat.is_file()

    def test_occupied_is_a_real_directory_only(self, tmp_path):
        (tmp_path / "d").mkdir()
        (tmp_path / "f").write_text("x", encoding="utf-8")
        (tmp_path / "l").symlink_to(tmp_path / "d")
        assert store.occupied(tmp_path / "d")
        assert not store.occupied(tmp_path / "f")
        assert not store.occupied(tmp_path / "l")
        assert not store.occupied(tmp_path / "gone")

    def test_every_surface_names_it(self, boost, tapped, cursor):
        (cursor / "rules" / "house.mdc").mkdir(parents=True)
        src = Path(tapped) / "rules" / "house.mdc"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("---\nname: house\n---\n\nUse tabs.\n", encoding="utf-8")
        import subprocess
        subprocess.run(["git", "add", "-A"], cwd=tapped, check=True)
        subprocess.run(["git", "commit", "-qm", "rule"], cwd=tapped, check=True)
        boost("update")
        line = ("~/.cursor/rules/house.mdc is a directory boost did not "
                "create — move it aside")
        inst = " ".join(boost("install", "house").out.split())
        assert "not written: %s, then `boost sync` writes it" % line in inst
        doc = " ".join(boost("doctor", expect=1).out.split())
        assert "rule house was not written for cursor: %s" % line in doc
        dry = " ".join(boost("heal", "--dry-run", expect=1).out.split())
        assert line in dry
        assert "would re-materialize" not in dry
        synced = " ".join(boost("sync").out.split())
        assert line in synced
        assert "everything in sync" not in synced


class TestAHealPreviewForARefusedRule:
    """``heal --dry-run`` said "would re-materialize" a rule whose dir still
    refused; the run then re-materialized nothing."""

    def test_the_preview_says_what_the_run_does(self, tap, cursor):
        entry = _rule(tap)
        store.install(entry)
        target = cursor / "rules" / "house.mdc"
        target.unlink()
        (cursor / "rules").chmod(0o500)
        plan = store.sync_plan()
        assert plan["missing_materializations"] == [("rule", "house")]
        preview = store.sync_preview(plan)
        actions = store.sync_apply(plan)
        (cursor / "rules").chmod(0o700)
        assert not any("would re-materialize" in p for p in preview)
        assert not any("re-materialized" in a for a in actions)

    def test_a_writable_dir_is_still_previewed(self, tap, cursor):
        entry = _rule(tap)
        store.install(entry)
        (cursor / "rules" / "house.mdc").unlink()
        assert not store.materialization_refused("rule", "house")
        preview = store.sync_preview(store.sync_plan())
        assert any("would re-materialize rule house" in p for p in preview)


class TestAReadOnlyStore:
    """Every install exits 1 naming ``~/.agents/skills``; doctor said
    healthy."""

    def test_doctor_and_heal_name_it(self, boost, installed):
        store_dir = paths.store_dir()
        store_dir.chmod(0o500)
        try:
            doc = " ".join(boost("doctor", expect=1).out.split())
            dry = " ".join(boost("heal", "--dry-run", expect=1).out.split())
        finally:
            store_dir.chmod(0o700)
        assert ("~/.agents/skills is not writable — every install is refused "
                "until it is fixed; run `chmod u+w ~/.agents/skills`") in doc
        assert ("~/.agents/skills is not writable — heal does not change "
                "permissions") in dry

    def test_a_writable_store_is_not_named(self, boost, installed):
        assert "~/.agents/skills is not writable" not in boost("doctor").out
