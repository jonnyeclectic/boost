# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What `claude_settings.save` keeps, and what it refuses, on a user's file.

* a read-only settings.json, or a symlink into a directory that is not there,
  crashed `hooks add` at exit 70 with a bare OSError — and left a history
  snapshot behind for a change that never happened;
* a UTF-8 byte-order mark read as corrupt JSON, so `hooks add` replaced a
  valid file with a hooks-only one;
* a CRLF file came back LF, so an add + remove round trip was a whole-file
  diff.
"""
from __future__ import annotations

import os
import sys

import pytest

from boost_cli.core import claude_settings as cs
from boost_cli.core import hookhost, jsonstate
from boost_cli.errors import BoostError

BOM = b"\xef\xbb\xbf"

needs_posix_perms = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="chmod does not refuse writes on Windows or as root")


def _history():
    d = cs._history_dir()
    return sorted(f.name for f in d.glob("*.json")) if d.is_dir() else []


class TestRefusedWrites:
    @needs_posix_perms
    def test_a_read_only_file_is_refused_by_name_and_left_alone(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(b'{\n  "model": "opus"\n}\n')
        p.chmod(0o444)
        try:
            with pytest.raises(BoostError) as ei:
                cs.add_hook("global", "SessionStart", "ro", "echo hi")
            assert str(ei.value) == (
                "could not save ~/.claude/settings.json (it is read-only)")
            assert ei.value.hint == (
                "chmod u+w ~/.claude/settings.json, then re-run")
            assert p.read_bytes() == b'{\n  "model": "opus"\n}\n'
            assert _history() == []
        finally:
            p.chmod(0o644)

    def test_a_dangling_symlink_is_refused_and_nothing_is_created(
            self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.symlink_to("../dotfiles/missing/settings.json")
        with pytest.raises(BoostError) as ei:
            cs.add_hook("global", "Stop", "ln", "echo a")
        assert "~/.claude/settings.json is a symlink to " in str(ei.value)
        assert "dotfiles/missing/settings.json" in str(ei.value)
        assert str(ei.value).endswith(", whose directory does not exist")
        assert ei.value.hint is not None
        assert ei.value.hint.startswith("create ")
        assert ei.value.hint.endswith(", or remove the link, then re-run")
        assert not (sandbox / "dotfiles").exists()
        assert p.is_symlink()
        assert _history() == []

    def test_a_symlink_is_written_through_and_stays_a_link(self, sandbox):
        real = sandbox / "dotfiles" / "settings.json"
        real.parent.mkdir()
        real.write_bytes(b'{\n  "model": "opus"\n}\n')
        real.chmod(0o640)
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.symlink_to(real)
        cs.add_hook("global", "Stop", "ln", "echo a")
        assert p.is_symlink()
        assert jsonstate.read_object(real)[0]["model"] == "opus"
        assert cs.has_hook("global", "Stop", "ln")
        if sys.platform != "win32":
            assert real.stat().st_mode & 0o777 == 0o640

    @needs_posix_perms
    def test_a_failed_write_removes_its_snapshot(self, sandbox, monkeypatch):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(b'{\n  "model": "opus"\n}\n')

        def refuse(path, text, base=None):
            raise PermissionError(13, "Permission denied", str(path))

        monkeypatch.setattr(cs.util, "write_user_file", refuse)
        with pytest.raises(BoostError) as ei:
            cs.add_hook("global", "Stop", "x", "echo a")
        assert str(ei.value).startswith(
            "could not save ~/.claude/settings.json (Permission denied)")
        assert _history() == []
        assert p.read_bytes() == b'{\n  "model": "opus"\n}\n'

    @needs_posix_perms
    def test_an_unwritable_history_dir_is_named(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(b'{\n  "model": "opus"\n}\n')
        state = cs._history_dir().parent
        state.mkdir(parents=True)
        state.chmod(0o555)
        try:
            with pytest.raises(BoostError) as ei:
                cs.add_hook("global", "Stop", "x", "echo a")
            assert str(ei.value).startswith(
                "could not save ~/.boost/state/claude-settings-history")
        finally:
            state.chmod(0o755)
        assert p.read_bytes() == b'{\n  "model": "opus"\n}\n'


class TestByteOrderMark:
    @pytest.mark.parametrize("host,key", [
        (hookhost.CLAUDE, "permissions"), (hookhost.GEMINI, "theme")])
    def test_add_keeps_every_key_and_the_mark(self, sandbox, host, key):
        p = cs.settings_path("global", host=host)
        p.parent.mkdir(parents=True)
        p.write_bytes(BOM + b'{\n  "model": "opus",\n  "%s": "dark"\n}\n'
                      % key.encode())
        cs.add_hook("global", hookhost.translate(host, "SessionStart") or "",
                    "bom", "echo hi", host=host)
        raw = p.read_bytes()
        assert raw.startswith(BOM)
        assert raw.count(BOM) == 1
        data, err = jsonstate.read_object(p)
        assert err is None
        assert data is not None
        assert data["model"] == "opus"
        assert data[key] == "dark"
        assert "hooks" in data

    def test_an_unchanged_bom_file_is_not_rewritten(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(BOM + b'{\n  "a": 1\n}\n')
        assert cs.save("global", {"a": 1}) is None
        assert _history() == []

    def test_a_file_without_a_mark_does_not_gain_one(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(b'{\n  "a": 1\n}\n')
        cs.save("global", {"a": 2})
        assert p.read_bytes() == b'{\n  "a": 2\n}\n'


class TestLineEndings:
    def test_add_remove_round_trip_is_byte_identical_for_crlf(self, sandbox):
        orig = b'{\r\n  "model": "x"\r\n}\r\n'
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(orig)
        cs.add_hook("global", "Stop", "e", "echo a")
        assert b"\r\n" in p.read_bytes()
        assert b"\n" not in p.read_bytes().replace(b"\r\n", b"")
        assert cs.remove_hook_by_name("global", "e") == 1
        assert p.read_bytes() == orig

    def test_round_trip_keeps_bom_and_crlf_together(self, sandbox):
        orig = BOM + b'{\r\n  "model": "x"\r\n}\r\n'
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(orig)
        cs.add_hook("global", "Stop", "e", "echo a")
        assert cs.remove_hook_by_name("global", "e") == 1
        assert p.read_bytes() == orig

    def test_a_new_file_is_lf(self, sandbox):
        cs.add_hook("global", "Stop", "e", "echo a")
        assert b"\r" not in cs.settings_path("global").read_bytes()


class TestRemovePrunesOnlyWhatItEmptied:
    def test_an_event_list_with_a_foreign_hook_is_kept(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text('{"hooks": {"Stop": [{"hooks": [{"type": "command", '
                     '"command": "mine"}]}]}}', encoding="utf-8")
        cs.add_hook("global", "Stop", "e", "echo a")
        assert cs.remove_hook("global", "Stop", "e") == 1
        data = jsonstate.read_object(p)[0]
        assert data == {"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "mine"}]}]}}

    def test_another_event_keeps_the_hooks_object(self, sandbox):
        cs.add_hook("global", "Stop", "e", "echo a")
        cs.add_hook("global", "SessionStart", "f", "echo b")
        assert cs.remove_hook("global", "Stop", "e") == 1
        data = jsonstate.read_object(cs.settings_path("global"))[0]
        assert list(data["hooks"]) == ["SessionStart"]
        assert cs.remove_hook("global", "SessionStart", "f") == 1
        data = jsonstate.read_object(cs.settings_path("global"))[0]
        assert data == {}
