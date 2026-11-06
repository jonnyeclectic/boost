# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: an agent's links and copies follow it being enabled or disabled.

Three gaps, each reproduced against the fixture tap:

* the user lock's ``agents`` (what list, info and ``list --json`` print) kept
  the agents linked at install time after ``sync`` linked a newly enabled one,
  and dropped an agent whose link a reinstall left in place while it was
  disabled;
* ``install SKILL --agent X`` with X disabled exited 0 with no link and
  ``agents: []``, where a rule, a workflow and a ``--local`` skill refuse;
* a ``--local`` skill never reached an agent enabled after it was installed:
  doctor, ``sync`` and ``heal`` all called it intact.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import agents, lockfile, projectlock, store
from boost_cli.errors import BoostError


def _enable(boost, agent, on):
    boost("config", "set", "agents.%s.enabled" % agent, "true" if on else "false")


class TestLockAgentsFollowLinks:
    def test_sync_records_the_link_it_makes(self, boost, tapped, sandbox):
        _enable(boost, "cursor", False)
        boost("install", "brainstorming")
        assert lockfile.get_skill("brainstorming")["agents"] == [
            "claude-code", "windsurf", "antigravity"]
        _enable(boost, "cursor", True)
        res = boost("sync")
        assert "linked brainstorming → cursor" in res.out
        assert lockfile.get_skill("brainstorming")["agents"] == [
            "claude-code", "windsurf", "cursor", "antigravity"]
        listed = json.loads(boost("list", "--json").out)
        assert listed["skills"]["brainstorming"]["agents"] == [
            "claude-code", "windsurf", "cursor", "antigravity"]

    def test_sync_leaves_untouched_rows_alone(self, boost, tapped, sandbox):
        boost("install", "brainstorming")
        boost("install", "commit-messages")
        _enable(boost, "cursor", False)
        lockfile.update_skill("commit-messages",
                              lambda r: r.update(agents=["sentinel"]))
        res = boost("sync")
        assert "linked" not in res.out
        assert lockfile.get_skill("commit-messages")["agents"] == ["sentinel"]

    def test_reinstall_keeps_a_disabled_agents_live_link(self, boost, tapped,
                                                         sandbox):
        boost("install", "brainstorming")
        _enable(boost, "claude-code", False)
        boost("reinstall", "brainstorming")
        assert (sandbox / ".claude" / "skills" / "brainstorming").is_symlink()
        assert lockfile.get_skill("brainstorming")["agents"] == [
            "claude-code", "windsurf", "cursor", "antigravity"]

    def test_linked_agents_counts_disabled_agents(self, boost, installed,
                                                  sandbox):
        _enable(boost, "cursor", False)
        assert store.linked_agents("brainstorming") == [
            "claude-code", "windsurf", "cursor", "antigravity"]
        (sandbox / ".cursor" / "skills" / "brainstorming").unlink()
        assert store.linked_agents("brainstorming") == [
            "claude-code", "windsurf", "antigravity"]


class TestDisabledAgentRefused:
    HINT = "enable one with `boost config set agents.<name>.enabled true`"
    ERR = "no agent left to install skill commit-messages into: --agent cursor"

    def test_install_refuses_and_writes_nothing(self, boost, tapped, sandbox):
        _enable(boost, "cursor", False)
        res = boost("install", "commit-messages", "--agent", "cursor", expect=1)
        assert self.ERR in res.err
        assert self.HINT in res.err
        assert lockfile.get_skill("commit-messages") is None
        assert not (sandbox / ".agents" / "skills" / "commit-messages").exists()

    def test_dry_run_refuses_in_the_same_words(self, boost, tapped):
        _enable(boost, "cursor", False)
        res = boost("install", "commit-messages", "--agent", "cursor",
                    "--dry-run", expect=1)
        assert self.ERR in res.err
        assert self.HINT in res.err
        assert "would install" not in res.out

    def test_one_reachable_agent_is_enough(self, boost, tapped):
        _enable(boost, "cursor", False)
        boost("install", "commit-messages", "--agent", "cursor", "--agent", "claude-code")
        assert lockfile.get_skill("commit-messages")["agents"] == ["claude-code"]

    def test_native_store_agent_counts_as_reached(self, boost, tapped):
        boost("install", "commit-messages", "--agent", "gemini")
        assert lockfile.get_skill("commit-messages")["agents"] == []

    def test_helper(self, sandbox):
        store.refuse_unreachable_skill(None, "x")
        store.refuse_unreachable_skill([], "x")
        store.refuse_unreachable_skill(["cursor"], "x")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(agents, "linking_agents", lambda: {})
            mp.setattr(agents, "native_store_agents", lambda: {})
            with pytest.raises(BoostError) as exc:
                store.refuse_unreachable_skill(["cursor"], "x")
        assert exc.value.message == (
            "no agent left to install skill x into: --agent cursor")


