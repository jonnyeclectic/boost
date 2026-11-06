# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: a lock row whose ``only_agents`` names an unknown agent.

doctor used to send the user to `boost sync --prune`, which unlinked the
skill from every agent, and then report it present "with agent links".
"""
from __future__ import annotations

import os

from boost_cli.core import agents, lockfile, store


def _flat(text):
    return " ".join(text.split())


def _links(name):
    return sorted(a for a, d in agents.linking_agents().items()
                  if os.path.islink(d / name))


WANT = ("skill brainstorming's declared agent scope names claud-code, an "
        "agent boost does not know — it is ignored; `boost heal` drops it "
        "from the lock")


class TestUnknownScopeAgent:
    def test_doctor_names_it_prune_keeps_links_heal_converges(
            self, boost, installed):
        before = _links(installed)
        assert before
        lockfile.update_skill(installed, lambda row: row.update(
            only_agents=["claud-code"]))
        flat = _flat(boost("doctor", expect=1).out)
        assert WANT in flat
        assert "outside its declared scope" not in flat
        assert "sync --prune" not in flat

        boost("sync", "--prune")
        assert _links(installed) == before

        r = boost("heal", "--dry-run")
        assert ("would drop claud-code from skill brainstorming's declared "
                "agent scope") in r.out
        assert lockfile.get_skill(installed)["only_agents"] == ["claud-code"]
        r = boost("heal")
        assert ("dropped claud-code from skill brainstorming's declared agent "
                "scope") in r.out
        assert sorted(lockfile.get_skill(installed)["only_agents"]) == before
        assert _links(installed) == before
        assert "nothing to heal" in boost("heal").out
        flat = _flat(boost("doctor").out)
        assert WANT not in flat
        assert "1 skill present in store with agent links" in flat

    def test_a_rules_unknown_scope_is_named(self, boost, installed):
        lockfile.set_rule("strict-types", {
            "version": "1", "tap": "t", "only_agents": ["nope"],
            "materializations": []})
        assert store.unknown_scope_rows() == [
            ("rule", "strict-types", ["nope"])]
        flat = _flat(boost("doctor", expect=1).out)
        assert ("rule strict-types's declared agent scope names nope, an "
                "agent boost does not know") in flat

    def test_a_skill_with_no_link_is_not_counted_as_linked(
            self, boost, installed):
        for d in agents.linking_agents().values():
            if os.path.islink(d / installed):
                os.unlink(d / installed)
        flat = _flat(boost("doctor", expect=1).out)
        assert "not linked for claude-code — run `boost sync`" in flat
        assert "with agent links" not in flat

    def test_a_scope_reaching_no_enabled_agent_is_counted_unlinked(
            self, boost, installed):
        # Narrowed to a disabled agent: nothing is owed a link, so no issue,
        # but the line must not call the skill one "with agent links".
        from boost_cli.core import config
        cfg = config.load()
        cfg["agents"]["cursor"]["enabled"] = False
        config.save(cfg)
        lockfile.update_skill(installed, lambda row: row.update(
            only_agents=["cursor"]))
        for d in agents.linking_agents().values():
            if os.path.islink(d / installed):
                os.unlink(d / installed)
        flat = _flat(boost("doctor", expect=None).out)
        assert "1 skill present in store, 0 with agent links" in flat
