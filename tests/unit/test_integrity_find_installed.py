# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`integrity.find_installed`, `installed_names`, `skill_modified`, `catalog.for_tap`.

The core helpers both the CLI and the MCP tools resolve "is it installed, and
is it intact" through, so the two surfaces cannot drift apart again.
"""
from __future__ import annotations

from pathlib import Path

from boost_cli.core import catalog, integrity, lockfile, paths, projectlock, util


def _skill(name: str, tap: str = "tap-a", **extra) -> dict:
    d = paths.store_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: %s\n---\nbody\n" % name,
                                encoding="utf-8")
    entry = {"tap": tap, "version": "1.0.0", "sha256": util.sha256_dir(d),
             **extra}
    lockfile.set_skill(name, entry)
    return entry


class TestForTap:
    def test_no_qualifier_keeps_the_entry(self):
        e = {"tap": "owner/a"}
        assert catalog.for_tap(e, None) is e

    def test_a_matching_qualifier_keeps_it(self):
        e = {"tap": "owner/a"}
        assert catalog.for_tap(e, "owner/a") is e
        assert catalog.for_tap(e, "a") is e

    def test_another_tap_drops_it(self):
        assert catalog.for_tap({"tap": "owner/a"}, "b") is None
        assert catalog.for_tap({}, "a") == {}
        assert catalog.for_tap(None, "a") is None


class TestFindInstalled:
    def test_bare_and_qualified_names_find_the_user_install(self, sandbox):
        entry = _skill("s1", tap="tap-a")
        assert integrity.find_installed("s1") == ("skill", entry, None)
        assert integrity.find_installed("tap-a:s1") == ("skill", entry, None)
        assert integrity.find_installed("tap-b:s1") is None
        assert integrity.find_installed("nope") is None

    def test_a_rule_answers_with_its_kind(self, sandbox):
        lockfile.set_rule("r1", {"kind": "rule", "tap": "tap-r"})
        kind, entry, base = integrity.find_installed("tap-r:r1")
        assert (kind, entry["tap"], base) == ("rule", "tap-r", None)

    def test_a_project_skill_answers_with_its_base(self, sandbox):
        base = Path.cwd()
        projectlock.set_skill(base, "p1", {"tap": "tap-p", "version": "2"})
        kind, entry, got = integrity.find_installed("p1")
        assert (kind, entry["tap"], str(got)) == ("skill", "tap-p", str(base))
        assert integrity.find_installed("tap-p:p1")[0] == "skill"
        assert integrity.find_installed("tap-q:p1") is None

    def test_the_user_lock_answers_first(self, sandbox):
        entry = _skill("both", tap="tap-u")
        projectlock.set_skill(Path.cwd(), "both", {"tap": "tap-p"})
        assert integrity.find_installed("both") == ("skill", entry, None)
        # ...unless the qualifier names the project's tap.
        found = integrity.find_installed("tap-p:both")
        assert found is not None and found[1]["tap"] == "tap-p"
        assert str(found[2]) == str(Path.cwd())


class TestInstalledNames:
    def test_all_kinds_and_both_scopes(self, sandbox):
        _skill("s1")
        lockfile.set_rule("r1", {"kind": "rule", "tap": "t"})
        lockfile.set_workflow("w1", {"kind": "workflow", "tap": "t"})
        projectlock.set_skill(Path.cwd(), "p1", {"tap": "t"})
        assert integrity.installed_names() == {"s1", "r1", "w1", "p1"}

    def test_empty(self, sandbox):
        assert integrity.installed_names() == set()


class TestSkillModified:
    def test_intact_then_edited(self, sandbox):
        entry = _skill("s1")
        assert integrity.skill_modified("s1", entry) is False
        (paths.store_dir() / "s1" / "SKILL.md").write_text("x", encoding="utf-8")
        assert integrity.skill_modified("s1", entry) is True

    def test_unlocked_and_missing_are_not_drift(self, sandbox):
        entry = _skill("s1")
        (paths.store_dir() / "s1" / "SKILL.md").write_text("x", encoding="utf-8")
        assert integrity.skill_modified("s1", {**entry, "sha256": ""}) is False
        assert integrity.skill_modified("gone", entry) is False
        assert integrity.skill_modified("s1", None) is False
        assert integrity.skill_modified("s1", {}) is False

    def test_a_quarantined_copy_is_asked_too(self, sandbox):
        # Doctor called the machine healthy over an edited quarantined copy
        # that `boost verify` failed.
        entry = {**_skill("s1"), "quarantined": True}
        assert integrity.skill_modified("s1", entry) is False
        (paths.store_dir() / "s1" / "SKILL.md").write_text("x", encoding="utf-8")
        assert integrity.skill_modified("s1", entry) is True
