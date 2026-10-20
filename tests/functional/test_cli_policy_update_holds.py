# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: policy and quarantine against `boost update`.

Three ways a governance setting was misreported or not enforced:

* at exactly ``max_skills``, upgrading or reinstalling a skill already
  installed was refused as if it added one, and `boost update` then said
  "everything up to date";
* `boost update` skipped a quarantined skill with a newer upstream and said
  "everything up to date", while `boost outdated` said `boost update`
  upgrades it;
* a tap-qualified ``blocked_skills`` entry (``tap:name``) never matched.
"""
from __future__ import annotations

import shutil
import subprocess

from boost_cli.core import lockfile


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


def _tap_copy(boost, fixture_tap_src, tmp_path, name):
    src = tmp_path / name
    shutil.copytree(fixture_tap_src, src)
    boost("tap", src)
    return src


def _bump_cowboy(src):
    md = src / "skills" / "cowboy-coding" / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8")
                  .replace("version: 0.1.0", "version: 0.2.0")
                  + "\nnew upstream line\n", encoding="utf-8")
    _git(src, "commit", "-qam", "bump cowboy-coding")


def _said(r):
    return " ".join((r.out + r.err).split())


class TestMaxSkillsAtCap:
    def test_update_upgrades_an_installed_skill_at_the_cap(
            self, boost, fixture_tap_src, tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "pu-cap-update")
        boost("install", "cowboy-coding")
        boost("install", "brainstorming")
        boost("policy", "set", "max_skills", "2")
        _bump_cowboy(src)
        said = _said(boost("update"))
        assert "policy blocks" not in said
        assert "upgraded cowboy-coding v0.1.0 → v0.2.0" in said
        assert lockfile.get_skill("cowboy-coding")["version"] == "0.2.0"

    def test_reinstall_at_the_cap(self, boost, fixture_tap_src, tmp_path):
        _tap_copy(boost, fixture_tap_src, tmp_path, "pu-cap-reinstall")
        boost("install", "cowboy-coding")
        boost("policy", "set", "max_skills", "1")
        said = _said(boost("reinstall", "cowboy-coding"))
        assert "policy blocks" not in said
        assert "Reinstalled 1 skill" in said

    def test_a_new_skill_is_still_refused_at_the_cap(
            self, boost, fixture_tap_src, tmp_path):
        _tap_copy(boost, fixture_tap_src, tmp_path, "pu-cap-new")
        boost("install", "cowboy-coding")
        boost("policy", "set", "max_skills", "1")
        r = boost("install", "brainstorming", expect=1)
        assert "max_skills limit (1) reached" in _said(r)

    def test_a_refused_upgrade_is_not_an_all_clear(
            self, boost, fixture_tap_src, tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "pu-refused")
        boost("install", "cowboy-coding")
        _bump_cowboy(src)
        boost("policy", "set", "blocked_skills", "cowboy-coding")
        said = _said(boost("update"))
        assert "policy blocks installing cowboy-coding" in said
        assert "everything up to date" not in said
        assert "1 item held back — see above" in said
        assert lockfile.get_skill("cowboy-coding")["version"] == "0.1.0"


class TestUpdateNamesQuarantinedHolds:
    def test_quarantined_skill_with_an_update_is_not_an_all_clear(
            self, boost, fixture_tap_src, tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "pu-quarantine")
        boost("install", "cowboy-coding")
        boost("quarantine", "cowboy-coding")
        _bump_cowboy(src)
        said = _said(boost("update"))
        assert "everything up to date" not in said
        assert ("1 quarantined item has an update held back — `boost "
                "quarantine --release <name>` lets one update") in said
        lk = lockfile.get_skill("cowboy-coding")
        assert lk["version"] == "0.1.0"
        assert lk["quarantined"]
        assert ("`boost update` upgrades (pinned and quarantined items stay "
                "put)") in _said(boost("outdated"))

    def test_quarantined_without_an_update_is_still_up_to_date(
            self, boost, fixture_tap_src, tmp_path):
        src = _tap_copy(boost, fixture_tap_src, tmp_path, "pu-quarantine-none")
        boost("install", "cowboy-coding")
        boost("quarantine", "cowboy-coding")
        _git(src, "commit", "-q", "--allow-empty", "-m", "nothing")
        said = _said(boost("update"))
        assert "everything up to date" in said
        assert "quarantined item" not in said


class TestTapQualifiedBlocklist:
    def test_tap_name_entry_blocks_install_and_fails_check(
            self, boost, fixture_tap_src, tmp_path):
        _tap_copy(boost, fixture_tap_src, tmp_path, "pu-block")
        boost("install", "cowboy-coding")
        boost("policy", "set", "blocked_skills", "pu-block:cowboy-coding")
        r = boost("policy", "check", expect=1)
        assert "cowboy-coding" in r.out + r.err
        assert "on the blocklist" in _said(r)
        boost("uninstall", "cowboy-coding")
        r = boost("install", "pu-block:cowboy-coding", expect=1)
        assert ("policy blocks installing cowboy-coding: skill "
                "'cowboy-coding' is on the blocklist") in _said(r)

    def test_another_taps_entry_does_not_block(
            self, boost, fixture_tap_src, tmp_path):
        _tap_copy(boost, fixture_tap_src, tmp_path, "pu-block-other")
        boost("policy", "set", "blocked_skills", "elsewhere:cowboy-coding")
        boost("install", "cowboy-coding")
        assert lockfile.get_skill("cowboy-coding") is not None
        boost("policy", "check")
