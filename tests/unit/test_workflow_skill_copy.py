# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the bookkeeping behind a workflow's copy in the skill store.

The functional suite drives the commands; these pin the predicates the
commands are built from, row for row, so a mutant in any one of them fails
here rather than somewhere three commands away.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from boost_cli.core import config, lockfile, paths, store, util

ROW = {"agent": None, "slot": "skill", "path": "", "sha256": ""}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entry(*rows, **extra):
    return {"kind": "workflow", "slot": "agents", "tap": "t",
            "materializations": list(rows), **extra}


def _agent_row(agent="claude-code"):
    return {"agent": agent, "slot": "agents", "path": "/x/%s.md" % agent,
            "sha256": "s"}


def _copy_row(name="wf", text="T"):
    return {**ROW, "path": str(paths.store_dir() / name / "SKILL.md"),
            "sha256": _sha(text)}


class TestLockRows:
    def test_is_skill_copy(self):
        assert lockfile.is_skill_copy({"slot": "skill"})
        assert not lockfile.is_skill_copy({"slot": "agents"})
        assert not lockfile.is_skill_copy({})

    def test_agent_names_leaves_the_copy_out(self, sandbox):
        entry = _entry(_agent_row("cursor"), _agent_row("claude-code"),
                       _copy_row())
        assert lockfile.agent_names("workflow", entry) == ["claude-code",
                                                           "cursor"]

    def test_untouched_never_carries_the_copy(self, sandbox):
        entry = _entry(_agent_row("cursor"), _copy_row())
        assert store._untouched_materializations(entry, []) == [
            _agent_row("cursor")]
        assert store._untouched_materializations(entry, ["cursor"]) == []

    def test_copy_row_finds_it_or_none(self, sandbox):
        assert store._copy_row(None) is None
        assert store._copy_row(_entry(_agent_row())) is None
        assert store._copy_row(_entry(_agent_row(), _copy_row())) == _copy_row()


class TestWants:
    def test_flag_beats_record_beats_config(self, sandbox):
        assert store.wants_skill_copy(True, {"as_skill": False}) is True
        assert store.wants_skill_copy(False, {"as_skill": True}) is False
        assert store.wants_skill_copy(None, {"as_skill": False}) is False
        assert store.wants_skill_copy(None, {"as_skill": True}) is True
        assert store.wants_skill_copy(None, None) is True
        config.set_value("workflows_as_skills", "false")
        assert store.wants_skill_copy(None, {}) is False
        assert store.wants_skill_copy(None, {"as_skill": True}) is True
        # A record that is not a bool is no record.
        assert store.wants_skill_copy(None, {"as_skill": "yes"}) is False

    def test_default_is_on(self):
        assert config.DEFAULTS["workflows_as_skills"] is True


class TestBlocker:
    def test_free(self, sandbox):
        assert store.skill_copy_blocker("wf", None) is None

    def test_unsafe_name(self, sandbox):
        assert "not a name the skill store can hold" in (
            store.skill_copy_blocker("../x", None) or "")

    def test_a_recorded_skill(self, sandbox):
        lockfile.set_skill("wf", {"tap": "t"})
        assert store.skill_copy_blocker("wf", None) == (
            "a skill named wf is already installed — the workflow is not "
            "written to the skill store")

    def test_a_foreign_dir_and_our_own(self, sandbox):
        (paths.store_dir() / "wf").mkdir(parents=True)
        assert "is not this workflow's" in (
            store.skill_copy_blocker("wf", None) or "")
        assert "is not this workflow's" in (
            store.skill_copy_blocker("wf", _entry(_agent_row())) or "")
        assert store.skill_copy_blocker("wf", _entry(_copy_row())) is None
        # a row naming another dir does not make this one ours
        assert store.skill_copy_blocker(
            "wf", _entry(_copy_row("other"))) is not None


class TestRemove:
    def _write(self, text="T"):
        d = paths.store_dir() / "wf"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(text, encoding="utf-8")
        return d

    def test_removes_ours_and_its_dir(self, sandbox):
        d = self._write()
        assert store._remove_skill_copy(_copy_row()) == (True, None)
        assert not d.exists()

    def test_keeps_an_edited_copy(self, sandbox):
        d = self._write("edited")
        assert store._remove_skill_copy(_copy_row()) == (
            False, str(d / "SKILL.md"))
        assert (d / "SKILL.md").read_text(encoding="utf-8") == "edited"

    def test_a_gone_file_still_clears_an_empty_dir(self, sandbox):
        d = paths.store_dir() / "wf"
        d.mkdir(parents=True)
        assert store._remove_skill_copy(_copy_row()) == (False, None)
        assert not d.exists()

    def test_rmdir_leaves_a_dir_with_files_and_anything_outside_the_store(
            self, sandbox, tmp_path):
        d = self._write()
        store._rmdir_quietly(d)
        assert d.is_dir()
        outside = tmp_path / "empty"
        outside.mkdir()
        store._rmdir_quietly(outside)
        assert outside.is_dir()


class TestOwnership:
    def test_owned_names_and_the_unrecorded_filter(self, sandbox):
        for n in ("wf", "loose"):
            (paths.store_dir() / n).mkdir(parents=True)
            (paths.store_dir() / n / "SKILL.md").write_text("x",
                                                            encoding="utf-8")
        lockfile.set_workflow("wf", _entry(_agent_row(), _copy_row()))
        lockfile.set_workflow("plain", _entry(_agent_row()))
        assert store.workflow_owned_store_names() == {"wf"}
        assert store.skill_copy_owner("wf") == "wf"
        assert store.skill_copy_owner("loose") is None
        assert store.unrecorded_store_dirs({}) == ["loose"]
        # The stale-link sweep's own set is untouched, so a link into the
        # copy is never swept as stale.
        assert "wf" in store._store_dirs()

    def test_drop_row_keeps_the_file(self, sandbox):
        lockfile.set_workflow("wf", _entry(_agent_row(), _copy_row()))
        store._drop_skill_copy_row("wf")
        assert lockfile.get_workflow("wf")["materializations"] == [
            _agent_row()]
        store._drop_skill_copy_row("missing")  # no entry: nothing to do
        assert lockfile.get_workflow("missing") is None

    def test_drop_row_clears_the_stash_too(self, sandbox):
        lockfile.set_workflow("wf", _entry(
            _agent_row(), _copy_row(), quarantined=True,
            quarantine_stash=[_agent_row(), {**_copy_row(), "content": "T"}]))
        store._drop_skill_copy_row("wf")
        got = lockfile.get_workflow("wf")
        assert got["quarantine_stash"] == [_agent_row()]
        assert got["materializations"] == [_agent_row()]
        # an entry with no stash does not grow one
        lockfile.set_workflow("wf", _entry(_copy_row()))
        store._drop_skill_copy_row("wf")
        assert "quarantine_stash" not in lockfile.get_workflow("wf")


