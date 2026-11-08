# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: an agent in a shell is told how to read and use what it found.

Measured on the fixture tap with both streams piped: `boost search commit`
ended at ``2 matches · ranked by full-content BM25`` and the [rag] hint, and
`boost install brainstorming` at ``next: boost info brainstorming``. The MCP
replies say where the text is (boost_read; "to use it now: ... read
~/.agents/skills/<name>/SKILL.md"). The shell is the only route on Cursor and
Windsurf, and on any host where boost's MCP server is not registered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from boost_cli.core import output as out
from boost_cli.core import paths

NOTE = ("  read one: boost cat fixture-tap:commit-messages · install: boost "
        "install fixture-tap:commit-messages (--local for this repository "
        "only)")


class TestSearchNextStep:
    def test_the_name_is_tap_qualified(self):
        assert out.search_next_step("docx", "anthropics/skills") == (
            "read one: boost cat anthropics/skills:docx · install: boost "
            "install anthropics/skills:docx (--local for this repository "
            "only)")

    def test_no_tap_gives_the_bare_name(self):
        assert out.search_next_step("docx") == (
            "read one: boost cat docx · install: boost install docx "
            "(--local for this repository only)")

    def test_a_taps_own_text_is_made_plain(self):
        line = out.search_next_step("x\x1b[2Jy", "o/r\x1b[31m")
        assert "\x1b" not in line
        assert line.startswith("read one: boost cat o/r")


class TestInstallUseNow:
    def test_a_skill_points_at_its_text(self):
        assert out.install_use_now(
            "skill", "x", "~/.agents/skills/x/SKILL.md") == (
            "use it now: read ~/.agents/skills/x/SKILL.md — the files it "
            "names by relative path sit beside it")

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_other_kinds_point_at_boost_cat(self, kind):
        assert out.install_use_now(kind, "x", "unused") == (
            "use it now: boost cat x")

    def test_the_name_is_made_plain(self):
        assert "\x1b" not in out.install_use_now("rule", "x\x1b[2J", "")


class TestThePipedSearch:
    def test_names_the_top_hit_on_stderr(self, boost, tapped):
        r = boost("search", "commit")
        assert NOTE in r.err.splitlines()
        # stdout stays rows and chrome: a grep for the tap matches rows only.
        assert "read one" not in r.out

    def test_the_commands_it_names_run(self, boost, tapped):
        assert "name: commit-messages" in boost(
            "cat", "fixture-tap:commit-messages").out
        boost("install", "fixture-tap:commit-messages")
        assert (paths.store_dir() / "commit-messages" / "SKILL.md").is_file()

    def test_a_terminal_on_stderr_gets_no_note(self, boost, tapped,
                                               monkeypatch):
        # `boost search x | grep y` in a terminal: a person, not an agent.
        monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
        r = boost("search", "commit")
        assert "commit-messages" in r.out
        assert "read one" not in r.out + r.err

    def test_no_match_no_note(self, boost, tapped):
        r = boost("search", "zzqxv-nothing-like-it", expect=None)
        assert "read one" not in r.out + r.err

    def test_json_gets_no_note(self, boost, tapped):
        r = boost("search", "commit", "--json")
        assert json.loads(r.out)
        assert "read one" not in r.err


class TestTheInstallTail:
    def test_a_skill_names_its_skill_md(self, boost, tapped):
        r = boost("install", "brainstorming")
        md = paths.store_dir() / "brainstorming" / "SKILL.md"
        assert md.is_file()
        assert ("\n  use it now: read %s — the files it names by relative "
                "path sit beside it\n  next: boost info brainstorming\n"
                % paths.tilde(md)) in r.out

    def test_a_local_skill_names_the_repository_copy(self, boost, tapped,
                                                     tmp_path, monkeypatch):
        repo = tmp_path / "proj"
        repo.mkdir()
        monkeypatch.chdir(repo)
        r = boost("install", "brainstorming", "--local")
        line = next(ln for ln in r.out.splitlines()
                    if ln.startswith("  use it now: read "))
        md = line.removeprefix("  use it now: read ").split(" — ")[0]
        assert md.endswith("/brainstorming/SKILL.md")
        copy = Path(md).expanduser()
        assert copy.is_file()
        assert copy.resolve().is_relative_to(repo.resolve())

    def test_a_rule_points_at_boost_cat(self, boost, sandbox):
        r = boost("install", "boost-first")
        assert ("\n  use it now: boost cat boost-first\n"
                "  next: boost info boost-first\n") in r.out

    def test_several_items_get_no_tail(self, boost, tapped):
        r = boost("install", "brainstorming", "commit-messages")
        assert "use it now" not in r.out
        assert "next: boost info" not in r.out
