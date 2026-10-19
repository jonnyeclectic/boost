# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: pins hold through reinstall and update, profiles snapshot.

Three ways user-set state was lost or misreported:

* `boost reinstall` of a commit-pinned item erased ``commit_pin`` and moved a
  pinned item to whatever the tap now held;
* `boost profile save` recorded sidelined skills, so restoring the profile
  switched them back on;
* `boost update` said "everything up to date" over pinned items it skipped,
  while `boost outdated` listed them.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import lockfile, paths


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


def _tap_copy(boost, fixture_tap_src, tmp_path, name, rule=False):
    src = tmp_path / name
    shutil.copytree(fixture_tap_src, src)
    if rule:
        md = src / "rules" / "house.mdc"
        md.parent.mkdir(parents=True)
        md.write_text("---\nname: house-rule\nversion: 1.0.0\n---\n\n"
                      "Keep it tidy.\n", encoding="utf-8")
        _git(src, "add", "rules")
        _git(src, "commit", "-qm", "add rule")
    boost("tap", src)
    return src


def _bump_cowboy(src):
    md = src / "skills" / "cowboy-coding" / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8")
                  .replace("version: 0.1.0", "version: 0.2.0")
                  + "\nnew upstream line\n", encoding="utf-8")
    _git(src, "commit", "-qam", "bump cowboy-coding")


def _bump_rule(src):
    md = src / "rules" / "house.mdc"
    md.write_text("---\nname: house-rule\nversion: 1.1.0\n---\n\n"
                  "Keep it tidier.\n", encoding="utf-8")
    _git(src, "commit", "-qam", "bump rule")


def _said(r):
    return " ".join((r.out + r.err).split())


