# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A live agent link is judged by which store entry it leads to.

Three checks asked only whether a link lands in the store, and each one let a
wrong link through:

* ``~/.claude/skills/brainstorming -> ~/.agents/skills/tdd-workflow`` read as
  healthy to doctor, heal, sync, verify and drift, while Claude loaded
  tdd-workflow under brainstorming's name.
* ``~/.claude/skills/ghost -> ~/.agents/skills/tdd-workflow`` read as healthy
  to doctor, and the next heal deleted it as a stale link.
* a link outside a declared ``--agent`` scope, made by hand, was invisible to
  doctor (it read the lock's ``agents``) while sync warned about it, and heal
  answered a bare "nothing to heal" under doctor's warning about it.
"""
from __future__ import annotations

import json
import os

import pytest

from boost_cli.core import agents, catalog, lockfile, paths, registry, store


def _link(agent: str, name: str):
    return agents.linking_agents()[agent] / name


def _repoint(link, name: str) -> None:
    link.unlink()
    link.symlink_to(store.skill_store_dir(name))


@pytest.fixture()
def two(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    for n in ("brainstorming", "tdd-workflow"):
        store.install(catalog.resolve_one(n))


@pytest.fixture()
def crossed(two):
    """claude-code's brainstorming link leads to tdd-workflow's copy."""
    link = _link("claude-code", "brainstorming")
    _repoint(link, "tdd-workflow")
    return link


def _checks(boost, name: str) -> list[dict]:
    res = boost("doctor", "--json", expect=None)
    return [c for c in json.loads(res.out)["checks"] if c["name"] == name]


class TestMisdirected:
    def test_names_the_store_dir_the_link_really_leads_to(self, crossed):
        assert store.misdirected("brainstorming", crossed) == \
            paths.store_dir() / "tdd-workflow"

    def test_a_link_to_its_own_copy_is_not_misdirected(self, two):
        assert store.misdirected("brainstorming",
                                 _link("claude-code", "brainstorming")) is None

    def test_a_dangling_boost_link_is_not_misdirected(self, two):
        link = _link("claude-code", "brainstorming")
        link.unlink()
        link.symlink_to(paths.store_dir() / "gone")
        assert store.misdirected("brainstorming", link) is None

    def test_the_users_own_live_link_is_not_misdirected(self, two, tmp_path):
        checkout = tmp_path / "checkout"
        checkout.mkdir()
        link = _link("claude-code", "brainstorming")
        link.unlink()
        link.symlink_to(checkout)
        assert store.misdirected("brainstorming", link) is None

    def test_a_missing_path_is_not_misdirected(self, two):
        assert store.misdirected("brainstorming",
                                 _link("claude-code", "nothing-here")) is None

    def test_a_link_to_the_store_itself_names_the_store(self, two):
        link = _link("claude-code", "brainstorming")
        link.unlink()
        link.symlink_to(paths.store_dir())
        assert store.misdirected("brainstorming", link) == \
            paths.store_dir().resolve()

    def test_a_link_into_its_own_subdir_names_the_subdir(self, two):
        sub = store.skill_store_dir("brainstorming") / "references"
        sub.mkdir(exist_ok=True)
        link = _link("claude-code", "brainstorming")
        link.unlink()
        link.symlink_to(sub)
        assert store.misdirected("brainstorming", link) == sub.resolve()

    def test_misdirected_links_lists_only_the_wrong_agent(self, crossed):
        assert store.misdirected_links("brainstorming") == [
            ("claude-code", paths.store_dir() / "tdd-workflow")]
        assert store.misdirected_links("tdd-workflow") == []

    def test_linked_agents_does_not_count_it(self, crossed):
        linked = store.linked_agents("brainstorming")
        assert "claude-code" not in linked
        assert "cursor" in linked
        assert "claude-code" in store.linked_agents("tdd-workflow")


class TestSyncRepairsIt:
    def test_planned_as_a_missing_link(self, crossed):
        plan = store.sync_plan()
        assert plan["missing_links"] == [("brainstorming", "claude-code")]
        assert plan["stale_links"] == []

    def test_a_missing_store_copy_is_restored_not_linked(self, crossed):
        (store.skill_store_dir("brainstorming") / "SKILL.md").unlink()
        plan = store.sync_plan()
        assert plan["missing_store"] == ["brainstorming"]
        assert plan["missing_links"] == []

    def test_sync_apply_relinks_to_its_own_copy(self, crossed):
        actions = store.sync_apply(store.sync_plan())
        assert "linked brainstorming → claude-code" in actions
        assert os.path.samefile(crossed, store.skill_store_dir("brainstorming"))
        assert store.sync_plan()["missing_links"] == []

    def test_heal_relinks_and_doctor_is_then_healthy(self, crossed, boost):
        dry = boost("heal", "--dry-run")
        assert "would link brainstorming → claude-code" in dry.out
        boost("heal")
        assert store.misdirected("brainstorming", crossed) is None
        assert _checks(boost, "skill-link") == []
        boost("doctor")


class TestDoctor:
    def test_flags_the_misdirected_link_with_heal(self, crossed, boost):
        res = boost("doctor", "--json", expect=1)
        checks = [c for c in json.loads(res.out)["checks"]
                  if c["name"] == "skill-link"]
        assert checks == [{
            "name": "skill-link", "status": "issue",
            "message": "skill brainstorming linked for claude-code to "
                       "~/.agents/skills/tdd-workflow, not its own store dir "
                       "— run `boost heal`",
            "hint": None}]

    def test_text_and_json_agree(self, crossed, boost):
        text = boost("doctor", expect=1).out
        assert "skill brainstorming linked for claude-code to" in text
        assert "1 issue needs attention" in text

    def test_flags_a_live_stale_link_heal_will_remove(self, two, boost):
        ghost = _link("claude-code", "ghost")
        ghost.symlink_to(store.skill_store_dir("tdd-workflow"))
        assert _checks(boost, "stale-links") == [{
            "name": "stale-links", "status": "issue",
            "message": "1 stale link into the store in agent dirs, for no "
                       "installed skill (~/.claude/skills/ghost) — run "
                       "`boost heal`",
            "hint": None}]
        boost("doctor", expect=1)
        # Doctor's verdict is heal's plan.
        assert store.sync_plan()["stale_links"] == [str(ghost)]
        assert "would remove stale link ~/.claude/skills/ghost" in \
            boost("heal", "--dry-run").out
        boost("heal")
        assert not os.path.lexists(ghost)
        assert _checks(boost, "stale-links") == []

    def test_a_dangling_link_is_left_to_the_broken_links_check(self, two, boost):
        ghost = _link("claude-code", "ghost")
        ghost.symlink_to(paths.store_dir() / "gone")
        assert _checks(boost, "stale-links") == []
        assert [c["message"] for c in _checks(boost, "broken-links")] == [
            "1 broken symlink in agent dirs — run `boost heal`"]


class TestStaleLinks:
    def test_live_link_for_no_installed_skill_is_stale(self, two):
        ghost = _link("cursor", "ghost")
        ghost.symlink_to(store.skill_store_dir("tdd-workflow"))
        assert store.stale_links(lockfile.installed(), True) == [str(ghost)]

    def test_not_while_the_lock_cannot_vouch(self, two):
        _link("cursor", "ghost").symlink_to(store.skill_store_dir("tdd-workflow"))
        assert store.stale_links(lockfile.installed(), False) == []

    def test_installed_links_are_not_stale(self, two):
        assert store.stale_links(lockfile.installed(), True) == []


@pytest.fixture()
def narrowed(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    store.install(catalog.resolve_one("commit-messages"), only_agents=["cursor"])
    link = _link("claude-code", "commit-messages")
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(store.skill_store_dir("commit-messages"))
    return link


class TestOutOfScope:
    def test_read_from_disk_not_the_lock(self, narrowed):
        entry = lockfile.get_skill("commit-messages")
        assert "claude-code" not in entry["agents"]
        assert store.out_of_scope_agents(
            "commit-messages", entry, agents.linking_agents()) == ["claude-code"]
        assert store.sync_plan()["out_of_scope_links"] == [
            ("commit-messages", "claude-code")]

    def test_empty_without_a_narrowing(self, narrowed):
        entry = dict(lockfile.get_skill("commit-messages"), only_agents=None)
        assert store.out_of_scope_agents(
            "commit-messages", entry, agents.linking_agents()) == []

    def test_the_users_own_link_is_not_offered(self, narrowed, tmp_path):
        narrowed.unlink()
        narrowed.symlink_to(tmp_path)
        assert store.out_of_scope_agents(
            "commit-messages", lockfile.get_skill("commit-messages"),
            agents.linking_agents()) == []

    def test_doctor_flags_a_hand_made_link(self, narrowed, boost):
        assert [c["message"] for c in _checks(boost, "skill-scope")] == [
            "skill commit-messages is linked for claude-code, outside its "
            "declared scope (cursor) — run `boost sync --prune`"]

    def test_heal_names_it_and_does_not_say_nothing_to_heal(self, narrowed, boost):
        boost("heal")             # creates the agent dirs install skipped
        res = boost("heal")
        flat = " ".join(res.out.split())
        assert ("1 link outside the declared scope: commit-messages → "
                "claude-code — remove with `boost sync --prune`") in flat
        assert "nothing to heal automatically" in flat
        assert "nothing to heal\n" not in res.out
        assert os.path.islink(narrowed)


class TestVerifyAndDrift:
    def test_verify_fails_the_skill_and_names_the_link(self, crossed, boost):
        res = boost("verify", "--json", expect=1)
        rows = {r["name"]: r for r in json.loads(res.out)["skills"]}
        assert rows["brainstorming"]["passed"] is False
        assert rows["brainstorming"]["misdirected_links"] == [
            {"agent": "claude-code", "target": "~/.agents/skills/tdd-workflow"}]
        assert rows["tdd-workflow"]["passed"] is True
        assert "misdirected_links" not in rows["tdd-workflow"]
        text = boost("verify", expect=1).out
        assert ("linked for claude-code to ~/.agents/skills/tdd-workflow — "
                "`boost heal` relinks it") in text
        assert "1 of 2 items failed verification" in text

    def test_drift_reports_it_with_heal(self, crossed, boost):
        rows = {r["name"]: r for r in
                json.loads(boost("drift", "--json").out)["skills"]}
        assert rows["brainstorming"]["status"] == "misdirected-link"
        assert rows["brainstorming"]["hint"] == "boost heal"
        assert rows["tdd-workflow"]["status"] == "in-sync"

    def test_content_drift_outranks_it(self, crossed, boost):
        md = store.skill_store_dir("brainstorming") / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")
        rows = {r["name"]: r for r in
                json.loads(boost("drift", "--json").out)["skills"]}
        assert rows["brainstorming"]["status"] == "local-edits"
