# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: an agent the config keeps a rule or workflow out of is named.

A Claude Code profile added by hand as ``skills_only`` (the antigravity row,
copied) gets no subagent, no command and no rule, and no lock row says so --
so install listed only the agents it wrote and doctor called everything fully
materialized. Install and doctor now name the agent and the key that decided
it, and doctor says when the row looks like a Claude Code profile.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from boost_cli.core import config, paths

RULE = "house-rule"
WORKFLOW = "reviewer"


@pytest.fixture()
def duo(boost, fixture_tap_src, tmp_path):
    """A sandbox with a tap holding one rule and one subagent, and a
    ``claude-personal`` row copied from the antigravity template."""
    tap = tmp_path / "duo-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    (tap / "rules" / "house.mdc").write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\nAlways test.\n" % RULE,
        encoding="utf-8")
    (tap / "agents").mkdir()
    (tap / "agents" / ("%s.md" % WORKFLOW)).write_text(
        "---\nname: %s\ndescription: reviews\n---\n\nReview.\n" % WORKFLOW,
        encoding="utf-8")
    subprocess.run(["git", "-C", str(tap), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap), "commit", "-qm", "duo"],
                   check=True, capture_output=True)
    boost("tap", tap)
    cfg = config.load()
    cfg["agents"]["claude-personal"] = {
        "dir": "~/.claude-personal/skills", "enabled": True,
        "project_scope": False, "skills_only": True}
    config.save(cfg)
    return boost


def _flat(text):
    return " ".join(text.split())


def test_install_names_the_profile_it_left_out(duo):
    out = _flat(duo("install", RULE).out)
    assert ("claude-personal: takes skills only "
            "(agents.claude-personal.skills_only) — not written") in out
    out = _flat(duo("install", WORKFLOW).out)
    assert ("claude-personal: takes skills only "
            "(agents.claude-personal.skills_only) — not written") in out
    # windsurf's `workflows: false` is boost's own: named, its key not offered
    assert "windsurf: has no slash-command format — not written" in out
    assert "agents.windsurf.workflows" not in out
    assert not (paths.home() / ".claude-personal" / "agents").exists()


def test_doctor_names_it_once_and_counts_no_issue(duo):
    duo("install", RULE)
    duo("install", WORKFLOW)
    r = duo("doctor")
    out = _flat(r.out)
    assert ("claude-personal: takes skills only "
            "(agents.claude-personal.skills_only) — not written for rule "
            "%s, workflow %s" % (RULE, WORKFLOW)) in out
    # the line under it no longer reads as covering every agent
    assert ("1 rule and 1 workflow fully materialized for every agent "
            "boost writes") in out
    assert "issue" not in out.split("● ")[-1]
    assert r.rc == 0
    # no `.claude.json` beside it, so nothing calls it a Claude profile
    assert "looks like a Claude Code profile" not in out


def test_doctor_offers_the_flag_to_a_claude_profile(duo):
    (paths.home() / ".claude-personal").mkdir(parents=True, exist_ok=True)
    (paths.home() / ".claude-personal" / ".claude.json").write_text(
        "{}\n", encoding="utf-8")
    out = _flat(duo("doctor").out)
    assert ("agents.claude-personal looks like a Claude Code profile — "
            "`boost config set agents.claude-personal.skills_only false` "
            "then `boost sync` gives it agents/, commands/ and rules/") in out


def test_the_named_remedy_writes_the_profile(duo):
    """The hint is only worth printing if following it works."""
    (paths.home() / ".claude-personal").mkdir(parents=True, exist_ok=True)
    (paths.home() / ".claude-personal" / ".claude.json").write_text(
        "{}\n", encoding="utf-8")
    duo("install", WORKFLOW)
    duo("config", "set", "agents.claude-personal.skills_only", "false")
    duo("sync")
    assert (paths.home() / ".claude-personal" / "agents"
            / ("%s.md" % WORKFLOW)).is_file()
    out = _flat(duo("doctor").out)
    assert "claude-personal: takes skills only" not in out
    assert "looks like a Claude Code profile" not in out
