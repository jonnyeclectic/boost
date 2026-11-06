# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a rule's files are boost's only while boost wrote them.

The ownership discipline a workflow already had, applied to rules: a user's
own ``.cursor/rules/<name>.mdc`` at the target path was overwritten and then
deleted by uninstall; an edited rules-dir file was deleted on uninstall; two
rule names that one filesystem maps to one file (``alpha`` and ``ALPHA`` on a
case-insensitive disk) overwrote and then deleted each other's file; and a
context file the user had created empty was deleted on uninstall.
"""
from __future__ import annotations

import hashlib
import itertools
import shutil
import sys
from pathlib import Path

import pytest

from boost_cli.commands import pkg
from boost_cli.core import agents, lockfile, paths, rules, store
from boost_cli.errors import BoostError

BODY = "---\nname: %s\n---\n\nAlways %s.\n"
_SEQ = itertools.count()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    from boost_cli.core import catalog, registry
    src = tmp_path / ("rule-own-%d" % next(_SEQ))
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _rule(tap, name, says="test first"):
    rel = "rules/%s.mdc" % name
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(BODY % (name, says), encoding="utf-8")
    return {"name": name, "kind": "rule", "tap": tap.name, "version": "1.0.0",
            "rel_dir": "rules", "skill_md": rel, "description": "",
            "curated": False, "meta": {"name": name}}


def _target(agent, name):
    return rules.rule_target(agent, agents.materializing_agents()[agent],
                             name)[1]


def _claude_md():
    return paths.home() / ".claude" / "CLAUDE.md"


def _mine(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestForeignRulesDirFile:
    def test_a_users_own_rule_file_survives_install_and_uninstall(self, tap):
        cursor = _mine(_target("cursor", "alpha"), "MY OWN cursor rule\n")
        windsurf = _mine(_target("windsurf", "alpha"), "MY OWN windsurf rule\n")
        res = store.install(_rule(tap, "alpha"))
        assert cursor.read_text(encoding="utf-8") == "MY OWN cursor rule\n"
        assert windsurf.read_text(encoding="utf-8") == "MY OWN windsurf rule\n"
        assert sorted(res.foreign) == sorted([str(cursor), str(windsurf)])
        assert "cursor" not in res.linked
        assert "windsurf" not in res.linked
        assert "claude-code" in res.linked
        entry = lockfile.get_rule("alpha")
        assert sorted(entry["foreign"], key=lambda r: r["agent"]) == [
            {"agent": "cursor", "mode": rules.MODE_FILE, "path": str(cursor)},
            {"agent": "windsurf", "mode": rules.MODE_FILE,
             "path": str(windsurf)}]
        recorded = [m["path"] for m in entry["materializations"]]
        assert str(cursor) not in recorded
        assert str(windsurf) not in recorded
        _conflicts, refused = pkg._skipped_agent_lines(res)
        assert sum("exists and is not managed by boost" in line
                   for line in refused) == 2
        # A forced reinstall (what update does) leaves them alone too, and
        # keeps the foreign rows rather than dropping them.
        res = store.install(_rule(tap, "alpha"), force=True)
        assert sorted(res.foreign) == sorted([str(cursor), str(windsurf)])
        assert cursor.read_text(encoding="utf-8") == "MY OWN cursor rule\n"
        assert len(lockfile.get_rule("alpha")["foreign"]) == 2
        store.uninstall("alpha")
        assert cursor.read_text(encoding="utf-8") == "MY OWN cursor rule\n"
        assert windsurf.read_text(encoding="utf-8") == "MY OWN windsurf rule\n"
        assert lockfile.get_rule("alpha") is None

    def test_a_narrowed_reinstall_keeps_the_other_agents_foreign_row(self, tap):
        cursor = _mine(_target("cursor", "nar"), "mine\n")
        store.install(_rule(tap, "nar"))
        store.install(_rule(tap, "nar"), force=True, only_agents=["windsurf"])
        assert lockfile.get_rule("nar")["foreign"] == [
            {"agent": "cursor", "mode": rules.MODE_FILE, "path": str(cursor)}]

    def test_a_file_already_holding_our_text_is_adopted(self, tap):
        entry = _rule(tap, "same")
        cursor = _mine(_target("cursor", "same"), BODY % ("same", "test first"))
        res = store.install(entry)
        assert res.foreign == []
        assert "cursor" in res.linked
        assert "foreign" not in lockfile.get_rule("same")
        assert {"agent": "cursor", "mode": rules.MODE_FILE,
                "path": str(cursor),
                "sha256": _sha(BODY % ("same", "test first"))} \
            in lockfile.get_rule("same")["materializations"]

    def test_our_own_recorded_file_is_rewritten(self, tap):
        store.install(_rule(tap, "again"))
        store.install(_rule(tap, "again", says="v2"), force=True)
        assert _target("cursor", "again").read_text(encoding="utf-8") \
            == BODY % ("again", "v2")

    def test_sync_writes_it_once_the_users_file_is_gone(self, tap):
        from boost_cli.core import catalog
        cursor = _mine(_target("cursor", "freed"), "mine\n")
        entry = _rule(tap, "freed")
        catalog.rebuild_tap(tap)   # sync finds the source by its catalog row
        store.install(entry)
        assert ("rule", "freed") not in \
            store.sync_plan()["missing_materializations"]
        cursor.unlink()
        assert store._freed_foreign(lockfile.get_rule("freed"), "rule") == [
            {"agent": "cursor", "mode": rules.MODE_FILE, "path": str(cursor)}]
        assert ("rule", "freed") in \
            store.sync_plan()["missing_materializations"]
        assert pkg.cmd_sync([]) == 0
        assert cursor.read_text(encoding="utf-8") == BODY % ("freed",
                                                             "test first")
        assert "foreign" not in lockfile.get_rule("freed")
        assert store.sync_plan()["missing_materializations"] == []

    def test_doctor_names_a_freed_path(self, tap, capsys):
        from boost_cli.commands import quality
        cursor = _mine(_target("cursor", "fd"), "mine\n")
        store.install(_rule(tap, "fd"))
        capsys.readouterr()
        quality.cmd_doctor([])
        assert "fd was not written for cursor" not in capsys.readouterr().out
        cursor.unlink()
        quality.cmd_doctor([])
        out = " ".join(capsys.readouterr().out.split())
        assert ("rule fd was not written for cursor: a file boost did not "
                "write held %s, and it is gone now — run `boost sync`"
                % paths.tilde(cursor)) in out


class TestEditedRulesDirFile:
    def test_an_edited_rule_file_is_kept_on_uninstall(self, tap):
        store.install(_rule(tap, "beta"))
        cursor = _target("cursor", "beta")
        windsurf = _target("windsurf", "beta")
        edited = cursor.read_text(encoding="utf-8") + "MY IMPORTANT TWEAK\n"
        cursor.write_text(edited, encoding="utf-8")
        res = store.uninstall("beta")
        assert res["kept"] == [str(cursor)]
        assert "cursor" not in res["unlinked"]
        assert "windsurf" in res["unlinked"]
        assert cursor.read_text(encoding="utf-8") == edited
        assert not windsurf.exists()
        assert lockfile.get_rule("beta") is None

    def test_the_cli_names_the_kept_file(self, tap, capsys):
        store.install(_rule(tap, "gamma"))
        cursor = _target("cursor", "gamma")
        cursor.write_text("edited\n", encoding="utf-8")
        capsys.readouterr()
        assert pkg.cmd_uninstall(["gamma"]) == 0
        printed = capsys.readouterr()
        text = printed.out + printed.err
        assert ("left %s in place: it was edited since boost wrote it"
                % paths.tilde(cursor)) in " ".join(text.split())
        assert cursor.read_text(encoding="utf-8") == "edited\n"

    def test_an_unedited_rule_file_is_removed_and_nothing_kept(self, tap):
        store.install(_rule(tap, "delta"))
        res = store.uninstall("delta")
        assert "kept" not in res
        assert not _target("cursor", "delta").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks")
class TestSharedRulesDirFile:
    def test_a_rule_whose_file_is_another_rules_is_refused(self, tap):
        # A case-insensitive disk maps ALPHA.mdc onto alpha.mdc; a symlink
        # makes the same aliasing on any filesystem.
        store.install(_rule(tap, "alpha"))
        theirs = _target("cursor", "alpha")
        before = theirs.read_text(encoding="utf-8")
        alias = _target("cursor", "ALPHA2")
        alias.symlink_to(theirs.name)
        with pytest.raises(BoostError) as exc:
            store.install(_rule(tap, "ALPHA2", says="SHOUT"))
        assert str(exc.value) == ("cannot install rule ALPHA2: %s is rule "
                                  "alpha's file" % paths.tilde(alias))
        assert "uninstall alpha first" in exc.value.hint
        assert theirs.read_text(encoding="utf-8") == before
        assert lockfile.get_rule("ALPHA2") is None
        assert "boost:rule:ALPHA2" not in \
            _claude_md().read_text(encoding="utf-8")
        assert store.uninstall("alpha")["unlinked"]
        assert not theirs.exists()

    def test_the_rules_own_file_and_context_files_are_not_a_collision(
            self, tap):
        store.install(_rule(tap, "one"))
        store.install(_rule(tap, "two"))
        store.install(_rule(tap, "one"), force=True)
        assert set(lockfile.installed_rules()) >= {"one", "two"}

    def test_a_vanished_other_file_is_not_a_collision(self, tap):
        store.install(_rule(tap, "gone"))
        _target("cursor", "gone").unlink()
        store._refuse_shared_rule_file("other", _target("cursor", "other"))
        _mine(_target("cursor", "other"), "x\n")
        store._refuse_shared_rule_file("other", _target("cursor", "other"))


class TestCreatedContextFile:
    def _claude_row(self, name):
        return next(m for m in lockfile.get_rule(name)["materializations"]
                    if m["agent"] == "claude-code")

    def test_a_users_empty_context_file_is_kept_on_uninstall(self, tap):
        ctx = _mine(_claude_md(), "")
        store.install(_rule(tap, "alpha"))
        assert self._claude_row("alpha")["created"] is False
        store.uninstall("alpha")
        assert ctx.is_file()
        assert ctx.read_text(encoding="utf-8") == ""

    def test_a_context_file_boost_created_is_removed(self, tap):
        store.install(_rule(tap, "alpha"))
        assert self._claude_row("alpha")["created"] is True
        # A reinstall finds the file it made already there: still boost's.
        store.install(_rule(tap, "alpha"), force=True)
        assert self._claude_row("alpha")["created"] is True
        store.uninstall("alpha")
        assert not _claude_md().exists()

    def test_a_row_from_before_created_keeps_the_file(self, tap):
        store.install(_rule(tap, "old"))
        entry = lockfile.get_rule("old")
        for m in entry["materializations"]:
            m.pop("created", None)
        lockfile.set_rule("old", entry)
        store.uninstall("old")
        assert _claude_md().read_text(encoding="utf-8") == ""

    def test_a_second_rule_inherits_the_file_boost_created(self, tap):
        store.install(_rule(tap, "first"))
        store.install(_rule(tap, "second"))
        assert self._claude_row("second")["created"] is True
        store.uninstall("first")
        assert _claude_md().is_file()
        store.uninstall("second")
        assert not _claude_md().exists()

    def test_a_second_rule_in_the_users_file_does_not_inherit(self, tap):
        _mine(_claude_md(), "")
        store.install(_rule(tap, "first"))
        store.install(_rule(tap, "second"))
        assert self._claude_row("second")["created"] is False
        store.uninstall("second")
        store.uninstall("first")
        assert _claude_md().read_text(encoding="utf-8") == ""

    def test_predicate(self, sandbox, tmp_path):
        p = tmp_path / "CLAUDE.md"
        assert store._context_file_created("r", p, {}) is True
        p.write_text("", encoding="utf-8")
        assert store._context_file_created("r", p, {}) is False
        assert store._context_file_created(
            "r", p, {str(p): {"created": True}}) is True
        assert store._context_file_created(
            "r", p, {str(p): {"created": False}}) is False
        assert store._context_file_created(
            "r", p, {str(Path(tmp_path / "x")): {"created": True}}) is False
