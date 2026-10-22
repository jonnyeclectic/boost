# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a held store copy is not "missing", and quarantine owns it.

The functional suite (tests/functional/test_item_state_scope.py) drives these
through the CLI; the mutation gate runs tests/unit only, so the core helpers
are pinned here too — without this file every mutant in them survived.
"""
from __future__ import annotations

import os

import pytest

from boost_cli.core import catalog, lockfile, paths, registry, store, util


@pytest.fixture()
def installed(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    store.install(catalog.resolve_one("brainstorming"))
    return "brainstorming"


def _link(name: str):
    return paths.home() / ".claude" / "skills" / name


class TestMissingFromStore:
    def test_store_dir_present_is_not_missing(self, sandbox):
        store.skill_store_dir("x").mkdir(parents=True)
        assert store.missing_from_store("x", {}) is False
        assert store.missing_from_store("x", None) is False

    def test_store_dir_absent_is_missing(self, sandbox):
        assert store.missing_from_store("y", {}) is True
        assert store.missing_from_store("y", None) is True
        assert store.missing_from_store("y", {"quarantined": True}) is True

    def test_a_held_row_is_not_missing(self, sandbox):
        assert store.missing_from_store(
            "y", {store.HELD_KEY: "/h/y"}) is False

    def test_quarantine_and_sideline_are_not_missing(self, installed):
        store.sideline(installed, "focus")
        assert store.missing_from_store(
            installed, lockfile.get_skill(installed)) is False
        store.unsideline(installed)
        store.quarantine_skill(installed, lockfile.get_skill(installed))
        assert store.missing_from_store(
            installed, lockfile.get_skill(installed)) is False


class TestHeldReason:
    def test_quarantine_wins_over_a_sideline(self):
        assert store.held_reason(
            "x", {"quarantined": True, "sidelined_by": "focus"}) == (
            "quarantined", "`boost quarantine --release x` puts it back")

    @pytest.mark.parametrize(("by", "back"), [
        ("focus", "`boost focus --clear` puts it back"),
        ("context", "`boost context disable` puts it back"),
        ("profile", "a `boost profile use` that includes it puts it back"),
        ("other", "relinking it puts it back"),
    ])
    def test_sideline_names_its_mechanism(self, by, back):
        assert store.held_reason("x", {"sidelined_by": by}) == (
            "sidelined by `boost %s`" % by, back)

    def test_unknown_sideline(self):
        assert store.held_reason("x", {}) == (
            "sidelined", "relinking it puts it back")
        assert store.held_reason("x", {"quarantined": False}) == (
            "sidelined", "relinking it puts it back")

    def test_held_refusal_uses_it(self):
        err = store.held_refusal("x", {store.HELD_KEY: "/h/x",
                                       "quarantined": True})
        assert err is not None
        assert str(err) == "x is quarantined — its store copy is held aside"
        assert err.hint == "`boost quarantine --release x` puts it back first"
        assert store.held_refusal("x", {"quarantined": True}) is None
        assert store.held_refusal("x", None) is None


class TestQuarantineOwnsTheHeldCopy:
    def test_quarantine_drops_the_sideline(self, installed):
        store.sideline(installed, "focus")
        assert lockfile.get_skill(installed)["sidelined_by"] == "focus"
        store.quarantine_skill(installed, lockfile.get_skill(installed))
        entry = lockfile.get_skill(installed)
        assert entry["quarantined"] is True
        assert "sidelined_by" not in entry
        assert store.is_held(entry)

    def test_unsideline_of_a_quarantined_row_restores_nothing(self, installed):
        store.quarantine_skill(installed, lockfile.get_skill(installed))

        def both(e):
            e["sidelined_by"] = "focus"
        lockfile.update_skill(installed, both)
        res = store.unsideline(installed)
        assert res.name == installed
        assert res.linked == []
        assert res.dest == store.skill_store_dir(installed)
        assert (res.conflicts, res.unwritable) == ([], [])
        entry = lockfile.get_skill(installed)
        assert "sidelined_by" not in entry
        assert entry["quarantined"] is True
        assert entry["agents"] == []
        assert store.is_held(entry)
        assert not os.path.lexists(store.skill_store_dir(installed))
        assert (store.held_copy_dir(installed) / "SKILL.md").is_file()
        assert not os.path.lexists(_link(installed))

    def test_unsideline_of_a_plain_row_still_relinks(self, installed):
        store.sideline(installed, "focus")
        res = store.unsideline(installed)
        assert "claude-code" in res.linked
        assert _link(installed).is_symlink()
        assert store.skill_store_dir(installed).is_dir()


class TestRefreshKeepsTheSideline:
    """`update` and `reinstall` refresh a sidelined skill's content and keep
    it aside; a plain `install --force` is still the one that brings it back."""

    @pytest.mark.parametrize("via", ["update", "reinstall"])
    def test_refresh_lands_in_the_held_copy(self, installed, via):
        from boost_cli.core import integrity
        store.sideline(installed, "context")
        res = store.install(catalog.resolve_one(installed), force=True,
                            via=via)
        assert res.linked == []
        entry = lockfile.get_skill(installed)
        assert entry["sidelined_by"] == "context"
        assert entry["agents"] == []
        assert entry[store.HELD_KEY] == str(store.held_copy_dir(installed))
        assert not os.path.lexists(_link(installed))
        assert not os.path.lexists(store.skill_store_dir(installed))
        assert (store.held_copy_dir(installed) / "SKILL.md").is_file()
        assert integrity.status(installed, entry) == integrity.STATUS_OK

    def test_a_plain_install_still_relinks(self, installed):
        store.sideline(installed, "focus")
        res = store.install(catalog.resolve_one(installed), force=True)
        assert "claude-code" in res.linked
        assert "sidelined_by" not in lockfile.get_skill(installed)
        assert _link(installed).is_symlink()

    def test_keep_sideline_needs_a_sidelined_unquarantined_row(self, installed):
        res = store.InstallResult(installed, store.skill_store_dir(installed),
                                  linked=["claude-code"])
        for existing in (None, {}, {"sidelined_by": ""},
                         {"sidelined_by": "focus", "quarantined": True}):
            assert store.keep_sideline(installed, existing, res) is False
        assert res.linked == ["claude-code"]
        assert _link(installed).is_symlink()
        assert store.keep_sideline(installed, {"sidelined_by": "profile"},
                                   res) is True
        assert res.linked == []
        assert lockfile.get_skill(installed)["sidelined_by"] == "profile"
        assert not os.path.lexists(_link(installed))

    def test_refresh_vias(self):
        assert frozenset({"update", "reinstall"}) == store.REFRESH_VIAS


class TestFocusBookkeeping:
    def test_sideline_priors_records_only_other_mechanisms(self):
        inst = {"a": {"sidelined_by": "context"}, "b": {"sidelined_by": "focus"},
                "c": {}, "d": {"sidelined_by": "profile"}}
        assert store.sideline_priors(inst, ["a", "b", "c", "x"]) == {
            "a": "context"}
        assert store.sideline_priors(inst, ["d"], None) == {"d": "profile"}
        assert store.sideline_priors({}, []) == {}

    def test_sideline_priors_carries_the_session_record(self):
        inst = {"a": {"sidelined_by": "focus"}, "b": {"sidelined_by": "profile"}}
        assert store.sideline_priors(
            inst, ["b"], {"a": "context", "z": ""}) == {
            "a": "context", "b": "profile"}
        # A fresh flag outranks a carried one for the same name.
        assert store.sideline_priors(inst, ["b"], {"b": "context"}) == {
            "b": "profile"}

    def test_focus_displaced(self):
        inst = {"a": {}, "b": {"sidelined_by": "profile"},
                "c": {"quarantined": True}, "d": {"sidelined_by": ""}}
        assert store.focus_displaced(["a", "b", "c", "d", "gone"], inst) == [
            ("b", "sidelined by `boost profile`"),
            ("c", "quarantined"),
            ("gone", "not installed")]
        assert store.focus_displaced([], inst) == []


class TestHeldCopiesForSnapshots:
    def test_held_copies_names_only_held_rows(self, installed):
        assert store.held_copies() == {}
        store.sideline(installed, "focus")
        assert store.held_copies() == {
            installed: store.held_copy_dir(installed)}

    def test_unhold_lost_copies(self, installed):
        assert store.unhold_lost_copies() == []
        store.sideline(installed, "focus")
        # Copy present: nothing lost.
        assert store.unhold_lost_copies() == []
        assert lockfile.get_skill(installed)["sidelined_by"] == "focus"
        util.rmtree(store.held_copy_dir(installed))
        assert store.unhold_lost_copies() == [installed]
        entry = lockfile.get_skill(installed)
        assert "sidelined_by" not in entry
        assert store.HELD_KEY not in entry
        assert store.missing_from_store(installed, entry) is True

    def test_a_quarantined_row_keeps_its_hold(self, installed):
        store.quarantine_skill(installed, lockfile.get_skill(installed))
        util.rmtree(store.held_copy_dir(installed))
        assert store.unhold_lost_copies() == []
        assert store.is_held(lockfile.get_skill(installed))
