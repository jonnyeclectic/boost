# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the bookkeeping behind a workflow's copy in the skill store.

The functional suite drives the commands; these pin the predicates the
commands are built from, row for row, so a mutant in any one of them fails
here rather than somewhere three commands away.
"""
from __future__ import annotations

import hashlib

import pytest

from boost_cli.core import config, lockfile, paths, store

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
            "~/.agents/skills/reviewer"]
        assert not _store_copy().exists()
        assert store.backfill_skill_copies() == [
            "wrote workflow reviewer's skill copy to ~/.agents/skills/reviewer"]
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
