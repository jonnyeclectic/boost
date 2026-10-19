# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A tap clone whose `.git` is gone, and the lock's record of a tap's source.

`Tap.is_cloned` is `path.is_dir()`, so a clone dir that lost its `.git` (a
backup or sync tool that skips it, or a hand `rm`) read as healthy to doctor
and heal while every `boost update` failed with "not a git repository" and
never re-cloned it.
"""
from __future__ import annotations

import shutil
import subprocess

from boost_cli.core import lockfile, registry, util


def _copy_tap(fixture_tap_src, tmp_path, name):
    src = tmp_path / name
    shutil.copytree(fixture_tap_src, src)
    return src


def _break(tap):
    util.rmtree(tap.path / ".git")
    assert tap.path.is_dir() and not (tap.path / ".git").exists()


class TestBrokenCloneProperty:
    def test_a_real_clone_is_not_broken(self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-ok"))
        tap = registry.get("health-ok")
        assert tap.is_cloned
        assert not tap.is_broken_clone

    def test_a_dir_without_git_is_broken(self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-nogit"))
        tap = registry.get("health-nogit")
        _break(tap)
        assert tap.is_cloned          # unchanged: still a directory
        assert tap.is_broken_clone

    def test_a_missing_clone_is_not_cloned_and_not_broken(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-gone"))
        tap = registry.get("health-gone")
        util.rmtree(tap.path)
        assert not tap.is_cloned
        assert not tap.is_broken_clone

    def test_the_wheel_tap_has_no_git_and_is_not_broken(self, sandbox):
        from boost_cli.core import builtin
        builtin.ensure_tap()
        tap = next(t for t in registry.list_taps()
                   if t.url.startswith(registry.WHEEL_SCHEME))
        assert tap.is_cloned
        assert not (tap.path / ".git").exists()
        assert not tap.is_broken_clone


class TestUpdateRecloneBrokenTap:
    def test_update_recovers_a_clone_without_git(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-upd"))
        tap = registry.get("health-upd")
        _break(tap)
        (tap.path / "leftover.txt").write_text("x", encoding="utf-8")
        done, failed = registry.update("health-upd")
        assert failed == {}
        assert done["health-upd"] == "cloned"
        assert (tap.path / ".git").exists()
        assert not (tap.path / "leftover.txt").exists()
        assert not registry.get("health-upd").is_broken_clone

    def test_update_command_exits_zero_and_doctor_is_healthy_after(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-cmd"))
        _break(registry.get("health-cmd"))
        boost("update", "health-cmd")
        res = boost("doctor", expect=None)
        assert "not a git repository" not in res.out + res.err

    def test_update_reclones_a_broken_pinned_tap_at_its_pin(
            self, boost, fixture_tap_src, tmp_path):
        src = _copy_tap(fixture_tap_src, tmp_path, "health-pin")
        first = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"],
                               check=True, capture_output=True,
                               text=True).stdout.strip()
        boost("tap", src, "--at", first)
        tap = registry.get("health-pin")
        _break(tap)
        done, failed = registry.update("health-pin")
        assert failed == {}
        assert done["health-pin"] == "cloned at %s" % first[:7]
        assert registry.get("health-pin").pin == first


class TestDoctorAndHealSeeIt:
    def test_doctor_flags_a_clone_without_git(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-doc"))
        _break(registry.get("health-doc"))
        res = boost("doctor", expect=None)
        text = res.out + res.err
        assert res.rc != 0
        assert "tap health-doc is not a git repository" in text
        assert "boost update health-doc" in text
        assert "1 tap cloned" not in text

    def test_heal_names_the_real_fix_and_is_not_all_clear(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-heal"))
        tap = registry.get("health-heal")
        _break(tap)
        res = boost("heal", expect=None)
        text = res.out + res.err
        assert res.rc == 1
        assert "nothing to heal" not in text
        assert "health-heal" in text
        assert "boost update health-heal" in text
        # heal did not rebuild a catalog over the broken tree
        assert not (tap.path / ".git").exists()

    def test_heal_dry_run_says_the_same(self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-dry"))
        _break(registry.get("health-dry"))
        res = boost("heal", "--dry-run", expect=None)
        assert res.rc == 1
        assert "boost update health-dry" in res.out + res.err
        assert "nothing to heal" not in res.out + res.err


def _rule_workflow_tap(fixture_tap_src, tmp_path, name):
    src = _copy_tap(fixture_tap_src, tmp_path, name)
    (src / "rules").mkdir()
    (src / "rules" / "tapurl-rule.mdc").write_text(
        "---\ndescription: A house rule\n---\nAlways test.\n", encoding="utf-8")
    (src / "commands").mkdir()
    (src / "commands" / "tapurl-flow.md").write_text(
        "---\ndescription: Ship it\n---\nShip the thing.\n", encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=src, check=True, capture_output=True)
    run("git", "add", "-A")
    run("git", "-c", "user.email=t@boost.test", "-c", "user.name=t",
        "commit", "-qm", "rule and workflow")
    return src


class TestLockRecordsTapUrl:
    def test_skill_rule_and_workflow_entries_record_the_tap_url(
            self, boost, fixture_tap_src, tmp_path):
        src = _rule_workflow_tap(fixture_tap_src, tmp_path, "tapurl-src")
        boost("tap", src)
        url = registry.get("tapurl-src").url
        assert url == str(src.resolve())
        boost("install", "brainstorming")
        boost("install", "tapurl-rule")
        boost("install", "tapurl-flow")
        lock = lockfile.read()
        assert lock["skills"]["brainstorming"]["tap_url"] == url
        assert lock["rules"]["tapurl-rule"]["tap_url"] == url
        assert lock["workflows"]["tapurl-flow"]["tap_url"] == url
