# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: user-set lock fields survive a re-install, and pins hold.

A re-install rebuilds its lock entry from scratch, so any user-set field the
builder does not name is lost. ``commit_pin`` was: ``boost reinstall`` of a
commit-pinned item dropped the integrity pin silently, and installed whatever
the tap had moved to under a version pin nobody set.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from boost_cli.core import catalog, gitutil, integrity, lockfile, registry, store

PIN = "f" * 40


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    src = tmp_path / "lockfield-tap"
    shutil.copytree(fixture_tap_src, src)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _rule_entry(tap):
    src = tap.path / "rules" / "keep.mdc"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: keep-rule\n---\n\nKeep it.\n", encoding="utf-8")
    return {"name": "keep-rule", "kind": "rule", "tap": tap.name,
            "version": "1.0.0", "rel_dir": "rules", "skill_md": "rules/keep.mdc",
            "description": "keep", "curated": False, "meta": {}}


def _workflow_entry(tap):
    src = tap.path / "commands" / "keep.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: keep-flow\ndescription: keep\n---\n\nKeep.\n",
                   encoding="utf-8")
    return {"name": "keep-flow", "kind": "workflow", "tap": tap.name,
            "version": "1.0.0", "rel_dir": "commands",
            "skill_md": "commands/keep.md", "description": "keep",
            "curated": False, "meta": {}}


def _commit_pin(kind, name):
    """What `boost pin NAME --commit` writes: the version pin, then the commit."""
    found = lockfile.find_any(name)
    assert found is not None and found[0] == kind
    # Two writes, as `boost pin --commit` makes them: set_commit_pin writes
    # only `commit_pin`, onto the row as the lock holds it.
    lockfile.update_entry(kind, name, lambda row: row.update(pinned=True))
    integrity.set_commit_pin(name, found[1], kind=kind)
    return lockfile.find_any(name)[1]


class TestCarriedUserState:
    def test_nothing_to_carry(self):
        assert store.carried_user_state(None) == {}
        assert store.carried_user_state({}) == {}
        assert store.carried_user_state({"commit_pin": ""}) == {}
        assert store.carried_user_state({"pinned": True}) == {}

    def test_commit_pin_is_carried(self):
        assert store.carried_user_state({"commit_pin": "abc"}) == {
            "commit_pin": "abc"}

    @pytest.mark.parametrize("kind", ["skill", "rule", "workflow"])
    def test_forced_reinstall_keeps_the_commit_pin(self, tap, kind):
        entry = {"skill": lambda: catalog.resolve_one("brainstorming"),
                 "rule": lambda: _rule_entry(tap),
                 "workflow": lambda: _workflow_entry(tap)}[kind]()
        store.install(entry)
        before = _commit_pin(kind, entry["name"])
        assert before["commit_pin"] == gitutil.head_commit(tap.path)
        before["tags"] = ["kept"] if kind == "skill" else []
        lockfile.set_entry(kind, entry["name"], before)
        store.install(entry, force=True)
        after = lockfile.find_any(entry["name"])[1]
        assert after["commit_pin"] == before["commit_pin"]
        assert after["pinned"] is True
        assert integrity.commit_status(entry["name"], after) == integrity.STATUS_OK
        if kind == "skill":
            assert after["tags"] == ["kept"]

    def test_reimport_keeps_the_commit_pin(self, sandbox, tmp_path):
        src = tmp_path / "keep-local"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: keep-local\n---\n\nv1\n",
                                      encoding="utf-8")
        store.install_from_path(src)
        lk = lockfile.get_skill("keep-local")
        lk["commit_pin"] = PIN
        lockfile.set_skill("keep-local", lk)
        store.install_from_path(src, force=True)
        assert lockfile.get_skill("keep-local")["commit_pin"] == PIN


class TestMovedOffCommitPin:
    def test_no_pin(self, tap):
        assert store.moved_off_commit_pin({}, tap.name) is None

    def test_on_the_pin(self, tap):
        head = gitutil.head_commit(tap.path)
        assert store.moved_off_commit_pin({"commit_pin": head}, tap.name) is None

    def test_off_the_pin_returns_the_head(self, tap):
        head = gitutil.head_commit(tap.path)
        assert store.moved_off_commit_pin({"commit_pin": PIN}, tap.name) == head

    def test_unknown_tap_fails_closed(self, sandbox):
        assert store.moved_off_commit_pin({"commit_pin": PIN}, "no-such-tap") == ""


