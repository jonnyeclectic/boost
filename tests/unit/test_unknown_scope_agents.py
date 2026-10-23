# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A lock ``only_agents`` naming an agent this boost does not know.

Measured before this fix: ``only_agents = ['claud-code']`` read as "linked
for no agent", doctor prescribed `boost sync --prune`, and that unlinked the
skill from every agent — then doctor called it present "with agent links".
"""
from __future__ import annotations

from boost_cli.core import agents, lockfile, store


def _skill(**extra):
    entry = {"version": "1", "tap": "t",
             "agents": ["claude-code", "cursor"]}
    entry.update(extra)
    return entry


class TestUnknownScopeAgents:
    def test_names_only_the_unknown_once_in_order(self, sandbox):
        e = _skill(only_agents=["nope", "claude-code", "zz", "nope"])
        assert store.unknown_scope_agents(e) == ["nope", "zz"]

    def test_a_disabled_agent_is_still_known(self, sandbox):
        assert "windsurf" in agents.known_agents()
        assert store.unknown_scope_agents(_skill(only_agents=["windsurf"])) == []

    def test_no_or_odd_scope_names_none(self, sandbox):
        assert store.unknown_scope_agents(_skill()) == []
        assert store.unknown_scope_agents(_skill(only_agents=None)) == []
        assert store.unknown_scope_agents(_skill(only_agents="nope")) == []


class TestEffectiveScope:
    def test_a_known_scope_is_itself(self, sandbox):
        assert store.effective_scope(_skill(only_agents=["cursor"])) == ["cursor"]
        assert store.effective_scope(_skill()) is None
        assert store.effective_scope(_skill(only_agents=[])) == []

    def test_unknown_names_are_dropped(self, sandbox):
        e = _skill(only_agents=["claud-code", "cursor"])
        assert store.effective_scope(e) == ["cursor"]

    def test_only_unknown_falls_back_to_what_it_reaches(self, sandbox):
        e = _skill(only_agents=["claud-code"],
                   agents=["claude-code", "ghost", "cursor", "cursor"])
        assert store.effective_scope(e) == ["claude-code", "cursor"]

    def test_a_rules_rows_are_what_it_reaches(self, sandbox):
        e = {"only_agents": ["nope"], "agents": ["cursor"],
             "materializations": [
                 {"agent": "claude-code"}, {"agent": None, "slot": "skill"},
                 {"agent": "gemini"}]}
        assert store.effective_scope(e) == ["claude-code", "gemini"]

    def test_reaching_nothing_is_no_narrowing(self, sandbox):
        assert store.effective_scope(
            _skill(only_agents=["nope"], agents=[])) is None

    def test_scoped_agents_no_longer_reads_it_as_no_agent(self, sandbox):
        enabled = agents.linking_agents()
        got = store.scoped_agents(_skill(only_agents=["claud-code"]), enabled)
        assert sorted(got) == ["claude-code", "cursor"]
        assert store.scoped_agents(_skill(only_agents=["claud-code"],
                                          agents=[]), enabled) == enabled


class TestDropUnknown:
    def test_rows_lines_and_the_rewrite_converge(self, sandbox):
        lockfile.set_skill("b", _skill(only_agents=["claud-code"]))
        lockfile.set_skill("a", _skill(only_agents=["cursor", "x", "y"]))
        lockfile.set_rule("r", {"only_agents": ["nope"], "materializations": [
            {"agent": "claude-code"}]})
        lockfile.set_skill("ok", _skill(only_agents=["cursor"]))
        assert store.unknown_scope_rows() == [
            ("skill", "a", ["x", "y"]), ("skill", "b", ["claud-code"]),
            ("rule", "r", ["nope"])]
        assert store.unknown_scope_line("skill", "a", ["x", "y"]) == (
            "skill a's declared agent scope names x, y, agents boost does not "
            "know — it is ignored; `boost heal` drops them from the lock")
        assert store.unknown_scope_line("rule", "r", ["nope"]) == (
            "rule r's declared agent scope names nope, an agent boost does "
            "not know — it is ignored; `boost heal` drops it from the lock")
        assert store.drop_unknown_scope_agents(dry=True) == [
            "would drop x, y from skill a's declared agent scope",
            "would drop claud-code from skill b's declared agent scope",
            "would drop nope from rule r's declared agent scope"]
        assert lockfile.get_skill("a")["only_agents"] == ["cursor", "x", "y"]
        assert store.drop_unknown_scope_agents() == [
            "dropped x, y from skill a's declared agent scope",
            "dropped claud-code from skill b's declared agent scope",
            "dropped nope from rule r's declared agent scope"]
        assert lockfile.get_skill("a")["only_agents"] == ["cursor"]
        assert lockfile.get_skill("b")["only_agents"] == ["claude-code", "cursor"]
        assert lockfile.get_rule("r")["only_agents"] == ["claude-code"]
        assert lockfile.get_skill("ok")["only_agents"] == ["cursor"]
        assert store.unknown_scope_rows() == []
        assert store.drop_unknown_scope_agents() == []
