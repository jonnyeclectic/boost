# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: a tap pin survives every re-clone, and drift's
source-missing hint is one its remedy can act on.

* `boost drift` re-cloned a deleted pinned tap at HEAD through
  `store.source_dir_for` (a bare `clone_shallow`), leaving config.json's pin
  beside a clone that was not on it. `update` then reported "pinned at <pin>
  (skipped)", and `heal` + `doctor` turned the off-pin clone green.
* `boost drift` hinted `boost update` for an item removed from a still-tapped
  registry, which `update` answers "no longer in tap — leaving as-is".
"""
from __future__ import annotations

import json
import shutil
import subprocess

from boost_cli.core import gitutil, registry, util


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


def _rev(repo, ref="HEAD"):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", ref],
                          check=True, capture_output=True,
                          text=True).stdout.strip()


def _said(r):
    return " ".join((r.out + r.err).split())


def _two_commit_tap(fixture_tap_src, tmp_path):
    """A copy of the fixture with a second commit. Returns (src, pin, head)."""
    src = tmp_path / "four"
    shutil.copytree(fixture_tap_src, src)
    md = src / "skills" / "brainstorming" / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nc2\n", encoding="utf-8")
    _git(src, "commit", "-qam", "c2")
    return src, _rev(src, "HEAD~1"), _rev(src)


class TestPinnedTapReclone:
    def test_drift_reclones_a_deleted_pinned_tap_at_its_pin(
            self, boost, fixture_tap_src, tmp_path):
        src, pin, head = _two_commit_tap(fixture_tap_src, tmp_path)
        assert pin != head
        boost("tap", src, "--at", pin)
        boost("install", "four:cowboy-coding")
        tap = registry.get("four")
        util.rmtree(tap.path)   # git objects are read-only on Windows

        boost("drift")

        assert gitutil.head_commit(tap.path) == pin
        assert registry.get("four").pin == pin
        r = boost("update", "four")
        assert "four: pinned at %s (skipped)" % pin[:7] in _said(r)
        boost("doctor")

    def test_doctor_flags_an_off_pin_clone_and_update_returns_it(
            self, boost, fixture_tap_src, tmp_path):
        src, pin, head = _two_commit_tap(fixture_tap_src, tmp_path)
        boost("tap", src, "--at", pin)
        boost("install", "four:cowboy-coding")
        clone = registry.get("four").path
        _git(clone, "fetch", "-q", "origin", head)
        _git(clone, "checkout", "-q", "--detach", head)

        doc = boost("doctor", expect=1)
        said = _said(doc)
        assert ("tap four is pinned at %s but its clone is at %s — run "
                "`boost update four` to return it, or `boost update --force "
                "four` to follow its default branch" % (pin[:7], head[:7])
                ) in said
        # Not the stale-catalog line: its remedy (`heal`) rescans the cache
        # to match the wrong tree and leaves the clone off its pin.
        assert "catalog is stale" not in said

        r = boost("update", "four")
        assert ("four: %s → %s (back on its pin)" % (head[:7], pin[:7])
                in _said(r))
        assert gitutil.head_commit(clone) == pin
        assert registry.get("four").pin == pin
        boost("doctor")                       # rc 0: the remedy worked


class TestDriftRemovedUpstream:
    def _tap_with_rule(self, boost, fixture_tap_src, tmp_path):
        src = tmp_path / "up"
        shutil.copytree(fixture_tap_src, src)
        md = src / "rules" / "house.mdc"
        md.parent.mkdir(parents=True)
        md.write_text("---\nname: house-rule\nversion: 1.0.0\n---\n\n"
                      "Keep it tidy.\n", encoding="utf-8")
        _git(src, "add", "rules")
        _git(src, "commit", "-qm", "add rule")
        boost("tap", src)
        return src

    def _hints(self, boost):
        rows = json.loads(boost("drift", "--json").out)["skills"]
        return {r["name"]: (r["status"], r["hint"]) for r in rows}

    def test_removed_skill_and_rule_hint_uninstall_not_update(
            self, boost, fixture_tap_src, tmp_path):
        src = self._tap_with_rule(boost, fixture_tap_src, tmp_path)
        boost("install", "brainstorming")
        boost("install", "house-rule")
        _git(src, "rm", "-rq", "skills/brainstorming", "rules/house.mdc")
        _git(src, "commit", "-qm", "rm")
        boost("update")

        hints = self._hints(boost)
        assert hints["brainstorming"] == (
            "source-missing", "boost uninstall brainstorming, or keep as-is")
        assert hints["house-rule"] == (
            "source-missing", "boost uninstall house-rule, or keep as-is")
        assert "boost uninstall brainstorming, or keep as-is" in _said(
            boost("drift"))

    def test_untapped_source_still_hints_retap(self, boost, fixture_tap_src,
                                               tmp_path):
        self._tap_with_rule(boost, fixture_tap_src, tmp_path)
        boost("install", "brainstorming")
        boost("untap", "up", expect=None)
        status, hint = self._hints(boost)["brainstorming"]
        assert status == "source-missing"
        assert hint.startswith("boost tap ")
