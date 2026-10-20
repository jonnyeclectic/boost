# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a workflow's agent files are boost's only while boost wrote them.

Four ways the per-agent command files went wrong, each pinned here: a user's
own command at the target path was overwritten and later deleted; a source
that moved from ``commands/`` to ``agents/`` left the old files orphaned; an
edited agent file was deleted on uninstall; and Gemini's TOML kept Claude's
``$ARGUMENTS`` literal instead of ``{{args}}``.
"""
from __future__ import annotations

import hashlib
import itertools
import shutil
from pathlib import Path

import pytest

from boost_cli.commands import pkg
from boost_cli.core import lockfile, paths, store, workflows

CMD = "---\ndescription: tap cmd\n---\ntap body\n"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_SEQ = itertools.count()


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    from boost_cli.core import catalog, registry
    src = tmp_path / ("wf-files-%d" % next(_SEQ))   # a tap name per test
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _wf(tap, name, rel, body=CMD):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(body, encoding="utf-8")
    return {"name": name, "kind": "workflow", "tap": tap.name,
            "version": "1.0.0", "rel_dir": str(src.parent.relative_to(tap.path)),
            "skill_md": rel, "description": "", "curated": False, "meta": {}}


def _rows(name):
    return lockfile.get_workflow(name)["materializations"]


def _claude(slot, name):
    # paths.home(), not Path.home(): on Windows the latter reads USERPROFILE
    # and ignores the sandbox's $HOME, so these files landed in the runner's
    # real profile while boost wrote into the sandbox.
    return paths.home() / ".claude" / slot / ("%s.md" % name)


class TestForeignTarget:
    def test_a_users_own_command_survives_install_and_uninstall(self, tap):
        mine = _claude("commands", "mine")
        mine.parent.mkdir(parents=True)
        mine.write_text("MY OWN PRECIOUS COMMAND\n", encoding="utf-8")
        res = store.install(_wf(tap, "mine", "commands/mine.md"),
                            as_skill=False)
        assert mine.read_text(encoding="utf-8") == "MY OWN PRECIOUS COMMAND\n"
        assert res.foreign == [str(mine)]
        assert "claude-code" not in res.linked
        assert res.linked   # the other agents were still written
        rows = _rows("mine")
        assert str(mine) not in [m["path"] for m in rows]
        assert "claude-code" not in [m["agent"] for m in rows]
        others = [Path(m["path"]) for m in rows]
        assert all(p.is_file() for p in others)
        conflicts, refused = pkg._skipped_agent_lines(res)
        assert conflicts == []
        assert any("exists and is not managed by boost" in line
                   and "mine.md" in line for line in refused)
        # Even a forced reinstall (what update does) leaves it alone.
        store.install(_wf(tap, "mine", "commands/mine.md"), force=True,
                      as_skill=False)
        assert mine.read_text(encoding="utf-8") == "MY OWN PRECIOUS COMMAND\n"
        store.uninstall("mine")
        assert mine.read_text(encoding="utf-8") == "MY OWN PRECIOUS COMMAND\n"
        assert not any(p.exists() for p in others)

    def test_a_file_already_holding_our_text_is_adopted(self, tap):
        mine = _claude("commands", "same")
        mine.parent.mkdir(parents=True)
        mine.write_text(CMD, encoding="utf-8")
        res = store.install(_wf(tap, "same", "commands/same.md"),
                            as_skill=False)
        assert res.foreign == []
        assert "claude-code" in res.linked
        assert {"agent": "claude-code", "slot": "commands", "path": str(mine),
                "sha256": _sha(CMD)} in _rows("same")

    def test_predicate(self, sandbox, tmp_path):
        p = tmp_path / "x.md"
        assert store._foreign_target(p, "T", set()) is False   # absent
        p.write_text("T", encoding="utf-8")
        assert store._foreign_target(p, "T", set()) is False   # identical
        assert store._foreign_target(p, "U", set()) is True
        assert store._foreign_target(p, "U", {str(p)}) is False   # ours
        d = tmp_path / "d.md"
        d.mkdir()
        assert store._foreign_target(d, "U", set()) is False   # a dir: elsewhere

    def test_our_own_recorded_file_is_rewritten(self, tap):
        store.install(_wf(tap, "again", "commands/again.md"), as_skill=False)
        path = _claude("commands", "again")
        store.install(_wf(tap, "again", "commands/again.md", body="v2\n"),
                      force=True, as_skill=False)
        assert path.read_text(encoding="utf-8") == "v2\n"


class TestSlotMove:
    def test_unedited_old_files_go_and_only_new_rows_remain(self, tap):
        store.install(_wf(tap, "mover", "commands/mover.md"), as_skill=False)
        old = [Path(m["path"]) for m in _rows("mover")]
        assert old and all(p.is_file() for p in old)
        res = store.install(_wf(tap, "mover", "agents/mover.md"), force=True,
                            as_skill=False)
        assert not any(p.exists() for p in old)
        rows = _rows("mover")
        assert {m["slot"] for m in rows} == {"agents"}
        assert sorted(m["agent"] for m in rows) == sorted(res.linked)
        assert all(Path(m["path"]).is_file() for m in rows)

    def test_an_edited_old_file_stays_recorded_and_uninstall_keeps_it(
            self, tap):
        store.install(_wf(tap, "mv2", "commands/mv2.md"), as_skill=False)
        edited = _claude("commands", "mv2")
        before = {m["path"]: m for m in _rows("mv2")}
        edited.write_text("MY EDIT\n", encoding="utf-8")
        store.install(_wf(tap, "mv2", "agents/mv2.md"), force=True,
                      as_skill=False)
        rows = _rows("mv2")
        assert before[str(edited)] in rows   # carried with its original sha
        assert [m for m in rows if m["slot"] == "commands"] \
            == [before[str(edited)]]
        assert edited.read_text(encoding="utf-8") == "MY EDIT\n"
        others = [p for p in before if p != str(edited)]
        assert not any(Path(p).exists() for p in others)
        info = store.uninstall("mv2")
        assert info["kept"] == [str(edited)]
        assert edited.read_text(encoding="utf-8") == "MY EDIT\n"

    def test_a_refused_new_write_keeps_the_old_command(self, tap,
                                                       monkeypatch):
        store.install(_wf(tap, "mv3", "commands/mv3.md"), as_skill=False)
        old = _claude("commands", "mv3")
        new = _claude("agents", "mv3")
        new.parent.mkdir(parents=True)
        new.write_text("THEIRS\n", encoding="utf-8")
        store.install(_wf(tap, "mv3", "agents/mv3.md"), force=True,
                      as_skill=False)
        assert old.is_file()   # claude-code was not written, so not retired
        assert str(old) in [m["path"] for m in _rows("mv3")]
        assert new.read_text(encoding="utf-8") == "THEIRS\n"

    def test_retire_moved_skips_copies_and_absent_files(self, sandbox,
                                                        tmp_path):
        gone = tmp_path / "gone.md"
        copy = {"agent": None, "slot": "skill", "path": str(tmp_path / "c"),
                "sha256": "x"}
        nosha = tmp_path / "nosha.md"
        nosha.write_text("anything", encoding="utf-8")
        existing = {"materializations": [
            copy,
            {"agent": "a", "slot": "commands", "path": str(gone),
             "sha256": "x"},
            {"agent": "a", "slot": "commands", "path": str(nosha)},
        ]}
        assert store._retire_moved("n", existing, ["a"], []) == []
        assert not nosha.exists()   # no sha recorded: removed as before
        assert store._retire_moved("n", None, ["a"], []) == []


class TestUninstallEdited:
    def test_an_edited_agent_file_is_kept_and_named(self, tap):
        store.install(_wf(tap, "tricky", "commands/tricky.md"), as_skill=False)
        rows = _rows("tricky")
        edited = _claude("commands", "tricky")
        edited.write_text(CMD + "MY EDIT\n", encoding="utf-8")
        info = store.uninstall("tricky")
        assert info["kept"] == [str(edited)]
        assert edited.read_text(encoding="utf-8") == CMD + "MY EDIT\n"
        assert "claude-code" not in info["unlinked"]
        others = [m for m in rows if m["path"] != str(edited)]
        assert others
        assert sorted(info["unlinked"]) == sorted(m["agent"] for m in others)
        assert not any(Path(m["path"]).exists() for m in others)
        assert lockfile.get_workflow("tricky") is None

    def test_unedited_files_are_all_removed(self, tap):
        store.install(_wf(tap, "plain", "commands/plain.md"), as_skill=False)
        rows = _rows("plain")
        info = store.uninstall("plain")
        assert "kept" not in info
        assert not any(Path(m["path"]).exists() for m in rows)


class TestGeminiArgs:
    def test_arguments_become_args(self):
        out = workflows.render_gemini_command(
            "x", "---\ndescription: d\n---\nRun $ARGUMENTS now\n")
        assert out == 'description = "d"\nprompt = "Run {{args}} now"\n'

    def test_every_occurrence_and_only_the_placeholder(self):
        out = workflows.render_gemini_command(
            "x", "$ARGUMENTS and $ARGUMENTS, $ARGUMENTSX $ARGUMENTS[0] $1\n")
        assert out == ('prompt = "{{args}} and {{args}}, $ARGUMENTSX '
                       '$ARGUMENTS[0] $1"\n')

    def test_a_body_without_it_is_unchanged(self):
        assert workflows.render_gemini_command("x", "Plain body\n") \
            == 'prompt = "Plain body"\n'

    def test_a_list_description_is_dropped_not_repr(self):
        out = workflows.render_gemini_command(
            "x", "---\ndescription:\n  - one\n  - two\n---\nB\n")
        assert out == 'prompt = "B"\n'
        out = workflows.render_gemini_command(
            "x", "---\ndescription: '  padded  '\n---\nB\n")
        assert out == 'description = "padded"\nprompt = "B"\n'

    def test_install_writes_args_into_the_toml(self, tap):
        store.install(_wf(tap, "argy", "commands/argy.md",
                          body="Run with $ARGUMENTS here.\n"), as_skill=False)
        toml = [Path(m["path"]) for m in _rows("argy")
                if m["path"].endswith(".toml")]
        if not toml:
            pytest.skip("gemini is not an enabled workflow agent here")
        assert toml[0].read_text(encoding="utf-8") \
            == 'prompt = "Run with {{args}} here."\n'


def _foreign_install(tap, name):
    """The review's repro: the user's own command at claude-code's path, then
    a workflow of that name installed through the CLI. Returns the path."""
    from boost_cli.core import catalog
    mine = _claude("commands", name)
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text("MY OWN %s\n" % name, encoding="utf-8")
    _wf(tap, name, "commands/%s.md" % name)
    catalog.rebuild_tap(tap)
    assert pkg.cmd_install([name, "--no-as-skill"]) == 0
    return mine


def _agents(name):
    return sorted(m["agent"] for m in _rows(name) if m.get("agent"))


class TestForeignStaysInScope:
    """A foreign path is recorded apart, so the agent stays in scope and the
    user's file is still never boost's."""

    def test_recorded_apart_and_never_owned(self, tap):
        mine = _foreign_install(tap, "fa")
        entry = lockfile.get_workflow("fa")
        assert entry["foreign"] == [{"agent": "claude-code",
                                     "slot": "commands", "path": str(mine)}]
        assert str(mine) not in [m["path"] for m in _rows("fa")]
        # Undeclared, so every agent stays in scope, claude-code included.
        assert store.preserved_agent_scope(None, entry) is None
        # With the file still there, no command writes over it or calls it a
        # fault, and the record survives each re-install.
        assert store.sync_plan()["missing_materializations"] == []
        assert pkg.cmd_reinstall(["fa"]) == 0
        assert pkg.cmd_sync([]) == 0
        assert pkg.cmd_install(["fa", "--force"]) == 0
        assert mine.read_text(encoding="utf-8") == "MY OWN fa\n"
        assert "claude-code" not in _agents("fa")
        assert lockfile.get_workflow("fa")["foreign"][0]["path"] == str(mine)
        # Quarantine and uninstall never touch it either.
        store.quarantine_materialized("workflow", "fa",
                                      lockfile.get_workflow("fa"))
        assert mine.read_text(encoding="utf-8") == "MY OWN fa\n"
        store.release_materialized("workflow", "fa",
                                   lockfile.get_workflow("fa"))
        res = store.uninstall("fa")
        assert mine.read_text(encoding="utf-8") == "MY OWN fa\n"
        assert "claude-code" not in res.get("removed", [])

    @pytest.mark.parametrize("how", ["sync", "reinstall", "force"])
    def test_moved_aside_the_next_run_writes_it(self, tap, how):
        name = "fb-%s" % how
        mine = _foreign_install(tap, name)
        others = _agents(name)
        mine.rename(mine.with_suffix(".bak"))
        assert store.sync_plan()["missing_materializations"] == [
            ("workflow", name)]
        argv = {"sync": (pkg.cmd_sync, []),
                "reinstall": (pkg.cmd_reinstall, [name]),
                "force": (pkg.cmd_install, [name, "--force"])}[how]
        assert argv[0](argv[1]) == 0
        assert mine.read_text(encoding="utf-8") == CMD
        assert _agents(name) == sorted([*others, "claude-code"])
        assert {"agent": "claude-code", "slot": "commands", "path": str(mine),
                "sha256": _sha(CMD)} in _rows(name)
        assert "foreign" not in lockfile.get_workflow(name)
        assert store.sync_plan()["missing_materializations"] == []

    def test_doctor_names_a_freed_path(self, tap, capsys):
        from boost_cli.commands import quality
        mine = _foreign_install(tap, "fc")
        capsys.readouterr()
        quality.cmd_doctor([])
        assert "fc was not written for claude-code" not in capsys.readouterr().out
        mine.unlink()
        quality.cmd_doctor([])
        out = capsys.readouterr().out
        assert "workflow fc was not written for claude-code" in out
        assert "`boost sync`" in out

    def test_the_hint_names_sync_not_install(self, tap):
        res = store.InstallResult(name="x", dest=Path("."), kind="workflow")
        res.foreign = [str(_claude("commands", "x"))]
        _c, refused = pkg._skipped_agent_lines(res)
        assert refused == [
            "not written: ~/.claude/commands/x.md exists and is not managed "
            "by boost — left alone; move it aside, then `boost sync` writes it"]

    def test_a_narrowed_run_keeps_another_agents_record(self, tap):
        mine = _foreign_install(tap, "fd")
        store.install(_wf(tap, "fd", "commands/fd.md"), force=True,
                      only_agents=["cursor"], as_skill=False)
        assert lockfile.get_workflow("fd")["foreign"][0]["path"] == str(mine)

    def test_scope_is_the_declaration_not_the_rows(self):
        # Foreign or written, a row is not a narrowing: replaying them kept
        # an agent enabled later out of every re-install.
        rows = {"materializations": [{"agent": "cursor", "path": "/y"}],
                "foreign": [{"agent": "claude-code", "path": "/x"}],
                "only_agents": None}
        assert store.preserved_agent_scope(None, rows) is None
        rows["only_agents"] = ["claude-code"]
        assert store.preserved_agent_scope(None, rows) == ["claude-code"]

    def test_a_legacy_entry_keeps_foreign_in_scope(self):
        # Written before the declaration was recorded: the rows, foreign
        # included, are the only record of a narrowing, so they still replay.
        rows = {"materializations": [],
                "foreign": [{"agent": "claude-code", "path": "/x"}]}
        assert store.preserved_agent_scope(None, rows) is None
        rows["materializations"] = [{"agent": "cursor", "path": "/y"}]
        assert store.preserved_agent_scope(None, rows) == ["cursor",
                                                           "claude-code"]

    def test_foreign_rows_and_freed(self, sandbox, tmp_path):
        held = tmp_path / "held.md"
        held.write_text("x", encoding="utf-8")
        gone = tmp_path / "gone.md"
        dangling = tmp_path / "link.md"
        entry = {"foreign": [{"agent": "claude-code", "path": str(held)},
                             {"agent": "claude-code", "path": str(gone)},
                             {"agent": "", "path": str(gone)},
                             {"agent": "claude-code"}, "junk"]}
        assert store.foreign_rows(entry) == entry["foreign"][:2]
        assert store.foreign_rows(None) == []
        assert store._freed_foreign(entry) == [entry["foreign"][1]]
        if hasattr(dangling, "symlink_to"):
            try:
                dangling.symlink_to(tmp_path / "nowhere")
            except OSError:
                return
            entry["foreign"] = [{"agent": "claude-code", "path": str(dangling)}]
            assert store._freed_foreign(entry) == []


def test_freed_foreign_skips_an_agent_boost_does_not_write(sandbox, tmp_path):
    gone = str(tmp_path / "gone.md")
    entry = {"foreign": [{"agent": "no-such-agent", "path": gone}]}
    assert store.foreign_rows(entry) == entry["foreign"]
    assert store._freed_foreign(entry) == []


def test_portable_contracts_foreign_paths(sandbox):
    home = paths.home()
    lock = {"skills": {}, "rules": {}, "workflows": {"w": {
        "materializations": [{"agent": "cursor",
                              "path": str(home / ".cursor" / "w.md")}],
        "foreign": [{"agent": "claude-code",
                     "path": str(home / ".claude" / "commands" / "w.md")},
                    "junk"]}}}
    out = lockfile.portable(lock)["workflows"]["w"]
    assert out["foreign"][0]["path"] == "~/.claude/commands/w.md"
    assert out["foreign"][1] == "junk"
    assert out["materializations"][0]["path"] == "~/.cursor/w.md"
    assert lock["workflows"]["w"]["foreign"][0]["path"].startswith(str(home))