class TestReinstallPinHold:
    def test_unpinned_is_never_held(self, tap):
        entry = catalog.resolve_one("brainstorming")
        store.install(entry)
        assert store.reinstall_pin_hold(
            "skill", lockfile.get_skill("brainstorming"), cat_entry=entry) is None

    def test_pinned_same_content_may_reinstall(self, tap):
        entry = catalog.resolve_one("brainstorming")
        store.install(entry)
        lk = _commit_pin("skill", "brainstorming")
        assert store.reinstall_pin_hold("skill", lk, cat_entry=entry) is None
        assert store.reinstall_pin_hold("skill", lk) is None

    def test_commit_pinned_tap_moved_is_held(self, tap):
        entry = catalog.resolve_one("brainstorming")
        store.install(entry)
        lk = _commit_pin("skill", "brainstorming")
        _git(tap.path, "commit", "-q", "--allow-empty", "-m", "move")
        head = gitutil.head_commit(tap.path)
        why = store.reinstall_pin_hold("skill", lk, cat_entry=entry)
        assert why == "commit-pinned at %s, and %s is now at %s" % (
            lk["commit_pin"][:12], tap.name, head[:12])

    def test_commit_pinned_unreadable_tap_is_held(self, tap):
        entry = catalog.resolve_one("brainstorming")
        store.install(entry)
        lk = _commit_pin("skill", "brainstorming")
        why = store.reinstall_pin_hold("skill", lk,
                                       cat_entry=dict(entry, tap="gone-tap"))
        assert why == ("commit-pinned at %s, and gone-tap is now at an "
                       "unreadable commit" % lk["commit_pin"][:12])

    def test_version_pinned_changed_source_is_held(self, tap):
        entry = catalog.resolve_one("brainstorming")
        store.install(entry)
        lk = lockfile.get_skill("brainstorming")
        lk["pinned"] = True
        lockfile.set_skill("brainstorming", lk)
        md = tap.path / entry["rel_dir"] / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "\nnew upstream\n",
                      encoding="utf-8")
        assert store.reinstall_pin_hold("skill", lk, cat_entry=entry) == (
            "pinned at v%s, and its source has changed since" % lk["version"])

    def test_rule_changed_source_is_held(self, tap):
        entry = _rule_entry(tap)
        store.install(entry)
        lk = lockfile.get_rule("keep-rule")
        lk["pinned"] = True
        assert store.reinstall_pin_hold("rule", lk, cat_entry=entry) is None
        (tap.path / "rules" / "keep.mdc").write_text(
            "---\nname: keep-rule\n---\n\nChanged.\n", encoding="utf-8")
        assert store.reinstall_pin_hold("rule", lk, cat_entry=entry) == (
            "pinned at v1.0.0, and its source has changed since")

    def test_local_source(self, sandbox, tmp_path):
        src = tmp_path / "hold-local"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: hold-local\n---\n\nv1\n",
                                      encoding="utf-8")
        store.install_from_path(src)
        lk = lockfile.get_skill("hold-local")
        lk["pinned"] = True
        assert store.reinstall_pin_hold("skill", lk, src=src) is None
        (src / "SKILL.md").write_text("---\nname: hold-local\n---\n\nv2\n",
                                      encoding="utf-8")
        assert store.reinstall_pin_hold("skill", lk, src=src) is not None
        lk["pinned"] = False
        assert store.reinstall_pin_hold("skill", lk, src=src) is None


class TestRepairHonoursCommitPin:
    def test_sync_declines_repair_off_the_commit_pin(self, tap):
        entry = catalog.resolve_one("brainstorming")
        store.install(entry)
        _commit_pin("skill", "brainstorming")
        _git(tap.path, "commit", "-q", "--allow-empty", "-m", "move")
        shutil.rmtree(store.skill_store_dir("brainstorming"))
        actions = store.sync_apply(store.sync_plan())
        assert any("brainstorming is pinned and its tap source has moved"
                   in a for a in actions)
        assert lockfile.get_skill("brainstorming")["commit_pin"]

    def test_commit_pin_alone_blocks_repair(self, tap):
        entry = {"tap": tap.name, "commit_pin": PIN}
        assert store._pin_blocks_repair(entry, lambda: None) is True

    def test_unpinned_never_hashes(self, tap):
        def boom():
            raise AssertionError("hashed an unpinned entry")
        assert store._pin_blocks_repair({"tap": tap.name}, boom) is False


class TestSplitSidelined:
    def test_split(self):
        skills = {"b": {"sidelined_by": "profile"}, "a": {},
                  "c": {"sidelined_by": "focus"}, "d": {"sidelined_by": ""}}
        active, aside = lockfile.split_sidelined(skills)
        assert active == {"a": {}, "d": {"sidelined_by": ""}}
        assert aside == ["b", "c"]