class TestStashedCopyIsOurs:
    def _path(self):
        return paths.store_dir() / "wf" / "SKILL.md"

    def test_an_absent_dir_is_ours(self, sandbox):
        assert store._stashed_copy_is_ours(self._path(), "T") is True

    def test_a_recorded_skill_is_not(self, sandbox):
        lockfile.set_skill("wf", {"tap": "t"})
        assert store._stashed_copy_is_ours(self._path(), "T") is False

    def test_the_very_text_left_by_an_interrupted_quarantine_is(self,
                                                                sandbox):
        self._path().parent.mkdir(parents=True)
        self._path().write_text("T", encoding="utf-8")
        assert store._stashed_copy_is_ours(self._path(), "T") is True
        assert store._stashed_copy_is_ours(self._path(), "U") is False
        (self._path().parent / "extra.md").write_text("x", encoding="utf-8")
        assert store._stashed_copy_is_ours(self._path(), "T") is False

    def test_a_symlinked_dir_is_not(self, sandbox, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        (real / "SKILL.md").write_text("T", encoding="utf-8")
        paths.store_dir().mkdir(parents=True, exist_ok=True)
        self._path().parent.symlink_to(real)
        assert store._stashed_copy_is_ours(self._path(), "T") is False


class TestInstalledRaw:
    def test_needs_a_recorded_sha(self, sandbox):
        assert store._installed_raw(_entry()) is None

    def test_reads_a_verbatim_agent_file_whose_sha_matches(self, sandbox,
                                                           tmp_path):
        good = tmp_path / "good.md"
        good.write_text("RAW", encoding="utf-8")
        bad = tmp_path / "bad.md"
        bad.write_text("OTHER", encoding="utf-8")
        rows = [{**_agent_row("a"), "path": str(tmp_path / "missing.md")},
                {**_agent_row("b"), "path": str(bad)},
                {**_agent_row("c"), "path": str(good), "unwritable": True},
                _copy_row()]
        assert store._installed_raw(_entry(*rows, sha256=_sha("RAW"))) is None
        rows.append({**_agent_row("d"), "path": str(good)})
        assert store._installed_raw(_entry(*rows, sha256=_sha("RAW"))) == "RAW"


@pytest.mark.parametrize("scope", ["project"])
def test_project_scope_writes_nothing(sandbox, scope):
    assert store._skill_copy("wf", "agents", "---\ndescription: d\n---\nb\n",
                             None, None, scope) == (None, None)
    row, note = store._skill_copy("wf", "agents",
                                  "---\ndescription: d\n---\nb\n", None, True,
                                  scope)
    assert row is None
    assert note == ("not written to the skill store: --as-skill is user "
                    "scope only")
    assert not (paths.store_dir() / "wf").exists()


def test_skill_copy_writes_and_returns_the_exact_row(sandbox):
    raw = "---\nname: x\ndescription: d\ntools: Bash\n---\nbody\n"
    row, note = store._skill_copy("wf", "agents", raw, None, None, "user")
    text = "---\nname: wf\ndescription: d\n---\n\nbody\n"
    assert note is None
    assert row == {"agent": None, "slot": "skill",
                   "path": str(paths.store_dir() / "wf" / "SKILL.md"),
                   "sha256": _sha(text)}
    assert (paths.store_dir() / "wf" / "SKILL.md").read_text(
        encoding="utf-8") == text


def test_losing_the_description_retires_the_copy(sandbox):
    raw = "---\ndescription: d\n---\nbody\n"
    row, _ = store._skill_copy("wf", "agents", raw, None, None, "user")
    row2, note = store._skill_copy("wf", "agents", "---\nname: wf\n---\nb\n",
                                   _entry(row), None, "user")
    assert row2 is None
    assert "it has no description" in (note or "")
    assert not (paths.store_dir() / "wf").exists()


def test_losing_the_description_keeps_an_edited_copy_recorded(sandbox):
    raw = "---\ndescription: d\n---\nbody\n"
    row, _ = store._skill_copy("wf", "agents", raw, None, None, "user")
    (paths.store_dir() / "wf" / "SKILL.md").write_text("mine",
                                                     encoding="utf-8")
    row2, note = store._skill_copy("wf", "agents", "---\nname: wf\n---\nb\n",
                                   _entry(row), None, "user")
    assert row2 == row
    assert note == ("not written to the skill store: it has no description, "
                    "and a skill host picks skills by theirs; left the edited "
                    "~/.agents/skills/wf/SKILL.md in place")


def test_a_store_that_refuses_keeps_the_old_row(sandbox, monkeypatch):
    raw = "---\ndescription: d\n---\nbody\n"
    row, _ = store._skill_copy("wf", "agents", raw, None, None, "user")

    def refuse(*_a, **_k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(store.util, "atomic_write_text", refuse)
    row2, note = store._skill_copy("wf", "agents", raw, _entry(row), None,
                                   "user")
    assert row2 == row
    assert note == "not written to the skill store: Permission denied"


# --------------------------------------------------------------------------
# Through store.install / uninstall / quarantine / backfill
# --------------------------------------------------------------------------
AGENT = ("---\nname: reviewer\ndescription: Reviews diffs\nmodel: opus\n"
         "---\n\nRead the diff.\n")
COPY = "---\nname: reviewer\ndescription: Reviews diffs\n---\n\nRead the diff.\n"


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    from boost_cli.core import catalog, registry
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


def _wf(tap, body=AGENT, rel="agents/reviewer.md", name="reviewer"):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(body, encoding="utf-8")
    return {"name": name, "kind": "workflow", "tap": tap.name,
            "version": "1.0.0", "rel_dir": str(src.parent.relative_to(tap.path)),
            "skill_md": rel, "description": "", "curated": False, "meta": {}}


def _store_copy(name="reviewer"):
    return paths.store_dir() / name / "SKILL.md"


class TestInstallPath:
    def test_install_records_the_copy_last_and_reports_it(self, tap):
        res = store.install(_wf(tap))
        rows = lockfile.get_workflow("reviewer")["materializations"]
        assert rows[-1] == {"agent": None, "slot": "skill",
                            "path": str(_store_copy()), "sha256": _sha(COPY)}
        assert [m["slot"] for m in rows[:-1]] == ["agents"] * (len(rows) - 1)
        assert res.skill_copy == paths.store_dir() / "reviewer"
        assert res.skill_note is None
        assert res.dest != _store_copy()   # the first row is an agent's
        assert _store_copy().read_text(encoding="utf-8") == COPY
        assert "as_skill" not in lockfile.get_workflow("reviewer")

    def test_flags_are_recorded_and_replayed(self, tap):
        store.install(_wf(tap), as_skill=False)
        assert lockfile.get_workflow("reviewer")["as_skill"] is False
        res = store.install(_wf(tap), force=True)
        assert res.skill_copy is None
        assert lockfile.get_workflow("reviewer")["as_skill"] is False
        store.install(_wf(tap), force=True, as_skill=True)
        assert lockfile.get_workflow("reviewer")["as_skill"] is True
        assert _store_copy().is_file()

    def test_a_reinstall_rewrites_one_row(self, tap):
        store.install(_wf(tap))
        store.install(_wf(tap, AGENT.replace("Read the diff.", "New.")),
                      force=True)
        rows = lockfile.get_workflow("reviewer")["materializations"]
        assert [m for m in rows if m["slot"] == "skill"] == [
            {"agent": None, "slot": "skill", "path": str(_store_copy()),
             "sha256": _sha(COPY.replace("Read the diff.", "New."))}]

    def test_turning_it_off_says_so(self, tap):
        store.install(_wf(tap))
        res = store.install(_wf(tap), force=True, as_skill=False)
        assert res.skill_note == "removed its copy from the skill store"
        assert not (paths.store_dir() / "reviewer").exists()
        _store_copy().parent.mkdir(parents=True)
        # Off with nothing to remove: no note.
        res = store.install(_wf(tap), force=True)
        assert res.skill_note is None

    def test_turning_it_off_keeps_an_edited_copy(self, tap):
        store.install(_wf(tap))
        _store_copy().write_text("mine", encoding="utf-8")
        res = store.install(_wf(tap), force=True, as_skill=False)
        assert res.skill_note == ("left ~/.agents/skills/reviewer/SKILL.md in "
                                  "place: it was edited since boost wrote it")
        assert _store_copy().read_text(encoding="utf-8") == "mine"
        # still the workflow's, so sync never adopts it as a hand-added skill
        assert lockfile.is_skill_copy(
            lockfile.get_workflow("reviewer")["materializations"][-1])

    def test_a_skill_by_that_name_wins(self, tap):
        lockfile.set_skill("reviewer", {"tap": "t"})
        res = store.install(_wf(tap))
        assert res.skill_copy is None
        assert res.skill_note == ("a skill named reviewer is already installed "
                                  "— the workflow is not written to the skill "
                                  "store")
        assert not _store_copy().exists()


class TestRemovalPaths:
    def test_uninstall_removes_the_file_and_the_dir(self, tap):
        store.install(_wf(tap))
        info = store.uninstall("reviewer")
        assert "kept" not in info
        assert not (paths.store_dir() / "reviewer").exists()
        assert "skill" not in info["unlinked"] and None not in info["unlinked"]

    def test_uninstall_keeps_an_edited_copy_and_names_it(self, tap):
        store.install(_wf(tap))
        _store_copy().write_text("mine", encoding="utf-8")
        info = store.uninstall("reviewer")
        assert info["kept"] == [str(_store_copy())]
        assert _store_copy().read_text(encoding="utf-8") == "mine"
        assert lockfile.get_workflow("reviewer") is None

    def test_uninstall_leaves_a_dir_the_user_added_files_to(self, tap):
        store.install(_wf(tap))
        (paths.store_dir() / "reviewer" / "notes.md").write_text(
            "n", encoding="utf-8")
        store.uninstall("reviewer")
        assert not _store_copy().exists()
        assert (paths.store_dir() / "reviewer" / "notes.md").is_file()

    def test_quarantine_removes_the_dir_and_release_restores_it(self, tap):
        store.install(_wf(tap))
        entry = lockfile.get_workflow("reviewer")
        store.quarantine_materialized("workflow", "reviewer", entry)
        assert not (paths.store_dir() / "reviewer").exists()
        assert "reviewer" in store.workflow_owned_store_names()
        store.release_materialized("workflow", "reviewer",
                                   lockfile.get_workflow("reviewer"))
        assert _store_copy().read_text(encoding="utf-8") == COPY

    def test_refuse_unrecorded_names_the_owner_and_force_disowns(self, tap):
        from boost_cli.errors import BoostError
        store.install(_wf(tap))
        with pytest.raises(BoostError) as err:
            store._refuse_unrecorded("reviewer", None, False)
        assert err.value.message == (
            "reviewer is already in the store at ~/.agents/skills/reviewer, "
            "as the skill copy of workflow reviewer")
        assert err.value.hint == ("`boost install %s:reviewer --path agents "
                                  "--force --no-as-skill` takes the copy out "
                                  "of the store" % lockfile.get_workflow(
                                      "reviewer")["tap"])
        # An entry of its own means the skill is boost's already: no refusal.
        store._refuse_unrecorded("reviewer", {"tap": "t"}, False)
        assert "reviewer" in store.workflow_owned_store_names()
        # Forced, it names the owner and disowns nothing yet: the caller
        # drops the row only once every later refusal has passed.
        assert store._refuse_unrecorded("reviewer", None, True) == "reviewer"
        assert "reviewer" in store.workflow_owned_store_names()
        store._drop_skill_copy_row("reviewer")
        assert "reviewer" not in store.workflow_owned_store_names()
        assert _store_copy().is_file()


class TestBackfill:
    def _strip(self):
        entry = lockfile.get_workflow("reviewer")
        entry["materializations"] = [m for m in entry["materializations"]
                                     if m["slot"] != "skill"]
        lockfile.set_workflow("reviewer", entry)
        _store_copy().unlink()
        _store_copy().parent.rmdir()

    def test_dry_then_real(self, tap):
        store.install(_wf(tap))
        self._strip()
        assert store.workflows_without_skill_copy() == ["reviewer"]
        assert store.backfill_skill_copies(dry=True) == [
            "would write workflow reviewer's skill copy to "
            "~/.agents/skills/reviewer and link it → windsurf · antigravity"]
        assert not _store_copy().exists()
        assert store.backfill_skill_copies() == [
            "wrote workflow reviewer's skill copy to ~/.agents/skills/reviewer "
            "and linked it → windsurf · antigravity"]
        assert _store_copy().read_text(encoding="utf-8") == COPY
        assert lockfile.get_workflow("reviewer")["materializations"][-1] == {
            "agent": None, "slot": "skill", "path": str(_store_copy()),
            "sha256": _sha(COPY)}
        assert store.workflows_without_skill_copy() == []
        assert store.backfill_skill_copies() == []

    @pytest.mark.parametrize("change", ["quarantined", "project", "no",
                                        "blocked", "nodesc", "config"])
    def test_what_is_not_a_candidate(self, tap, change):
        body = AGENT if change != "nodesc" else "---\nname: reviewer\n---\nx\n"
        store.install(_wf(tap, body), as_skill=False)
        entry = lockfile.get_workflow("reviewer")
        if change != "no":
            entry.pop("as_skill")
        if change == "quarantined":
            entry["quarantined"] = True
        if change == "project":
            entry["scope"] = "project"
        if change == "blocked":
            (paths.store_dir() / "reviewer").mkdir(parents=True)
        if change == "config":
            config.set_value("workflows_as_skills", "false")
        lockfile.set_workflow("reviewer", entry)
        assert store.workflows_without_skill_copy() == []

    def test_a_write_that_fails_reports_the_reason(self, tap, monkeypatch):
        store.install(_wf(tap))
        self._strip()

        def refuse(*_a, **_k):
            raise PermissionError(13, "Permission denied")
        monkeypatch.setattr(store.util, "atomic_write_text", refuse)
        assert store.backfill_skill_copies() == [
            "workflow reviewer: not written to the skill store: Permission "
            "denied"]
        assert not any(m["slot"] == "skill" for m in
                       lockfile.get_workflow("reviewer")["materializations"])

    def test_the_slot_falls_back_to_the_source_path(self, tap):
        store.install(_wf(tap))
        self._strip()
        entry = lockfile.get_workflow("reviewer")
        entry.pop("slot")
        lockfile.set_workflow("reviewer", entry)
        assert store.workflows_without_skill_copy() == ["reviewer"]
        store.backfill_skill_copies()
        assert _store_copy().is_file()


@pytest.mark.parametrize(("tap", "name", "rel_dir", "want"), [
    ("t", "ship", "skills/ship", "boost install t:ship --path skills/ship"),
    ("t", "ship", ".", "boost install t:ship"),
    ("t", "ship", None, "boost install t:ship"),
    ("t", "ship", "", "boost install t:ship"),
    (None, "ship", "agents", "boost install ship --path agents"),
    (None, "ship", None, "boost install ship"),
])
def test_install_spelling_names_one_item(tap, name, rel_dir, want):
    assert store.install_spelling(tap, name, rel_dir) == want


def test_workflow_spelling_without_a_lock_row_is_the_bare_name(sandbox):
    assert store._workflow_spelling("nothing") == "boost install nothing"


# --------------------------------------------------------------------------
# Copy links: the copy reaches the linking agents that get no workflow file
# --------------------------------------------------------------------------
# A skills-only agent (antigravity, a Claude Code profile added as
# `skills_only`) and one with no slash-command format (windsurf) get no file
# of the workflow's own, so without a link to the copy they got the procedure
# in no form. claude-code and cursor hold agents/<name>.md and get no link:
# that would show them the procedure twice.

def _linked(entry, name="reviewer"):
    return list(store.copy_link_targets(name, entry))


def _workflow_entry(*agent_rows, **extra):
    extra.setdefault("only_agents", None)
    return _entry(*(_agent_row(a) for a in agent_rows),
                  _copy_row("reviewer"), **extra)


class TestCopyLinkTargets:
    """A pure function of the lock row and the agent table: no disk."""

    def test_the_linking_agents_with_no_row_of_their_own(self, sandbox):
        entry = _workflow_entry("claude-code", "cursor")
        assert _linked(entry) == ["windsurf", "antigravity"]
        assert store.copy_link_targets("reviewer", entry) == {
            "windsurf": paths.home() / ".windsurf" / "skills",
            "antigravity": paths.home() / ".gemini" / "antigravity-cli"
                           / "skills"}

    def test_a_declared_narrowing_links_nowhere(self, sandbox):
        assert _linked(_workflow_entry("claude-code",
                                       only_agents=["claude-code"])) == []

    def test_no_copy_row_links_nowhere(self, sandbox):
        entry = _entry(_agent_row("claude-code"), _agent_row("cursor"),
                       only_agents=None)
        assert _linked(entry) == []
        assert _linked(None) == []

    def test_quarantined_links_nowhere(self, sandbox):
        assert _linked(_workflow_entry("claude-code", "cursor",
                                       quarantined=True)) == []

    def test_a_copy_kept_only_because_it_was_edited_links_nowhere(self,
                                                                  sandbox):
        # --no-as-skill over an edited copy keeps the row, not the request.
        assert _linked(_workflow_entry("claude-code", "cursor",
                                       as_skill=False)) == []
        config.set_value("workflows_as_skills", "false")
        assert _linked(_workflow_entry("claude-code", "cursor")) == []
        assert _linked(_workflow_entry("claude-code", "cursor",
                                       as_skill=True)) == [
            "windsurf", "antigravity"]

    def test_a_skill_by_that_name_owns_the_store_dir(self, sandbox):
        lockfile.set_skill("reviewer", {"tap": "t"})
        assert _linked(_workflow_entry("claude-code", "cursor")) == []

    @pytest.mark.parametrize("key", ["foreign", "declined"])
    def test_an_agent_a_foreign_or_declined_row_names_is_left_out(
            self, sandbox, key):
        row = {"agent": "windsurf", "slot": "agents", "path": "/x",
               "reason": "r"}
        entry = _workflow_entry("claude-code", "cursor", **{key: [row]})
        assert _linked(entry) == ["antigravity"]

    def test_an_agent_due_its_own_file_is_left_out(self, sandbox):
        # cursor takes workflows and has no row yet: `boost sync` writes its
        # file, so a link now would only be taken back.
        assert _linked(_workflow_entry("claude-code")) == [
            "windsurf", "antigravity"]
        # An entry from before `only_agents` was recorded replays its rows,
        # so cursor is not due a file -- and its rows are the only record of
        # an `--agent` narrowing, so an agent the workflow set writes with
        # no row was left out, not left pending: no link either.
        legacy = _workflow_entry("claude-code")
        legacy.pop("only_agents")
        assert _linked(legacy) == ["windsurf", "antigravity"]
        cfg = config.load()
        cfg["agents"]["windsurf"]["workflows"] = True
        config.save(cfg)
        assert _linked(legacy) == ["antigravity"]

    def test_follows_the_agent_table(self, sandbox):
        cfg = config.load()
        cfg["agents"]["claude-personal"] = {
            "dir": "~/.claude-personal/skills", "enabled": True,
            "skills_only": True}
        cfg["agents"]["antigravity"]["enabled"] = False
        cfg["agents"]["windsurf"]["workflows"] = True
        config.save(cfg)
        entry = _workflow_entry("claude-code", "cursor", "windsurf")
        assert _linked(entry) == ["claude-personal"]
        # every linking agent has a file of its own: nothing to link
        entry = _workflow_entry("claude-code", "cursor", "windsurf",
                                "claude-personal")
        assert _linked(entry) == []

    def test_copy_link_agents(self, sandbox):
        assert list(store.copy_link_agents({"claude-code", "cursor"})) == [
            "windsurf", "antigravity"]
        assert list(store.copy_link_agents(set())) == [
            "claude-code", "windsurf", "cursor", "antigravity"]
        assert store.copy_link_agents(set(), narrowed=True) == {}


def _copy_on_disk(name="reviewer", text="T"):
    d = paths.store_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    return d


def _agent_dir(agent):
    from boost_cli.core import agents
    d = agents.known_agents()[agent]["dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestCopyLinksOnDisk:
    def test_link_creates_only_the_targets_and_keeps_theirs(self, sandbox,
                                                            tmp_path):
        target = _copy_on_disk()
        elsewhere = tmp_path / "mine"
        elsewhere.mkdir()
        (_agent_dir("windsurf") / "reviewer").symlink_to(elsewhere)
        res = store.link_skill_copy("reviewer",
                                    _workflow_entry("claude-code", "cursor"))
        assert res is not None
        assert res.linked == ["antigravity"]
        assert res.conflicts == [str(_agent_dir("windsurf") / "reviewer")]
        assert (_agent_dir("antigravity") / "reviewer").resolve() == \
            target.resolve()
        # the user's link is theirs, and stays pointing where it did
        assert (_agent_dir("windsurf") / "reviewer").resolve() == \
            elsewhere.resolve()
        for agent in ("claude-code", "cursor"):
            assert not (_agent_dir(agent) / "reviewer").is_symlink()

    def test_only_limits_the_targets_and_empty_is_none(self, sandbox):
        _copy_on_disk()
        entry = _workflow_entry("claude-code", "cursor")
        res = store.link_skill_copy("reviewer", entry, only=["windsurf",
                                                             "cursor"])
        assert res is not None
        assert res.linked == ["windsurf"]
        assert not os.path.lexists(_agent_dir("antigravity") / "reviewer")
        assert not os.path.lexists(_agent_dir("cursor") / "reviewer")
        # `link_agents` reads an empty `only` as every agent: never passed
        assert store.link_skill_copy("reviewer", entry, only=[]) is None
        assert store.reconcile_copy_links("reviewer", entry, only=[]) == (
            [], [], [])
        assert not os.path.lexists(_agent_dir("antigravity") / "reviewer")

    def test_no_target_means_no_link_anywhere(self, sandbox):
        """An empty `only` is every agent to `link_agents`, so the call is
        never made with one."""
        _copy_on_disk()
        assert store.link_skill_copy(
            "reviewer", _workflow_entry("claude-code",
                                        only_agents=["claude-code"])) is None
        for agent in ("claude-code", "windsurf", "cursor", "antigravity"):
            assert not os.path.lexists(_agent_dir(agent) / "reviewer")

    def test_missing_names_what_sync_can_link(self, sandbox, tmp_path):
        _copy_on_disk()
        _copy_on_disk("other")
        entry = _workflow_entry("claude-code", "cursor")
        assert store.missing_copy_links("reviewer", entry) == [
            "windsurf", "antigravity"]
        # boost's link into another store dir is wrong, and is replaced
        (_agent_dir("windsurf") / "reviewer").symlink_to(
            paths.store_dir() / "other")
        # the right one is fine
        (_agent_dir("antigravity") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        assert store.missing_copy_links("reviewer", entry) == ["windsurf"]
        # the user's own link, or a file, is not boost's to replace
        (_agent_dir("windsurf") / "reviewer").unlink()
        (_agent_dir("windsurf") / "reviewer").symlink_to(tmp_path)
        assert store.missing_copy_links("reviewer", entry) == []
        (_agent_dir("windsurf") / "reviewer").unlink()
        (_agent_dir("windsurf") / "reviewer").write_text("x",
                                                         encoding="utf-8")
        assert store.missing_copy_links("reviewer", entry) == []

    def test_missing_needs_the_copy_on_disk(self, sandbox):
        # Its own repair (a missing materialization) reinstalls, which links.
        assert store.missing_copy_links(
            "reviewer", _workflow_entry("claude-code", "cursor")) == []

    def test_a_dangling_boost_link_is_missing(self, sandbox):
        _copy_on_disk()
        (_agent_dir("windsurf") / "reviewer").symlink_to(
            paths.store_dir() / "gone")
        assert store.missing_copy_links(
            "reviewer", _workflow_entry("claude-code", "cursor")) == [
            "windsurf", "antigravity"]

    def test_stale_is_a_copy_link_beside_the_workflows_own_file(self,
                                                                sandbox,
                                                                tmp_path):
        _copy_on_disk()
        _copy_on_disk("other")
        entry = _workflow_entry("claude-code", "cursor")
        assert store.stale_copy_links("reviewer", entry) == []
        (_agent_dir("claude-code") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        (_agent_dir("cursor") / "reviewer").symlink_to(
            paths.store_dir() / "other")
        (_agent_dir("windsurf") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        # cursor's leads elsewhere and windsurf's is wanted
        assert store.stale_copy_links("reviewer", entry) == ["claude-code"]
        # with no copy row, or a skill owning the dir, the link is not ours
        assert store.stale_copy_links(
            "reviewer", _entry(_agent_row("claude-code"))) == []
        lockfile.set_skill("reviewer", {"tap": "t"})
        assert store.stale_copy_links("reviewer", entry) == []

    def test_under_a_narrowing_every_copy_link_is_stale(self, sandbox):
        """A declared `--agent` narrowing links nowhere, so a link an
        earlier, wider install made is stale wherever it is."""
        _copy_on_disk()
        entry = _workflow_entry("claude-code", only_agents=["claude-code"])
        for agent in ("claude-code", "windsurf", "antigravity"):
            (_agent_dir(agent) / "reviewer").symlink_to(
                paths.store_dir() / "reviewer")
        assert store.stale_copy_links("reviewer", entry) == [
            "claude-code", "windsurf", "antigravity"]
        entry["only_agents"] = None
        assert store.stale_copy_links("reviewer", entry) == ["claude-code"]

    def test_the_reason_a_link_is_stale(self, sandbox):
        entry = _workflow_entry("claude-code", only_agents=["claude-code"],
                                foreign=[{"agent": "cursor", "slot": "agents",
                                          "path": "/x"}])
        assert store.stale_copy_reason(entry, "claude-code") == (
            "which has the workflow's own file")
        assert store.stale_copy_reason(entry, "cursor") == (
            "which has the workflow's own file")
        assert store.stale_copy_reason(entry, "windsurf") == (
            "which the workflow's --agent scope leaves out")

    def test_a_dir_shared_with_an_agent_holding_its_own_file(self, sandbox):
        """``~/.claude-personal/skills -> ../.claude/skills`` is claude-code's
        dir under a second name: decided by name, the copy was linked there
        for claude-personal and unlinked as claude-code's in the same run."""
        _copy_on_disk()
        home = paths.home()
        (home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        (home / ".claude-personal").mkdir()
        (home / ".claude-personal" / "skills").symlink_to(
            os.path.join("..", ".claude", "skills"))
        cfg = config.load()
        cfg["agents"]["claude-personal"] = {
            "dir": "~/.claude-personal/skills", "enabled": True,
            "skills_only": True}
        config.save(cfg)
        entry = _workflow_entry("claude-code", "cursor")
        assert _linked(entry) == ["windsurf", "antigravity"]
        assert list(store.copy_link_agents({"claude-code", "cursor"})) == [
            "windsurf", "antigravity"]
        assert store.missing_copy_links("reviewer", entry) == [
            "windsurf", "antigravity"]
        # a link there is stale, and named once: by the agent with the file
        (home / ".claude" / "skills" / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        assert store.stale_copy_links("reviewer", entry) == ["claude-code"]
        assert store.reconcile_copy_links("reviewer", entry)[2] == [
            "claude-code"]
        assert not os.path.lexists(home / ".claude" / "skills" / "reviewer")
        # With claude-code no longer a linking agent its row still holds the
        # file, so the profile's name is the one that speaks for the dir.
        cfg["agents"]["claude-code"]["enabled"] = False
        config.save(cfg)
        (home / ".claude" / "skills" / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        assert store.stale_copy_links("reviewer", entry) == ["claude-personal"]
        assert store.stale_copy_reason(entry, "claude-personal") == (
            "whose skills dir is claude-code's, which has the workflow's own "
            "file")
        assert "claude-personal" not in _linked(entry)

    def test_unlink_takes_only_links_to_this_copy(self, sandbox, tmp_path):
        _copy_on_disk()
        _copy_on_disk("other")
        (_agent_dir("windsurf") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        (_agent_dir("antigravity") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        (_agent_dir("claude-code") / "reviewer").symlink_to(
            paths.store_dir() / "other")
        (_agent_dir("cursor") / "reviewer").symlink_to(tmp_path)
        assert store.unlink_skill_copy("reviewer", only=["antigravity"]) == [
            "antigravity"]
        assert (_agent_dir("windsurf") / "reviewer").is_symlink()
        assert store.unlink_skill_copy("reviewer") == ["windsurf"]
        assert not os.path.lexists(_agent_dir("windsurf") / "reviewer")
        assert not os.path.lexists(_agent_dir("antigravity") / "reviewer")
        assert (_agent_dir("claude-code") / "reviewer").is_symlink()
        assert (_agent_dir("cursor") / "reviewer").is_symlink()
        assert store.unlink_skill_copy("reviewer", only=[]) == []

    def test_unlink_sweeps_dangling_disabled_and_former_dirs(self, sandbox):
        from boost_cli.core import agents
        old = paths.home() / ".old-windsurf" / "skills"
        old.mkdir(parents=True)
        agents.remember_link_dir("windsurf", old)
        (old / "reviewer").symlink_to(paths.store_dir() / "reviewer")
        cfg = config.load()
        cfg["agents"]["antigravity"]["enabled"] = False
        config.save(cfg)
        (_agent_dir("antigravity") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        # dangling: no copy on disk at all
        assert sorted(store.unlink_skill_copy("reviewer")) == [
            "antigravity", "windsurf"]
        assert not os.path.lexists(old / "reviewer")
        assert not os.path.lexists(_agent_dir("antigravity") / "reviewer")

    def test_unlink_leaves_a_skills_links(self, sandbox):
        _copy_on_disk()
        (_agent_dir("windsurf") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        lockfile.set_skill("reviewer", {"tap": "t"})
        assert store.unlink_skill_copy("reviewer") == []
        assert (_agent_dir("windsurf") / "reviewer").is_symlink()

    def test_problems_are_worded(self, sandbox):
        res = store.InstallResult("reviewer", paths.store_dir() / "reviewer")
        res.conflicts = [str(paths.home() / ".windsurf/skills/reviewer")]
        res.unwritable = [str(paths.home() / ".gemini")]
        res.unlinkable = [str(paths.home() / ".x")]
        res.blocked = [(str(paths.home() / ".y/skills"),
                        str(paths.home() / ".y"))]
        lines = store.copy_link_problems(res)
        assert lines[0] == ("~/.windsurf/skills/reviewer is in the way and "
                            "is not boost's — left alone")
        assert lines[1] == "%s — %s" % store.unwritable_refusal(
            res.unwritable[0])
        assert lines[2] == "%s — %s" % store.link_refusal(*res.blocked[0])
        assert lines[3] == "%s — %s" % store.symlink_refusal(
            res.unlinkable[0])
        assert len(lines) == 4


class TestCopyLinksThroughInstall:
    def _links(self):
        return {a: os.path.realpath(_agent_dir(a) / "reviewer")
                for a in ("claude-code", "windsurf", "cursor", "antigravity")
                if os.path.lexists(_agent_dir(a) / "reviewer")}

    def test_install_links_and_reports(self, tap):
        res = store.install(_wf(tap))
        want = os.path.realpath(paths.store_dir() / "reviewer")
        assert self._links() == {"windsurf": want, "antigravity": want}
        assert res.copy_linked == ["windsurf", "antigravity"]
        assert res.copy_blocked == []
        # none of it is recorded: the set is derived from the row each time
        entry = lockfile.get_workflow("reviewer")
        assert [m for m in entry["materializations"]
                if lockfile.is_skill_copy(m)] == [store._copy_row(entry)]
        assert "copy_links" not in entry

    def test_a_narrowed_install_links_nothing(self, tap):
        res = store.install(_wf(tap), only_agents=["claude-code"])
        assert self._links() == {}
        assert res.copy_linked == []

    def test_a_narrowed_reinstall_takes_every_earlier_link(self, tap):
        """Narrowed after a wide install: no copy links, the disabled
        agent's included, and nothing left for doctor or sync to name."""
        store.install(_wf(tap))
        cfg = config.load()
        cfg["agents"]["antigravity"]["enabled"] = False
        config.save(cfg)
        res = store.install(_wf(tap), force=True, only_agents=["claude-code"])
        assert self._links() == {}
        assert res.copy_linked == []
        assert res.copy_unlinked == ["windsurf", "antigravity"]
        entry = lockfile.get_workflow("reviewer")
        assert store.missing_copy_links("reviewer", entry) == []
        assert store.stale_copy_links("reviewer", entry) == []

    def test_install_reports_what_is_in_the_way(self, tap, tmp_path):
        (_agent_dir("windsurf") / "reviewer").symlink_to(tmp_path)
        res = store.install(_wf(tap))
        assert res.copy_linked == ["antigravity"]
        assert res.copy_blocked == [
            "~/.windsurf/skills/reviewer is in the way and is not boost's "
            "— left alone"]
        assert os.path.realpath(_agent_dir("windsurf") / "reviewer") == \
            os.path.realpath(tmp_path)

    def test_retiring_the_copy_unlinks_it(self, tap):
        store.install(_wf(tap))
        res = store.install(_wf(tap), force=True, as_skill=False)
        assert self._links() == {}
        assert res.copy_unlinked == ["windsurf", "antigravity"]

    def test_an_edited_copy_kept_on_retire_keeps_its_links(self, tap):
        store.install(_wf(tap))
        _store_copy().write_text("mine", encoding="utf-8")
        store.install(_wf(tap), force=True, as_skill=False)
        assert set(self._links()) == {"windsurf", "antigravity"}

    def test_a_skill_by_that_name_keeps_its_links(self, tap):
        _copy_on_disk(text="---\nname: reviewer\ndescription: d\n---\nx\n")
        lockfile.set_skill("reviewer", {"tap": "t"})
        store.link_agents("reviewer")
        store.install(_wf(tap), force=True)
        assert set(self._links()) == {"claude-code", "windsurf", "cursor",
                                      "antigravity"}
        store._uninstall_workflow("reviewer",
                                  lockfile.get_workflow("reviewer"))
        assert set(self._links()) == {"claude-code", "windsurf", "cursor",
                                      "antigravity"}

    def test_moving_an_agent_into_the_workflow_set_unlinks_it(self, tap):
        store.install(_wf(tap))
        cfg = config.load()
        cfg["agents"]["windsurf"]["workflows"] = True
        config.save(cfg)
        res = store.install(_wf(tap), force=True)
        assert (paths.home() / ".windsurf" / "agents" / "reviewer.md").is_file()
        assert set(self._links()) == {"antigravity"}
        assert res.copy_unlinked == ["windsurf"]

    def test_a_failed_lock_write_takes_a_fresh_copys_links_back(
            self, tap, monkeypatch):
        def boom(*_a, **_k):
            raise KeyboardInterrupt
        monkeypatch.setattr(lockfile, "set_workflow", boom)
        with pytest.raises(KeyboardInterrupt):
            store.install(_wf(tap))
        assert self._links() == {}
        assert not (paths.store_dir() / "reviewer").exists()

    def test_uninstall_unlinks_and_an_edited_copy_keeps_them(self, tap):
        store.install(_wf(tap))
        store.uninstall("reviewer")
        assert self._links() == {}
        store.install(_wf(tap))
        _store_copy().write_text("mine", encoding="utf-8")
        store.uninstall("reviewer")
        assert set(self._links()) == {"windsurf", "antigravity"}

    def test_quarantine_unlinks_and_release_relinks(self, tap):
        store.install(_wf(tap))
        store.quarantine_materialized("workflow", "reviewer",
                                      lockfile.get_workflow("reviewer"))
        assert self._links() == {}
        store.release_materialized("workflow", "reviewer",
                                   lockfile.get_workflow("reviewer"))
        assert set(self._links()) == {"windsurf", "antigravity"}

    def test_release_names_a_link_it_could_not_make(self, tap, tmp_path):
        store.install(_wf(tap))
        store.quarantine_materialized("workflow", "reviewer",
                                      lockfile.get_workflow("reviewer"))
        (_agent_dir("windsurf") / "reviewer").symlink_to(tmp_path)
        problems: list[str] = []
        store.release_materialized("workflow", "reviewer",
                                   lockfile.get_workflow("reviewer"),
                                   problems=problems)
        assert problems == ["~/.windsurf/skills/reviewer is in the way and "
                            "is not boost's — left alone"]
        assert set(self._links()) == {"windsurf", "antigravity"}
        assert os.path.realpath(_agent_dir("windsurf") / "reviewer") == \
            os.path.realpath(tmp_path)

    def test_release_links_nothing_to_a_copy_it_did_not_restore(self, tap):
        """A copy gone before quarantine stashes no content, so release
        writes no file -- and a link to it would dangle."""
        store.install(_wf(tap))
        util.remove_path(paths.store_dir() / "reviewer")
        store.quarantine_materialized("workflow", "reviewer",
                                      lockfile.get_workflow("reviewer"))
        assert self._links() == {}
        store.release_materialized("workflow", "reviewer",
                                   lockfile.get_workflow("reviewer"))
        assert not (paths.store_dir() / "reviewer").exists()
        assert self._links() == {}
        assert store.link_skill_copy(
            "reviewer", lockfile.get_workflow("reviewer")) is None

    def test_a_copy_the_store_refused_is_not_linked(self, tap, monkeypatch):
        """`_skill_copy` keeps the old row when the store refuses the write,
        whether or not its file is still there."""
        store.install(_wf(tap))
        util.remove_path(paths.store_dir() / "reviewer")
        store.unlink_skill_copy("reviewer")
        write = util.atomic_write_text

        def refuse(path, *a, **k):
            if paths.store_dir() / "reviewer" in Path(path).parents:
                raise PermissionError(13, "Permission denied")
            return write(path, *a, **k)
        monkeypatch.setattr(util, "atomic_write_text", refuse)
        res = store.install(_wf(tap), force=True)
        assert store._copy_row(lockfile.get_workflow("reviewer")) is not None
        assert res.copy_linked == []
        assert self._links() == {}

    def test_backfill_links_what_it_writes(self, tap):
        store.install(_wf(tap), as_skill=False)
        entry = lockfile.get_workflow("reviewer")
        entry.pop("as_skill")
        lockfile.set_workflow("reviewer", entry)
        assert store.backfill_skill_copies(dry=True) == [
            "would write workflow reviewer's skill copy to "
            "~/.agents/skills/reviewer and link it → windsurf · antigravity"]
        assert self._links() == {}
        assert store.backfill_skill_copies() == [
            "wrote workflow reviewer's skill copy to ~/.agents/skills/"
            "reviewer and linked it → windsurf · antigravity"]
        assert set(self._links()) == {"windsurf", "antigravity"}

    def test_backfill_names_a_link_it_could_not_make(self, tap, tmp_path):
        store.install(_wf(tap), as_skill=False)
        entry = lockfile.get_workflow("reviewer")
        entry.pop("as_skill")
        lockfile.set_workflow("reviewer", entry)
        cfg = config.load()
        cfg["agents"]["antigravity"]["enabled"] = False
        config.save(cfg)
        (_agent_dir("windsurf") / "reviewer").symlink_to(tmp_path)
        assert store.backfill_skill_copies(dry=True) == [
            "would write workflow reviewer's skill copy to "
            "~/.agents/skills/reviewer and link it → windsurf"]
        assert store.backfill_skill_copies() == [
            "wrote workflow reviewer's skill copy to ~/.agents/skills/"
            "reviewer",
            "workflow reviewer: skill copy not linked: ~/.windsurf/skills/"
            "reviewer is in the way and is not boost's — left alone"]
        assert os.path.realpath(_agent_dir("windsurf") / "reviewer") == \
            os.path.realpath(tmp_path)


class TestCopyLinksThroughSync:
    def test_plan_keys_are_their_own(self, tap):
        plan = store.sync_plan()
        assert plan["missing_copy_links"] == []
        assert plan["stale_copy_links"] == []
        store.install(_wf(tap))
        (_agent_dir("windsurf") / "reviewer").unlink()
        (_agent_dir("claude-code") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        plan = store.sync_plan()
        assert plan["missing_copy_links"] == [("reviewer", "windsurf")]
        assert plan["stale_copy_links"] == [("reviewer", "claude-code")]
        assert plan["missing_links"] == []
        assert store.plan_issues(plan) == 2
        assert store.sync_preview(plan)[-2:] == [
            "would link workflow reviewer's skill copy → windsurf",
            "would unlink workflow reviewer's skill copy from claude-code, "
            "which has the workflow's own file"]
        actions = store.sync_apply(plan)
        assert "linked workflow reviewer's skill copy → windsurf" in actions
        assert ("unlinked workflow reviewer's skill copy from claude-code, "
                "which has the workflow's own file") in actions
        assert os.path.lexists(_agent_dir("windsurf") / "reviewer")
        assert not os.path.lexists(_agent_dir("claude-code") / "reviewer")
        assert lockfile.get_skill("reviewer") is None
        plan = store.sync_plan()
        assert plan["missing_copy_links"] == plan["stale_copy_links"] == []

    def test_plan_rows_follow_the_workflow_names(self, tap):
        store.install(_wf(tap, rel="agents/zeta.md", name="zeta"))
        store.install(_wf(tap))
        for name in ("zeta", "reviewer"):
            (_agent_dir("windsurf") / name).unlink()
            (_agent_dir("claude-code") / name).symlink_to(
                paths.store_dir() / name)
        plan = store.sync_plan()
        assert plan["missing_copy_links"] == [("reviewer", "windsurf"),
                                              ("zeta", "windsurf")]
        assert plan["stale_copy_links"] == [("reviewer", "claude-code"),
                                            ("zeta", "claude-code")]
        assert store.sync_preview(plan)[-4:] == [
            "would link workflow reviewer's skill copy → windsurf",
            "would link workflow zeta's skill copy → windsurf",
            "would unlink workflow reviewer's skill copy from claude-code, "
            "which has the workflow's own file",
            "would unlink workflow zeta's skill copy from claude-code, "
            "which has the workflow's own file"]

    def test_apply_links_only_what_the_plan_named(self, tap, tmp_path):
        """The user's own link at windsurf is not a fault doctor counts, so
        repairing antigravity must not report it -- or exit 1 over it."""
        store.install(_wf(tap))
        (_agent_dir("windsurf") / "reviewer").unlink()
        (_agent_dir("windsurf") / "reviewer").symlink_to(tmp_path)
        (_agent_dir("antigravity") / "reviewer").unlink()
        plan = store.sync_plan()
        assert plan["missing_copy_links"] == [("reviewer", "antigravity")]
        actions = store.sync_apply(plan)
        assert [a for a in actions if "skill copy" in a] == [
            "linked workflow reviewer's skill copy → antigravity"]
        assert not any(store.is_unrepaired(a) for a in actions)

    def test_apply_names_a_planned_link_it_could_not_make(self, tap,
                                                          tmp_path):
        store.install(_wf(tap))
        (_agent_dir("windsurf") / "reviewer").unlink()
        plan = store.sync_plan()
        assert plan["missing_copy_links"] == [("reviewer", "windsurf")]
        # the user's link lands between the plan and the repair
        (_agent_dir("windsurf") / "reviewer").symlink_to(tmp_path)
        lines = [a for a in store.sync_apply(plan) if "skill copy" in a]
        assert lines == [
            "workflow reviewer's skill copy was not linked: ~/.windsurf/"
            "skills/reviewer is in the way and is not boost's — left alone"]
        assert store.is_unrepaired(lines[0])
        assert os.path.realpath(_agent_dir("windsurf") / "reviewer") == \
            os.path.realpath(tmp_path)

    def test_a_legacy_narrowed_entry_never_links_cursor(self, tap):
        """A row from before `only_agents` was recorded: sync links the
        agents that take no workflow file, and never one that does."""
        store.install(_wf(tap), only_agents=["claude-code"])
        entry = lockfile.get_workflow("reviewer")
        entry.pop("only_agents")
        lockfile.set_workflow("reviewer", entry)
        plan = store.sync_plan()
        assert plan["missing_copy_links"] == [("reviewer", "windsurf"),
                                              ("reviewer", "antigravity")]
        store.sync_apply(plan)
        assert not os.path.lexists(_agent_dir("cursor") / "reviewer")
        assert os.path.islink(_agent_dir("windsurf") / "reviewer")

    def test_the_mcp_doctor_words_both_keys(self, tap):
        from boost_cli.commands import configuration
        store.install(_wf(tap))
        (_agent_dir("windsurf") / "reviewer").unlink()
        (_agent_dir("claude-code") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        text, _ = configuration._tool_doctor({})
        assert ("workflow reviewer's skill copy is not linked for windsurf — "
                "`boost sync` links it") in text
        assert ("workflow reviewer's skill copy is linked for claude-code, "
                "which has the workflow's own file — `boost sync` removes "
                "the link") in text

    def test_a_link_under_a_narrowing_is_named_and_removed(self, tap):
        store.install(_wf(tap), only_agents=["claude-code"])
        (_agent_dir("windsurf") / "reviewer").symlink_to(
            paths.store_dir() / "reviewer")
        plan = store.sync_plan()
        assert plan["stale_copy_links"] == [("reviewer", "windsurf")]
        assert plan["missing_copy_links"] == []
        line = ("unlink workflow reviewer's skill copy from windsurf, which "
                "the workflow's --agent scope leaves out")
        assert store.sync_preview(plan)[-1:] == ["would " + line]
        assert [a for a in store.sync_apply(plan) if "skill copy" in a] == [
            line.replace("unlink", "unlinked", 1)]
        assert not os.path.lexists(_agent_dir("windsurf") / "reviewer")

    def test_apply_rechecks_the_lock(self, tap):
        """A plan from before a narrowing links nothing it now excludes, and
        says which link the narrowing took."""
        store.install(_wf(tap))
        (_agent_dir("windsurf") / "reviewer").unlink()
        plan = store.sync_plan()
        entry = lockfile.get_workflow("reviewer")
        entry["only_agents"] = ["claude-code"]
        lockfile.set_workflow("reviewer", entry)
        assert [a for a in store.sync_apply(plan) if "skill copy" in a] == [
            "unlinked workflow reviewer's skill copy from antigravity, which "
            "the workflow's --agent scope leaves out"]
        assert not os.path.lexists(_agent_dir("windsurf") / "reviewer")
        assert not os.path.lexists(_agent_dir("antigravity") / "reviewer")
