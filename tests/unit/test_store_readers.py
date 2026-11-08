# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every surface that names a skill's agents names the store readers.

Gemini CLI and Codex read ``~/.agents/skills`` directly, so boost links
nothing for them, and `boost_install` says so: "available without linking
(reads ~/.agents/skills directly): gemini, codex". Measured on the same
skill right after, `boost_info` said ``agents: antigravity, claude-code,
cursor, windsurf``, and so did `boost info` and the AGENTS column of
`boost list`. A Codex or Gemini session asking whether a skill reached it
was told no. Only user scope: a ``--local`` copy is written into each
agent's project dir and was already named.
"""
from __future__ import annotations

import pytest

from boost_cli.commands import configuration, info
from boost_cli.core import builtin, config, integrity

SKILL = builtin.BUILTIN_SKILLS[0]
NATIVE = "codex, gemini (read the store directly)"


def _user_row(**extra):
    return {"kind": "skill", "agents": ["claude-code", "cursor"], **extra}


class TestStoreReaderNames:
    def test_a_user_scope_skill(self, sandbox):
        assert integrity.store_reader_names("skill", _user_row()) == [
            "codex", "gemini"]

    def test_a_row_without_a_kind_is_a_skill(self, sandbox):
        row = {"agents": ["claude-code"]}
        assert integrity.store_reader_names(None, row) == ["codex", "gemini"]

    def test_a_project_scope_row(self, sandbox):
        assert integrity.store_reader_names(
            "skill", _user_row(scope="project")) == []

    def test_a_project_lock_row_marked_only_by_its_copies(self, sandbox):
        row = _user_row(materializations=[{"agent": "gemini", "path": "x"}])
        assert integrity.store_reader_names("skill", row) == []

    @pytest.mark.parametrize("kind", ["rule", "workflow"])
    def test_other_kinds(self, sandbox, kind):
        assert integrity.store_reader_names(kind, {"kind": kind}) == []

    def test_a_row_kind_other_than_skill(self, sandbox):
        assert integrity.store_reader_names(None, {"kind": "rule"}) == []

    @pytest.mark.parametrize("entry", [None, {}])
    def test_no_entry(self, sandbox, entry):
        assert integrity.store_reader_names("skill", entry) == []

    def test_a_quarantined_skill_has_no_copy_to_read(self, sandbox):
        assert integrity.store_reader_names(
            "skill", _user_row(quarantined=True)) == []

    def test_a_named_skill_needs_its_store_dir(self, sandbox):
        from boost_cli.core import paths
        assert integrity.store_reader_names("skill", _user_row(), "x") == []
        (paths.store_dir() / "x").mkdir(parents=True)
        assert integrity.store_reader_names("skill", _user_row(), "x") == [
            "codex", "gemini"]

    def test_a_disabled_reader_is_not_named(self, sandbox):
        cfg = config.load()
        cfg["agents"]["gemini"]["enabled"] = False
        config.save(cfg)
        assert integrity.store_reader_names("skill", _user_row()) == ["codex"]


class TestReachLine:
    def test_written_then_readers(self, sandbox):
        assert integrity.reach_line("skill", _user_row()) == (
            "claude-code, cursor; " + NATIVE)

    def test_a_rule_names_only_what_was_written(self, sandbox):
        assert integrity.reach_line("rule", {"kind": "rule"}) == "none"

    def test_the_caller_spells_none(self, sandbox):
        assert integrity.reach_line("rule", {"kind": "rule"},
                                    none="(none)") == "(none)"

    def test_the_name_reaches_the_reader_check(self, sandbox):
        # No store dir for `gone`, so no reader can see it.
        assert integrity.reach_line("skill", _user_row(), "gone") == \
            "claude-code, cursor"


class TestTheSurfacesAgreeWithBoostInstall:
    def test_boost_info_tool(self, boost):
        boost("install", SKILL)
        text, is_err = configuration._tool_info({"name": SKILL})
        assert not is_err
        agents_line = next(line for line in text.splitlines()
                           if line.startswith("agents: "))
        assert agents_line.endswith("; " + NATIVE)
        assert "claude-code" in agents_line

    def test_boost_info_cli(self, boost):
        boost("install", SKILL)
        r = boost("info", SKILL)
        assert NATIVE in " ".join(r.out.split())

    def test_boost_list_column_and_its_legend(self, boost):
        boost("install", SKILL)
        r = boost("list")
        row = next(line for line in r.out.splitlines()
                   if line.startswith(SKILL))
        assert "+codex·gemini" in row
        assert "+agents read ~/.agents/skills directly, with no link" in r.out

    def test_the_list_column_for_a_project_row_has_no_plus(self, sandbox):
        row = {"kind": "skill", "scope": "project",
               "agents": ["claude-code", "codex"],
               "materializations": [{"agent": "claude-code", "path": "a"},
                                    {"agent": "codex", "path": "b"}]}
        assert "+" not in info._materialized_agents("skill", row)

    def test_the_list_column_for_a_user_row(self, sandbox):
        assert info._materialized_agents("skill", _user_row()) == (
            "claude·cursor +codex·gemini")

    def test_the_list_column_when_nothing_is_linked(self, sandbox):
        assert info._materialized_agents(
            "skill", _user_row(agents=[])) == "+codex·gemini"

    def test_the_list_column_for_a_rule(self, sandbox):
        assert info._materialized_agents("rule", {"kind": "rule"}) == ""
