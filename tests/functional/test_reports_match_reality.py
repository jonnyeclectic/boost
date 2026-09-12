# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: boost's own tallies must describe boost's own state.

Three commands reported something false about the machine they were run on:

* ``boost taps`` headed its count column SKILLS and footed "N taps · N skills",
  but the number is ``len(catalog.load_tap(tap))`` -- every item, of all three
  kinds. ``boost tap`` had already been fixed to say "items" for exactly this
  reason ("a pure rules registry reported '257 skills' immediately after the
  README promised three kinds"); the listing never got the same treatment.
* ``boost who``'s SKILLS column counted distinct journal *subjects*, and a
  subject is a grab-bag -- ``journal.log("tap", tap.name)``,
  ``journal.log("config", args.key)``, snapshot ids, scopes, paths. So a fresh
  machine with one skill installed reported four "skills". The function already
  defines the right filter (``expertise``) one branch above; the aggregate
  branch just never used it.
* ``boost who --json`` printed prose whenever nothing matched, because the
  empty-events guard runs before the ``--json`` check -- and the prose it
  printed, "no journal activity yet", is a claim about the whole journal made
  when the journal is full and only the *filter* came back empty.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def mixed_tap(boost, tmp_path):
    """A tap holding exactly one of each kind. Returns its path."""
    import subprocess

    src = tmp_path / "mixed-tap"
    (src / "skills" / "alpha-skill").mkdir(parents=True)
    (src / "rules").mkdir()
    (src / "commands").mkdir()
    (src / "skills" / "alpha-skill" / "SKILL.md").write_text(
        "---\nname: alpha-skill\ndescription: A sample skill.\n---\nBody.\n",
        encoding="utf-8")
    (src / "rules" / "beta-rule.mdc").write_text(
        "---\ndescription: A sample rule.\n---\nRule body.\n", encoding="utf-8")
    (src / "commands" / "gamma-flow.md").write_text(
        "---\ndescription: A sample workflow.\n---\nWorkflow body.\n",
        encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=src, check=True)
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], cwd=src, check=True)
    boost("tap", str(src))
    return src


class TestTapsCountsItemsNotSkills:
    def test_the_column_is_not_labelled_skills(self, boost, mixed_tap):
        r = boost("taps")
        assert "ITEMS" in r.out
        assert "SKILLS" not in r.out

    def test_the_footer_counts_items(self, boost, mixed_tap):
        """One skill, one rule and one workflow is three items, not three skills."""
        r = boost("taps")
        assert "3 items" in r.out
        assert "3 skills" not in r.out

    def test_a_single_tap_is_not_pluralised(self, boost, mixed_tap):
        assert "1 tap ·" in boost("taps").out

    def test_json_keeps_the_old_key_and_gains_the_right_one(self, boost, mixed_tap):
        """`skills` stays so existing scripts keep working; `items` is the truth."""
        data = json.loads(boost("taps", "--json").out)
        assert data[0]["items"] == 3
        assert data[0]["skills"] == 3


class TestWhoCountsSkills:
    def test_a_tap_is_not_counted_as_a_skill(self, boost, installed):
        """`tap` and `install` both write a journal subject; only one is a skill."""
        data = json.loads(boost("who", "--json").out)
        (person,) = data.values()
        assert person["skills"] == [installed]

    def test_the_table_agrees_with_the_json(self, boost, installed):
        r = boost("who")
        assert " 1 " in r.out  # the SKILLS cell


class TestQuarantinedSkillIsNotAdvertised:
    """`quarantine` deletes the symlinks but left `agents` on the lock entry,
    so `list` kept naming three agents that could no longer see the skill.
    `release` recomputes the list from `link_agents`, so clearing it costs
    nothing and makes every consumer of the lock truthful at once."""

    def test_agents_are_cleared_on_quarantine(self, boost, installed):
        assert json.loads(boost("list", "--json").out)["skills"][installed]["agents"]
        boost("quarantine", installed)
        data = json.loads(boost("list", "--json").out)
        assert data["skills"][installed]["agents"] == []
        assert data["skills"][installed]["quarantined"] is True

    def test_the_table_stops_naming_agents(self, boost, installed):
        boost("quarantine", installed)
        row = next(ln for ln in boost("list").out.splitlines()
                   if ln.startswith(installed))
        assert "claude" not in row
        assert "quarantined" in row

    def test_release_restores_them(self, boost, installed):
        boost("quarantine", installed)
        boost("quarantine", "--release", installed)
        data = json.loads(boost("list", "--json").out)
        assert data["skills"][installed]["agents"]
        assert data["skills"][installed]["quarantined"] is False

    def test_the_cell_matches_the_symlinks_on_disk(self, boost, installed, sandbox):
        """The column claims availability, so check the thing it claims."""
        boost("quarantine", installed)
        live = [d for d in (".claude", ".windsurf", ".cursor")
                if (sandbox / d / "skills" / installed).exists()]
        named = json.loads(boost("list", "--json").out)["skills"][installed]["agents"]
        assert live == [] and named == []


class TestSidelinedSkillStaysSidelined:
    """`profile use` unlinked the extras but left `agents` on the lock, so
    `boost doctor` reported each as "not linked — run `boost sync`" and
    `boost sync` relinked them, silently undoing the switch the user asked for."""

    @pytest.fixture()
    def sidelined(self, boost, installed):
        boost("profile", "save", "p1")          # brainstorming only
        boost("install", "commit-messages")
        boost("profile", "save", "both")        # both, for the round trip
        boost("profile", "use", "p1")
        return "commit-messages"

    def test_switching_back_relinks_it(self, boost, sidelined, sandbox):
        """A sideline that cannot be undone would be worse than the bug."""
        boost("profile", "use", "both")
        assert (sandbox / ".claude" / "skills" / sidelined).exists()
        entry = json.loads(boost("list", "--json").out)["skills"][sidelined]
        assert entry["agents"] and not entry.get("sidelined_by")

    def test_the_lock_records_the_sideline(self, boost, sidelined):
        data = json.loads(boost("list", "--json").out)
        assert data["skills"][sidelined]["agents"] == []

    def test_doctor_does_not_prescribe_undoing_it(self, boost, sidelined):
        assert "not linked" not in boost("doctor", expect=None).out

    def test_sync_does_not_reverse_the_switch(self, boost, sidelined, sandbox):
        boost("sync")
        assert not (sandbox / ".claude" / "skills" / sidelined).exists()


class TestWhoOnNoMatch:
    def test_json_stays_json_when_nothing_matches(self, boost, installed):
        r = boost("who", "no-such-skill", "--json")
        payload = json.loads(r.out)          # would raise on prose
        assert payload["skill"] == "no-such-skill"
        assert payload["events"] == []

    def test_an_unknown_name_does_not_claim_an_empty_journal(self, boost, installed):
        r = boost("who", "no-such-skill")
        assert "no journal activity yet" not in r.out

    def test_a_genuinely_empty_journal_still_says_so(self, boost, sandbox):
        assert "no journal activity yet" in boost("who").out
