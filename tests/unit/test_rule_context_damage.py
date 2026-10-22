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

from boost_cli.commands import quality, safety
from boost_cli.core import integrity, lockfile, paths, store, util
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
        assert "vd modified" in _flat(capsys.readouterr())
        assert quality.cmd_doctor([]) == 1
        assert ("rule vd's block in %s cannot be read: the file is not "
                "UTF-8 — save it as UTF-8, then run `boost doctor` again"
                % paths.tilde(md)) in _flat(capsys.readouterr())
        assert md.read_bytes() == raw

    def test_the_duplicate_scan_skips_it(self, tap):
        self._installed_then_latin1(tap, "dup")
        assert store.duplicate_rule_blocks() == []

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


