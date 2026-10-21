# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost list` and `boost info` flag a lock row whose store dir is gone.

Measured before this fix: with ``~/.agents/skills/brainstorming`` moved away,
`list` printed it with every agent and an empty FLAGS column under "2 skills
installed", and `info` said ``[installed]``. Only doctor said it was missing,
though no agent can load a skill with no store dir.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import lockfile, store, util


@pytest.fixture()
def two(boost, tapped):
    boost("install", "brainstorming", "tdd-workflow")
    util.rmtree(store.skill_store_dir("brainstorming"))


def _row(out: str, name: str) -> str:
    return next(ln for ln in out.splitlines() if ln.startswith(name + " "))


class TestList:
    def test_the_row_is_flagged_and_the_heal_is_named(self, boost, two):
        r = boost("list")
        assert _row(r.out, "brainstorming").endswith("missing")
        assert "missing" not in _row(r.out, "tdd-workflow")
        assert ("1 skill is missing from the store, so no agent can load it "
                "(brainstorming) — `boost heal` restores it") in " ".join(
                    r.out.split())

    def test_several_are_counted(self, boost, two):
        util.rmtree(store.skill_store_dir("tdd-workflow"))
        r = boost("list")
        assert ("2 skills are missing from the store, so no agent can load "
                "them (brainstorming, tdd-workflow) — `boost heal` restores "
                "them") in " ".join(r.out.split())

    def test_json_marks_only_the_missing_row(self, boost, two):
        data = json.loads(boost("list", "--json").out)
        assert data["skills"]["brainstorming"]["missing_from_store"] is True
        assert "missing_from_store" not in data["skills"]["tdd-workflow"]
        # The lock itself is not changed.
        assert "missing_from_store" not in lockfile.get_skill("brainstorming")

    def test_a_healthy_install_says_nothing(self, boost, installed):
        r = boost("list")
        assert "missing" not in r.out


class TestInfo:
    def test_the_card_says_missing(self, boost, two):
        r = boost("info", "brainstorming")
        assert "[installed] [missing from store]" in r.out
        assert "missing  (`boost heal` restores it)" in r.out
        data = json.loads(boost("info", "brainstorming", "--json").out)
        assert (data["missing_from_store"], data["store"]) == (True, None)

    def test_a_present_one_does_not(self, boost, two):
        r = boost("info", "tdd-workflow")
        assert "missing" not in r.out
        data = json.loads(boost("info", "tdd-workflow", "--json").out)
        assert data["missing_from_store"] is False

    def test_a_skill_not_installed_is_not_missing(self, boost, tapped):
        data = json.loads(boost("info", "brainstorming", "--json").out)
        assert data["missing_from_store"] is False
