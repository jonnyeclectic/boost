# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: settings.json writes keep what boost does not own.

Three ways a ``hooks add`` used to damage a file it only meant to add one key
to: a commented Gemini settings.json read as corrupt and was replaced by a
hooks-only file; a snapshot of a 0600 file landed world-readable; and every
write escaped non-ASCII text and re-indented the file to two spaces.
"""
from __future__ import annotations

import json
import os
import stat
import sys

import pytest

from boost_cli.core import claude_settings as cs
from boost_cli.core import hookhost as hh
from boost_cli.core import jsonstate, paths
from boost_cli.errors import BoostError

POSIX = pytest.mark.skipif(sys.platform == "win32",
                           reason="POSIX permission bits")

COMMENTED = (
    '{\n'
    '  // my theme\n'
    '  "ui": {"theme": "GitHub"},\n'
    '  /* servers */\n'
    '  "mcpServers": {"pg": {"command": "pg-mcp"}},\n'
    '  "url": "http://x//y/*z*/"\n'
    '}\n')


def _hist():
    return paths.state_dir() / "claude-settings-history"


# ------------------------------------------------------------ strip_comments

class TestStripComments:
    def test_line_comment_blanked_to_spaces(self):
        assert jsonstate.strip_comments('{"a": 1} // hi\n') == (
            '{"a": 1}      \n')

    def test_block_comment_keeps_line_breaks(self):
        assert jsonstate.strip_comments('{/* a\nb */"a": 1}') == (
            '{    \n    "a": 1}')

    def test_comment_markers_inside_strings_are_kept(self):
        text = '{"u": "http://x//y/*z*/", "q": "say \\"//\\" ok"}'
        assert jsonstate.strip_comments(text) == text

    def test_unterminated_block_runs_to_end(self):
        assert jsonstate.strip_comments('{} /* open\nx') == '{} ' + ' ' * 7 + '\n '

    def test_backslash_at_end_inside_string(self):
        assert jsonstate.strip_comments('"a\\') == '"a\\'

    def test_carriage_return_in_block_comment_is_kept(self):
        assert jsonstate.strip_comments('/*\r\n*/{}') == '  \r\n  {}'

    def test_line_comment_at_end_of_file(self):
        assert jsonstate.strip_comments('{}//') == '{}  '

    def test_lone_slash_is_not_a_comment(self):
        assert jsonstate.strip_comments('{} /') == '{} /'

    def test_read_object_jsonc_parses_comments(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(COMMENTED, encoding="utf-8")
        data, err = jsonstate.read_object(p, jsonc=True)
        assert err is None
        assert data == {"ui": {"theme": "GitHub"},
                        "mcpServers": {"pg": {"command": "pg-mcp"}},
                        "url": "http://x//y/*z*/"}

    def test_read_object_default_still_rejects_comments(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(COMMENTED, encoding="utf-8")
        data, err = jsonstate.read_object(p)
        assert data is None
        assert err.startswith("%s: invalid JSON (" % p)


# ------------------------------------------------------------ JSONC on Gemini

class TestJsoncHost:
    def test_only_gemini_reads_comments(self):
        assert hh.jsonc(hh.GEMINI) is True
        assert hh.jsonc(hh.CLAUDE) is False
        assert hh.jsonc(hh.CODEX) is False

    def _write(self, text):
        p = cs.settings_path("global", host=hh.GEMINI)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_commented_gemini_settings_load_without_warning(
            self, sandbox, capsys):
        self._write(COMMENTED)
        data = cs.load("global", host=hh.GEMINI)
        assert data["mcpServers"] == {"pg": {"command": "pg-mcp"}}
        assert capsys.readouterr().err == ""

    def test_add_hook_refuses_and_leaves_commented_file_untouched(
            self, sandbox):
        p = self._write(COMMENTED)
        with pytest.raises(BoostError) as ei:
            cs.add_hook("global", "SessionStart", "greet", "echo hi",
                        host=hh.GEMINI)
        assert str(ei.value) == (
            "%s has comments, which Gemini CLI reads but boost cannot write "
            "back — rewriting it would drop them, so it was left unchanged"
            % p)
        assert ei.value.hint == (
            "remove the comments from %s and run this again, or make the "
            "change by hand" % p)
        assert p.read_text(encoding="utf-8") == COMMENTED
        assert not _hist().exists()

    def test_uncommented_gemini_file_still_written(self, sandbox):
        p = self._write('{"mcpServers": {"pg": {"command": "pg-mcp"}}}\n')
        cs.add_hook("global", "SessionStart", "greet", "echo hi",
                    host=hh.GEMINI)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["mcpServers"] == {"pg": {"command": "pg-mcp"}}
        assert list(data["hooks"]) == ["SessionStart"]

    def test_commented_claude_file_is_still_corrupt_for_claude(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text(COMMENTED, encoding="utf-8")
        assert cs.load("global") == {}
        cs.add_hook("global", "SessionStart", "greet", "echo hi")
        assert list(json.loads(p.read_text(encoding="utf-8"))) == ["hooks"]


# ------------------------------------------------------------ snapshot mode

@POSIX
class TestSnapshotMode:
    def test_snapshot_keeps_a_private_source_private(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text('{"env": {"ANTHROPIC_API_KEY": "sk-ant-secret"}}',
                     encoding="utf-8")
        os.chmod(p, 0o600)
        old = os.umask(0o022)
        try:
            dest = cs.add_hook("global", "SessionStart", "g2", "echo hi")
        finally:
            os.umask(old)
        assert dest is not None
        assert stat.S_IMODE(dest.stat().st_mode) == 0o600
        assert stat.S_IMODE(_hist().stat().st_mode) == 0o700
        assert dest.read_bytes() == (
            b'{"env": {"ANTHROPIC_API_KEY": "sk-ant-secret"}}')

    def test_snapshot_copies_the_source_mode_exactly(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text('{"v": 1}', encoding="utf-8")
        os.chmod(p, 0o640)
        dest = cs.save("global", {"v": 2})
        assert stat.S_IMODE(dest.stat().st_mode) == 0o640

    def test_existing_history_dir_is_tightened(self, sandbox):
        _hist().mkdir(parents=True)
        os.chmod(_hist(), 0o755)  # noqa: S103 - the wide mode under test
        cs.save("global", {"v": 1})
        cs.save("global", {"v": 2})
        assert stat.S_IMODE(_hist().stat().st_mode) == 0o700

    def test_snapshot_is_byte_exact_for_non_utf8(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(b'{"a": "\xff"}')
        dest = cs.save("global", {"v": 2})
        assert dest.read_bytes() == b'{"a": "\xff"}'


# ------------------------------------------------------------ text fidelity

class TestTextFidelity:
    def test_non_ascii_written_verbatim(self, sandbox):
        cs.save("global", {"g": "¡hola, café ☕"})
        assert cs.settings_path("global").read_text(encoding="utf-8") == (
            '{\n  "g": "¡hola, café ☕"\n}\n')

    def test_four_space_indent_preserved(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text('{\n    "a": 1\n}\n', encoding="utf-8")
        cs.save("global", {"a": 1, "b": 2})
        assert p.read_text(encoding="utf-8") == (
            '{\n    "a": 1,\n    "b": 2\n}\n')

    def test_tab_indent_preserved(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_bytes(b'{\r\n\t"a": 1\r\n}\r\n')
        cs.save("global", {"a": [1]})
        assert p.read_text(encoding="utf-8") == '{\n\t"a": [\n\t\t1\n\t]\n}\n'

    def test_compact_file_falls_back_to_two(self, sandbox):
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text('{"a": 1}', encoding="utf-8")
        cs.save("global", {"a": 2})
        assert p.read_text(encoding="utf-8") == '{\n  "a": 2\n}\n'

    def test_add_then_remove_round_trip_keeps_text(self, sandbox):
        orig = ('{\n    "env": {\n        "GREETING": "¡hola, café ☕"\n    },\n'
                '    "permissions": {\n        "allow": [\n'
                '            "Bash(ls)"\n        ]\n    }\n}\n')
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text(orig, encoding="utf-8")
        cs.add_hook("global", "SessionStart", "greet", "echo hi")
        assert cs.remove_hook_by_name("global", "greet") == 1
        assert p.read_text(encoding="utf-8") == orig

    def test_lone_surrogate_falls_back_to_escapes(self, sandbox):
        # A raw surrogate cannot be encoded: writing it would truncate the
        # file and then raise, emptying the user's settings.
        p = cs.settings_path("global")
        p.parent.mkdir(parents=True)
        p.write_text('{\n  "env": {"X": "\\ud83d", "Y": "café"}\n}\n',
                     encoding="utf-8")
        cs.add_hook("global", "SessionStart", "greet", "echo hi")
        text = p.read_text(encoding="utf-8")
        assert '"X": "\\ud83d"' in text
        assert '"Y": "caf\\u00e9"' in text
        data = json.loads(text)
        assert data["env"] == {"X": "\ud83d", "Y": "café"}
        assert "SessionStart" in data["hooks"]
