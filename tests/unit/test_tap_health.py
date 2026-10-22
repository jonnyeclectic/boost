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

import pytest

from boost_cli.core import gitutil, lockfile, paths, registry, util
from boost_cli.errors import BoostError


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


class TestFailedRecloneKeepsTheTree:
    """`update` on a broken clone used to clear the tree *before* cloning, so
    a re-clone that failed left nothing on disk to scan or install from."""

    def _staging(self, tap):
        return tap.path.with_name(tap.path.name + ".boost-reclone")

    def test_unreachable_source_leaves_the_tree_in_place(
            self, boost, fixture_tap_src, tmp_path):
        src = _copy_tap(fixture_tap_src, tmp_path, "health-keep")
        boost("tap", src)
        tap = registry.get("health-keep")
        _break(tap)
        before = sorted(str(p.relative_to(tap.path))
                        for p in tap.path.rglob("*"))
        assert before
        shutil.move(str(src), str(tmp_path / "moved-away"))
        with pytest.raises(BoostError):
            registry.update("health-keep")
        after = sorted(str(p.relative_to(tap.path))
                       for p in tap.path.rglob("*"))
        assert after == before
        assert not self._staging(tap).exists()
        assert registry.get("health-keep").is_broken_clone

    def test_install_still_works_after_a_failed_reclone(
            self, boost, fixture_tap_src, tmp_path):
        src = _copy_tap(fixture_tap_src, tmp_path, "health-inst")
        boost("tap", src)
        _break(registry.get("health-inst"))
        shutil.move(str(src), str(tmp_path / "gone-inst"))
        res = boost("update", "health-inst", expect=None)
        assert res.rc != 0
        # `is_sparse` is memoised per process; a real `install` is a new one.
        gitutil._SPARSE.clear()
        boost("install", "brainstorming")
        assert (paths.store_dir() / "brainstorming").is_dir()

    def test_unhonourable_pin_leaves_the_tree_in_place(
            self, boost, fixture_tap_src, tmp_path, monkeypatch):
        src = _copy_tap(fixture_tap_src, tmp_path, "health-badpin")
        first = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"],
                               check=True, capture_output=True,
                               text=True).stdout.strip()
        boost("tap", src, "--at", first)
        tap = registry.get("health-badpin")
        _break(tap)
        marker = tap.path / "marker.txt"
        marker.write_text("kept", encoding="utf-8")

        def refuse(path, sha):
            raise BoostError("no such commit")
        monkeypatch.setattr(registry.gitutil, "checkout_commit", refuse)
        with pytest.raises(BoostError):
            registry.update("health-badpin")
        assert marker.read_text(encoding="utf-8") == "kept"
        assert not self._staging(tap).exists()

    def test_a_stale_staging_dir_does_not_block_the_reclone(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-stale"))
        tap = registry.get("health-stale")
        _break(tap)
        staging = self._staging(tap)
        staging.mkdir()
        (staging / "junk.txt").write_text("x", encoding="utf-8")
        done, failed = registry.update("health-stale")
        assert failed == {}
        assert done["health-stale"] == "cloned"
        assert (tap.path / ".git").is_dir()
        assert not staging.exists()


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


    @pytest.mark.parametrize("dry", [False, True])
    def test_heal_fails_over_a_tap_that_is_not_cloned(
            self, boost, fixture_tap_src, tmp_path, dry):
        # Doctor counts an uncloned tap as an issue; heal warned about it and
        # then printed "nothing to heal" and exited 0 beneath the warning.
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-uncl"))
        tap = registry.get("health-uncl")
        util.rmtree(tap.path)
        res = boost("heal", *(["--dry-run"] if dry else []), expect=None)
        text = res.out + res.err
        assert res.rc == 1
        assert ("tap health-uncl not cloned — skipped (run `boost update`)"
                in text)
        assert "nothing to heal" not in text
        assert not tap.path.exists()


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


class TestUnfinishedClones:
    """A clone killed part-way leaves `repos/<x>/.git` that nothing lists."""

    def test_names_only_unlisted_dirs_with_no_head(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-listed"))
        repos = paths.repos_dir()
        (repos / "o__half" / ".git").mkdir(parents=True)
        (repos / "o__bare").mkdir()
        # Someone's real clone, unlisted: not debris, and not boost's to call so.
        subprocess.run(["git", "clone", "-q", str(fixture_tap_src),
                        str(repos / "o__whole")], check=True,
                       capture_output=True)
        (repos / "stray.txt").write_text("x", encoding="utf-8")
        assert registry.unfinished_clones() == [repos / "o__bare",
                                                repos / "o__half"]

    def test_a_listed_tap_is_left_to_the_tap_checks(
            self, boost, fixture_tap_src, tmp_path):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "health-headless"))
        _break(registry.get("health-headless"))
        assert registry.unfinished_clones() == []

    def test_nothing_without_git_or_without_a_repos_dir(
            self, sandbox, monkeypatch):
        repos = paths.repos_dir()
        if repos.exists():
            util.rmtree(repos)
        assert registry.unfinished_clones() == []
        (repos / "o__half" / ".git").mkdir(parents=True)
        monkeypatch.setattr(gitutil, "has_git", lambda: False)
        assert registry.unfinished_clones() == []