@pytest.fixture()
def repo(sandbox, tmp_path, monkeypatch):
    d = tmp_path / "als-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


class TestProjectSkillReachesNewAgent:
    def _install(self, boost, *extra):
        _enable(boost, "cursor", False)
        boost("install", "tdd-workflow", "--scope", "project", *extra)
        _enable(boost, "cursor", True)

    def test_install_records_declared_scope(self, boost, tapped, repo):
        boost("install", "tdd-workflow", "--scope", "project")
        assert projectlock.get_skill(repo, "tdd-workflow")["only_agents"] is None
        boost("install", "tdd-workflow", "--scope", "project", "--force",
              "--agent", "claude-code")
        assert projectlock.get_skill(repo, "tdd-workflow")["only_agents"] == [
            "claude-code"]

    def test_doctor_names_it_and_sync_copies_it(self, boost, tapped, repo):
        self._install(boost)
        entry = projectlock.get_skill(repo, "tdd-workflow")
        assert store.unmaterialized_project_agents(
            repo, "tdd-workflow", entry) == ["cursor"]
        assert store.project_sync_plan()["missing"] == [("tdd-workflow", "cursor")]
        doc = boost("doctor", expect=None)
        assert ("project skill tdd-workflow was never written for cursor "
                "— run `boost sync`") in doc.out
        res = boost("sync")
        # From the intact .claude copy, which is the locked content.
        assert ("re-materialized tdd-workflow from its "
                ".claude/skills/tdd-workflow copy") in res.out
        assert (repo / ".cursor" / "skills" / "tdd-workflow" / "SKILL.md").is_file()
        entry = projectlock.get_skill(repo, "tdd-workflow")
        before = [m["agent"] for m in entry["materializations"]
                  if m["agent"] != "cursor"]
        assert entry["agents"] == [*before, "cursor"]
        cursor_rows = [m for m in entry["materializations"]
                       if m["agent"] == "cursor"]
        assert cursor_rows == [
            {"agent": "cursor", "path": ".cursor/skills/tdd-workflow"}]
        assert store.project_sync_plan()["missing"] == []
        assert "never written" not in boost("doctor", expect=None).out

    def test_heal_copies_it_too(self, boost, tapped, repo):
        self._install(boost)
        boost("heal", expect=None)
        assert (repo / ".cursor" / "skills" / "tdd-workflow").is_dir()

    def test_a_narrowing_is_not_widened(self, boost, tapped, repo):
        self._install(boost, "--agent", "claude-code")
        assert store.project_sync_plan()["missing"] == []

    def test_legacy_row_without_only_agents_is_not_widened(self, boost, tapped,
                                                           repo):
        self._install(boost)

        def legacy(lock):
            lock["skills"]["tdd-workflow"].pop("only_agents")
        projectlock.mutate(repo, legacy)
        assert store.project_sync_plan()["missing"] == []

    def test_existing_dir_is_not_claimed(self, boost, tapped, repo):
        self._install(boost)
        theirs = repo / ".cursor" / "skills" / "tdd-workflow"
        theirs.mkdir(parents=True)
        assert store.project_sync_plan()["missing"] == []

    def test_apply_rechecks_a_dir_that_appeared_after_the_plan(
            self, boost, tapped, repo):
        # `_copy_skill` swaps its copy in over whatever is there, so the
        # apply-time check is the only thing between a stale plan and a
        # hand-written skill that landed after it was made.
        self._install(boost)
        plan = store.project_sync_plan()
        assert plan["missing"] == [("tdd-workflow", "cursor")]
        theirs = repo / ".cursor" / "skills" / "tdd-workflow"
        theirs.mkdir(parents=True)
        (theirs / "notes.md").write_text("mine\n", encoding="utf-8")
        store.project_sync_apply(plan)
        assert sorted(p.name for p in theirs.iterdir()) == ["notes.md"]
        entry = projectlock.get_skill(repo, "tdd-workflow")
        assert "cursor" not in entry["agents"]
        assert all(m["agent"] != "cursor" for m in entry["materializations"])

    def test_quarantined_and_rowless_entries_are_skipped(self, repo):
        assert store.unmaterialized_project_agents(
            repo, "x", {"only_agents": None, "materializations": []}) == []
        assert store.unmaterialized_project_agents(
            repo, "x", {"only_agents": None, "quarantined": True,
                        "materializations": [{"agent": "claude-code"}]}) == []
        assert "cursor" in store.unmaterialized_project_agents(
            repo, "x", {"only_agents": None,
                        "materializations": [{"agent": "claude-code"}]})
        assert store.unmaterialized_project_agents(
            repo, "x", {"only_agents": ["windsurf"],
                        "materializations": [{"agent": "claude-code"}]}) == [
            "windsurf"]
