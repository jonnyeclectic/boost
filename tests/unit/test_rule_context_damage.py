# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a context file boost cannot read as its own is left alone.

Three shapes the managed-block code read wrongly. A ``CLAUDE.md`` block the
user edited was stripped by uninstall with no warning, though an edited
``.cursor/rules`` file was kept. A context file holding one byte that is not
UTF-8 crashed install, uninstall, doctor and verify with exit 70. And a block
whose start marker was deleted read as "missing": heal appended a second copy
under the remnant, and uninstall reported success with the old text live.
"""
from __future__ import annotations

import itertools
import shutil
from pathlib import Path

import pytest

from boost_cli.commands import pkg, quality, safety
from boost_cli.core import integrity, lockfile, paths, rules, store, util
from boost_cli.errors import BoostError, NotUTF8Error

BODY = "---\nname: %s\n---\n\nAlways %s.\n"
_SEQ = itertools.count()
LATIN1 = b"# Notes\n\nCaf\xe9 latin-1 text.\n"


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    from boost_cli.core import catalog, registry
    src = tmp_path / ("rule-damage-%d" % next(_SEQ))
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


def _claude_md() -> Path:
    return paths.home() / ".claude" / "CLAUDE.md"


def _flat(captured) -> str:
    return " ".join((captured.out + captured.err).split())


class TestEditedContextBlockIsKept:
    def test_an_edited_block_survives_uninstall_and_is_named(self, tap):
        md = _claude_md()
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("# My notes\n\nKeep this.\n", encoding="utf-8")
        store.install(_rule(tap, "ed"))
        edited = md.read_text(encoding="utf-8").replace("Always test first.",
                                                        "EDITED")
        md.write_text(edited, encoding="utf-8")
        res = store.uninstall("ed")
        assert res["kept"] == [str(md)]
        assert "claude-code" not in res["unlinked"]
        assert "cursor" in res["unlinked"]
        assert md.read_text(encoding="utf-8") == edited
        assert lockfile.get_rule("ed") is None

    def test_an_edited_second_copy_is_kept_too(self, tap):
        store.install(_rule(tap, "two"))
        md = _claude_md()
        text = md.read_text(encoding="utf-8")
        start, end = rules.markers("two")
        doubled = text + "\n" + start + "\nMINE\n" + end + "\n"
        md.write_text(doubled, encoding="utf-8")
        res = store.uninstall("two")
        assert res["kept"] == [str(md)]
        assert md.read_text(encoding="utf-8") == doubled

    def test_an_unedited_block_is_stripped_and_nothing_kept(self, tap):
        md = _claude_md()
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("mine\n", encoding="utf-8")
        store.install(_rule(tap, "plain"))
        res = store.uninstall("plain")
        assert "kept" not in res
        assert "claude-code" in res["unlinked"]
        assert md.read_text(encoding="utf-8") == "mine\n"

    def test_a_row_with_no_digest_is_stripped_as_before(self, tap):
        md = _claude_md()
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("mine\n", encoding="utf-8")
        store.install(_rule(tap, "old"))
        row = lockfile.get_rule("old")
        assert row is not None
        for m in row["materializations"]:
            m.pop("sha256", None)
        lockfile.set_entry("rule", "old", row)
        md.write_text(md.read_text(encoding="utf-8").replace(
            "Always test first.", "EDITED"), encoding="utf-8")
        res = store.uninstall("old")
        assert "kept" not in res
        assert md.read_text(encoding="utf-8") == "mine\n"

    def test_the_cli_names_the_kept_context_file(self, tap, capsys):
        store.install(_rule(tap, "cli"))
        md = _claude_md()
        md.write_text(md.read_text(encoding="utf-8").replace(
            "Always test first.", "EDITED"), encoding="utf-8")
        capsys.readouterr()
        assert pkg.cmd_uninstall(["cli"]) == 0
        assert ("left %s in place: it was edited since boost wrote it"
                % paths.tilde(md)) in _flat(capsys.readouterr())
        assert "EDITED" in md.read_text(encoding="utf-8")


class TestBlockBodies:
    def test_every_clean_block_is_read_like_the_first(self):
        text = rules.merge_block("", "r", "A")
        start, end = rules.markers("r")
        text += "x\r\n" + start + "\r\n\nB\r\n" + end + "\n"
        assert rules.block_bodies(text, "r") == ["A", "B"]

    def test_no_block_is_no_bodies(self):
        assert rules.block_bodies("notes\n", "r") == []


class TestNotUTF8:
    def test_read_user_text_names_the_file_and_byte(self, sandbox, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_bytes(LATIN1)
        with pytest.raises(NotUTF8Error) as ei:
            util.read_user_text(p)
        assert issubclass(NotUTF8Error, BoostError)  # so rc 1, not 70
        assert ei.value.path == p
        assert ei.value.message == (
            "%s is not UTF-8 (byte 0xe9 at offset 12), so boost cannot edit "
            "it without changing your bytes" % p)
        assert ei.value.hint == ("save the file as UTF-8, then run the "
                                 "command again")
        assert ei.value.wrap is True

    def test_install_refuses_before_any_write(self, tap):
        md = _claude_md()
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_bytes(LATIN1)
        with pytest.raises(NotUTF8Error):
            store.install(_rule(tap, "lat"))
        assert md.read_bytes() == LATIN1
        assert lockfile.get_rule("lat") is None
        assert not (paths.home() / ".cursor" / "rules" / "lat.mdc").exists()

    def test_cli_install_exits_1_naming_the_file(self, tap, capsys):
        md = _claude_md()
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_bytes(LATIN1)
        _rule(tap, "lat2")
        from boost_cli.core import catalog
        catalog.rebuild_tap(tap)
        capsys.readouterr()
        from boost_cli import cli
        assert cli.main(["install", "lat2"]) == 1
        assert "is not UTF-8 (byte 0xe9 at offset 12)" in _flat(
            capsys.readouterr())
        assert md.read_bytes() == LATIN1

    def _installed_then_latin1(self, tap, name):
        store.install(_rule(tap, name))
        md = _claude_md()
        raw = md.read_bytes() + b"Caf\xe9\n"
        md.write_bytes(raw)
        return md, raw

    def test_uninstall_refuses_and_keeps_the_row(self, tap):
        md, raw = self._installed_then_latin1(tap, "un")
        with pytest.raises(NotUTF8Error) as ei:
            store.uninstall("un")
        assert ei.value.path == md
        assert md.read_bytes() == raw
        assert lockfile.get_rule("un") is not None
        assert (paths.home() / ".cursor" / "rules" / "un.mdc").exists()

    def test_verify_reads_modified_and_doctor_names_the_file(self, tap, capsys):
        md, raw = self._installed_then_latin1(tap, "vd")
        entry = lockfile.get_rule("vd")
        assert entry is not None
        assert (integrity.materialized_status("vd", entry, "rule")
                == integrity.STATUS_MODIFIED)
        assert integrity.locally_edited("rule", "vd", entry) is True
        capsys.readouterr()
        assert safety.cmd_verify(["vd"]) == 1
        verified = _flat(capsys.readouterr())
        assert ("vd modified rule · %s is not UTF-8 — save it as UTF-8"
                % paths.tilde(md)) in verified
        assert "discard local edits" not in verified
        assert quality.cmd_doctor([]) == 1
        assert ("rule vd's block in %s cannot be read: the file is not "
                "UTF-8 — save it as UTF-8, then run `boost doctor` again"
                % paths.tilde(md)) in _flat(capsys.readouterr())
        assert md.read_bytes() == raw

    def test_the_duplicate_scan_skips_it(self, tap):
        md, _ = self._installed_then_latin1(tap, "dup")
        assert store.duplicate_rule_blocks() == []
        assert store.unreadable_context_files() == [("dup", str(md))]

    def test_a_readable_file_is_not_unreadable(self, tap):
        store.install(_rule(tap, "fine"))
        assert store.unreadable_context_files() == []

    def test_verify_json_lists_the_file(self, tap, capsys):
        import json
        md, _ = self._installed_then_latin1(tap, "vj")
        capsys.readouterr()
        assert safety.cmd_verify(["vj", "--json"]) == 1
        row = json.loads(capsys.readouterr().out)["skills"][0]
        assert row["unreadable"] == [paths.tilde(md)]
        assert row["status"] == integrity.STATUS_MODIFIED

    def test_note_prior_skips_an_unreadable_file(self, sandbox, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_bytes(LATIN1)
        undo: list = []
        store._note_prior(undo, p, user_file=True)
        assert undo == []

    def test_undo_leaves_an_unreadable_file(self, sandbox, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_bytes(LATIN1)
        store._undo_writes([(p, "before\n", True)])
        assert p.read_bytes() == LATIN1


class TestOrphanEnd:
    START, END = rules.markers("r")
    CLEAN = START + "\nB\n" + END + "\n"
    ORPHAN = "Mine\n\n# r\n\nold text\n" + END + "\n"

    def test_an_end_with_no_start_is_orphaned(self):
        assert rules.orphan_end(self.ORPHAN, "r")

    def test_an_orphan_end_before_a_clean_block(self):
        assert rules.orphan_end(self.ORPHAN + self.CLEAN, "r")

    def test_an_orphan_end_after_a_clean_block(self):
        assert rules.orphan_end(self.CLEAN + "old\n" + self.END + "\n", "r")

    @pytest.mark.parametrize("text", [
        "notes\n", CLEAN, CLEAN + CLEAN, CLEAN + "x\n" + CLEAN,
        START + "\nA\n" + START + "\nB\n" + END,   # a doubled start, not this
        CLEAN + "<!-- boost:rule:other end -->\n",
    ])
    def test_clean_and_other_shapes_are_not(self, text):
        assert not rules.orphan_end(text, "r")

    def test_require_well_formed_refuses_it_naming_the_file(self):
        with pytest.raises(BoostError) as ei:
            rules.require_well_formed(self.ORPHAN, "r", Path("/x/CLAUDE.md"))
        assert ei.value.message == (
            "rule r's managed block in %s has an end marker with no start "
            "marker above it, so boost cannot tell where its text begins and "
            "yours ends" % "/x/CLAUDE.md")
        assert ei.value.hint == (
            "restore `<!-- boost:rule:r start -->` above the rule's text (or "
            "delete the rule's text and `<!-- boost:rule:r end -->`), then "
            "run the command again")
        assert ei.value.wrap is True

    def test_the_file_is_named_the_way_doctor_names_it(self):
        md = paths.home() / ".claude" / "CLAUDE.md"
        for text in (self.ORPHAN, self.START + "\nx\n"):
            with pytest.raises(BoostError) as ei:
                rules.require_well_formed(text, "r", md)
            assert " in ~/.claude/CLAUDE.md " in ei.value.message
            assert str(md) not in ei.value.message

    def test_merge_refuses_rather_than_append_a_second_copy(self):
        with pytest.raises(BoostError):
            rules.merge_block(self.ORPHAN, "r", "NEWER")

    def test_a_damaged_start_keeps_its_own_message(self):
        with pytest.raises(BoostError) as ei:
            rules.require_well_formed(self.END + "\n" + self.START + "\nx\n",
                                      "r")
        assert "has no matching end marker" in ei.value.message

    def _installed_then_unstarted(self, tap, name):
        md = _claude_md()
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("Mine\n", encoding="utf-8")
        store.install(_rule(tap, name))
        from boost_cli.core import catalog
        catalog.rebuild_tap(tap)  # heal re-reads the rule from its tap
        start, _end = rules.markers(name)
        damaged = md.read_text(encoding="utf-8").replace(start + "\n", "")
        md.write_text(damaged, encoding="utf-8")
        return md, damaged

    def test_uninstall_refuses_and_keeps_the_row(self, tap):
        md, damaged = self._installed_then_unstarted(tap, "oe")
        with pytest.raises(BoostError) as ei:
            store.uninstall("oe")
        assert "has an end marker with no start marker" in ei.value.message
        assert md.read_text(encoding="utf-8") == damaged
        assert lockfile.get_rule("oe") is not None

    def test_doctor_names_it_instead_of_missing(self, tap, capsys):
        md, _ = self._installed_then_unstarted(tap, "od")
        capsys.readouterr()
        assert quality.cmd_doctor([]) == 1
        out = _flat(capsys.readouterr())
        assert ("rule od's block in %s has an end marker and no start marker "
                "— restore its `<!-- boost:rule:od start -->` line above the "
                "rule's text, or delete that text and the end marker, then "
                "run `boost reinstall od`" % paths.tilde(md)) in out
        assert "rule od missing its claude-code materialization" not in out

    def test_heal_does_not_append_a_second_copy(self, tap, capsys):
        md, damaged = self._installed_then_unstarted(tap, "oh")
        capsys.readouterr()
        quality.cmd_heal([])
        out = _flat(capsys.readouterr())
        assert md.read_text(encoding="utf-8") == damaged
        assert "re-materialized rule oh" not in out
        assert ("rule oh was not re-materialized: rule oh's managed block in "
                "%s has an end marker with no start marker above it"
                % paths.tilde(md)) in out
        assert lockfile.get_rule("oh") is not None

    def test_quarantine_refuses_rather_than_claim_it_withheld(self, tap):
        md, damaged = self._installed_then_unstarted(tap, "oq")
        entry = lockfile.get_rule("oq")
        with pytest.raises(BoostError) as ei:
            store.quarantine_materialized("rule", "oq", entry)
        assert "has an end marker with no start marker" in ei.value.message
        assert md.read_text(encoding="utf-8") == damaged
        row = lockfile.get_rule("oq")
        assert not row.get("quarantined")
        assert "quarantine_stash" not in row