class TestReinstallHoldsThePin:
    def test_commit_pinned_skill_is_not_moved(self, boost, fixture_tap_src,
                                              tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-reinstall-commit")
        boost("install", "cowboy-coding")
        boost("pin", "cowboy-coding", "--commit")
        pin = lockfile.get_skill("cowboy-coding")["commit_pin"]
        _bump_cowboy(src)
        boost("update")

        r = boost("reinstall", "cowboy-coding", expect=1)
        said = _said(r)
        assert "cowboy-coding: not reinstalled — commit-pinned at %s" % pin[:12] \
            in said
        assert "`boost unpin cowboy-coding` first" in said
        assert "reinstalled cowboy-coding v0.2.0" not in said
        lk = lockfile.get_skill("cowboy-coding")
        assert lk["commit_pin"] == pin
        assert lk["commit"] == pin
        assert lk["version"] == "0.1.0"
        text = (paths.store_dir() / "cowboy-coding" / "SKILL.md").read_text(
            encoding="utf-8")
        assert "new upstream line" not in text
        v = boost("verify")
        assert "commit-pinned" in v.out

    def test_same_commit_reinstall_keeps_the_pin(self, boost, fixture_tap_src,
                                                 tmp_path):
        _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-reinstall-same")
        boost("install", "cowboy-coding")
        boost("pin", "cowboy-coding", "--commit")
        pin = lockfile.get_skill("cowboy-coding")["commit_pin"]
        r = boost("reinstall", "cowboy-coding")
        assert "reinstalled cowboy-coding v0.1.0" in r.out
        lk = lockfile.get_skill("cowboy-coding")
        assert lk["commit_pin"] == pin and lk["pinned"] is True
        assert "commit-pinned" in boost("verify").out

    def test_version_pinned_skill_is_not_moved(self, boost, fixture_tap_src,
                                               tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-reinstall-version")
        boost("install", "cowboy-coding")
        boost("pin", "cowboy-coding")
        _bump_cowboy(src)
        boost("update")
        r = boost("reinstall", "cowboy-coding", expect=1)
        assert ("cowboy-coding: not reinstalled — pinned at v0.1.0, and its "
                "source has changed since") in _said(r)
        assert lockfile.get_skill("cowboy-coding")["version"] == "0.1.0"
        boost("unpin", "cowboy-coding")
        r = boost("reinstall", "cowboy-coding")
        assert "reinstalled cowboy-coding v0.2.0" in r.out

    def test_commit_pinned_rule_keeps_the_pin(self, boost, fixture_tap_src,
                                              tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-reinstall-rule",
                        rule=True)
        boost("install", "house-rule")
        boost("pin", "house-rule", "--commit")
        pin = lockfile.get_rule("house-rule")["commit_pin"]
        boost("reinstall", "house-rule")
        assert lockfile.get_rule("house-rule")["commit_pin"] == pin
        _bump_rule(src)
        boost("update")
        r = boost("reinstall", "house-rule", expect=1)
        assert "rule house-rule: not reinstalled — commit-pinned at" in _said(r)
        lk = lockfile.get_rule("house-rule")
        assert lk["commit_pin"] == pin and lk["version"] == "1.0.0"


class TestProfileSaveSkipsSidelined:
    def test_sidelined_skill_stays_off_after_round_trip(
            self, boost, fixture_tap_src, tmp_path):
        _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-profile")
        boost("install", "brainstorming", "tdd-workflow", "cowboy-coding")
        boost("uninstall", "tdd-workflow")
        boost("profile", "save", "minimal")
        boost("install", "tdd-workflow")
        boost("profile", "use", "minimal")
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "profile"

        r = boost("profile", "save", "now")
        said = _said(r)
        assert "saved profile now (2 skills)" in said
        assert ("not captured: 1 sidelined skill (tdd-workflow) — `profile use "
                "now` keeps it off") in said
        shown = json.loads(boost("profile", "show", "now", "--json").out)
        assert set(shown["skills"]) == {"brainstorming", "cowboy-coding"}
        js = json.loads(boost("profile", "save", "now", "--json").out)
        assert js["skills"] == 2
        assert js["sidelined_not_captured"] == ["tdd-workflow"]

        boost("install", "--force", "tdd-workflow")
        boost("profile", "use", "now")
        lk = lockfile.get_skill("tdd-workflow")
        assert lk["sidelined_by"] == "profile"
        assert lk["agents"] == []

    def test_nothing_sidelined_says_nothing(self, boost, fixture_tap_src,
                                            tmp_path):
        _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-profile-plain")
        boost("install", "brainstorming")
        r = boost("profile", "save", "plain")
        assert "not captured" not in _said(r)
        js = json.loads(boost("profile", "save", "plain", "--json").out)
        assert js["sidelined_not_captured"] == []


class TestUpdateNamesPinnedHolds:
    def test_pinned_skill_with_an_update_is_not_an_all_clear(
            self, boost, fixture_tap_src, tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-update-skill")
        boost("install", "cowboy-coding")
        boost("pin", "cowboy-coding")
        _bump_cowboy(src)
        r = boost("update")
        said = _said(r)
        assert "everything up to date" not in said
        assert ("1 pinned item has an update held back — `boost outdated` "
                "lists it, `boost unpin <name>` lets one update") in said
        assert lockfile.get_skill("cowboy-coding")["version"] == "0.1.0"
        assert "0.1.0 (pinned)" in boost("outdated").out

    def test_pinned_rule_and_skill_are_counted_together(
            self, boost, fixture_tap_src, tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "lfp-update-both",
                        rule=True)
        boost("install", "cowboy-coding")
        boost("install", "house-rule")
        boost("pin", "cowboy-coding")
        boost("pin", "house-rule")
        _bump_cowboy(src)
        _bump_rule(src)
        said = _said(boost("update"))
        assert "everything up to date" not in said
        assert ("2 pinned items have an update held back — `boost outdated` "
                "lists them") in said
        assert lockfile.get_rule("house-rule")["version"] == "1.0.0"

    @pytest.mark.parametrize("pin", [False, True])
    def test_pinned_without_an_update_is_still_up_to_date(
            self, boost, fixture_tap_src, tmp_path, pin):
        src = _tap_copy(boost, fixture_tap_src, tmp_path,
                        "lfp-update-none-%d" % pin)
        boost("install", "cowboy-coding")
        if pin:
            boost("pin", "cowboy-coding")
        _git(src, "commit", "-q", "--allow-empty", "-m", "nothing")
        said = _said(boost("update"))
        assert "everything up to date" in said
        assert "pinned item" not in said