def _drop_from_config(name):
    from boost_cli.core import config
    config.mutate(lambda cfg: cfg.__setitem__(
        "taps", [t for t in cfg["taps"] if t["name"] != name]))


class TestUnlistedClones:
    """A complete clone no tap row lists: named, with the command that re-adds it."""

    def test_only_complete_unlisted_clones_with_their_origin(
            self, boost, fixture_tap_src, tmp_path):
        assert registry.unlisted_clones() == []          # no repos/ at all
        keep = _copy_tap(fixture_tap_src, tmp_path, "ul-keep")
        lost = _copy_tap(fixture_tap_src, tmp_path, "ul-lost")
        boost("tap", keep)
        boost("tap", lost)
        (paths.repos_dir() / "o__half" / ".git").mkdir(parents=True)
        (paths.repos_dir() / "stray.txt").write_text("x", encoding="utf-8")
        # A killed re-clone's staging copy is a full clone, and not a tap.
        subprocess.run(["git", "clone", "-q", str(keep),
                        str(paths.repos_dir() / ("ul-keep"
                                                 + registry.RECLONE_SUFFIX))],
                       check=True, capture_output=True)
        assert registry.unlisted_clones() == []
        _drop_from_config("ul-lost")
        clone = paths.repos_dir() / "ul-lost"
        assert registry.unlisted_clones() == [(clone, str(lost))]
        assert registry.readd_hint(clone, str(lost)) == (
            "`boost tap %s`" % util.shell_arg(str(lost)))
        assert registry.unlisted_clone_line(clone, str(lost)) == (
            "%s is a tap clone no configured tap lists, so boost reads "
            "nothing from it — re-add it with `boost tap %s`, or delete the "
            "directory" % (paths.tilde(clone), util.shell_arg(str(lost))))

    def test_a_clone_without_an_origin_gets_words_not_a_command(self, sandbox):
        clone = paths.repos_dir() / "nourl"
        assert registry.readd_hint(clone, "") == (
            "re-tap nourl from its original source (its URL was not recorded)")
        assert registry.readd_hint(paths.repos_dir() / "o__r", "") == (
            "`boost tap o/r`")

    def test_without_git_none_are_reported(self, boost, fixture_tap_src,
                                           tmp_path, monkeypatch):
        boost("tap", _copy_tap(fixture_tap_src, tmp_path, "ul-nogit"))
        _drop_from_config("ul-nogit")
        monkeypatch.setattr(gitutil, "has_git", lambda: False)
        assert registry.unlisted_clones() == []

    def test_corrupt_config_names_each_clone_and_doctor_stays_red_until_all(
            self, boost, fixture_tap_src, tmp_path):
        one = _copy_tap(fixture_tap_src, tmp_path, "ul-one")
        two = _copy_tap(fixture_tap_src, tmp_path, "ul-two")
        boost("tap", one)
        boost("tap", two)
        paths.config_path().write_text('{"taps": [', encoding="utf-8")
        flat = " ".join(boost("doctor", expect=1).out.split())
        assert ("the 2 tap clones on disk are not listed. Repair the file, "
                "or re-add them with `boost tap %s`, `boost tap %s`; the next "
                "write" % (util.shell_arg(str(one)), util.shell_arg(str(two)))
                in flat)
        # Following the advice for one tap is not the whole remedy.
        boost("tap", one)
        r = boost("doctor", "--json", expect=1)
        import json
        rows = [c for c in json.loads(r.out)["checks"]
                if c["status"] == "issue"]
        assert [(c["name"], c["message"]) for c in rows] == [
            ("tap", registry.unlisted_clone_line(
                paths.repos_dir() / "ul-two", str(two)))]
        for dry in ([], ["--dry-run"]):
            r = boost("heal", *dry, expect=1)
            text = " ".join(r.out.split())
            assert "re-add it with `boost tap %s`" % util.shell_arg(
                str(two)) in text
            assert "nothing to heal" not in text
        boost("tap", two)
        r = boost("doctor")
        assert "2 taps cloned" in r.out
