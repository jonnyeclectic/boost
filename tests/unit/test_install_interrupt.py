# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""An install interrupted after its copy must not strand an unrecorded skill.

Measured before this fix: a Ctrl-C during `source_updated_at` (an unshallow
fetch of up to a minute on a real tap) left `~/.agents/skills/tdd-workflow`
on disk with no lock row. The rerun refused ("already in the store ... the
lock file does not record it"), and the `boost sync` its hint suggested
re-filed it as a `local` 0.0.0 skill that `boost update` never moves again.
"""
from __future__ import annotations

import shutil

import pytest

from boost_cli.core import catalog, lockfile, registry, store


@pytest.fixture()
def tap(sandbox, fixture_tap_src, tmp_path):
    """A tap with a name no other test module uses."""
    src = tmp_path / "install-interrupt-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    t = registry.add(str(src))
    catalog.rebuild_tap(t)
    return t


def _interrupt(monkeypatch, target: str) -> None:
    def boom(*_a, **_k):
        raise KeyboardInterrupt
    monkeypatch.setattr(store, target, boom)


class TestInterruptedInstall:
    def test_dates_the_source_before_copying(self, tap, monkeypatch):
        order: list[str] = []
        real_copy, real_dated = store._copy_skill, store.source_updated_at
        monkeypatch.setattr(store, "_copy_skill", lambda *a, **k: (
            order.append("copy"), real_copy(*a, **k))[1])
        monkeypatch.setattr(store, "source_updated_at", lambda *a, **k: (
            order.append("date"), real_dated(*a, **k))[1])
        store.install(catalog.resolve_one("tdd-workflow"))
        assert order == ["date", "copy"]

    def test_interrupt_while_dating_writes_nothing(self, tap, monkeypatch):
        _interrupt(monkeypatch, "source_updated_at")
        with pytest.raises(KeyboardInterrupt):
            store.install(catalog.resolve_one("tdd-workflow"))
        assert not store.skill_store_dir("tdd-workflow").exists()
        assert lockfile.get_skill("tdd-workflow") is None

    @pytest.mark.parametrize("step", ["link_agents", "linked_agents"])
    def test_interrupt_after_the_copy_rolls_back(self, tap, monkeypatch, step):
        real = getattr(store, step)
        _interrupt(monkeypatch, step)
        with pytest.raises(KeyboardInterrupt):
            store.install(catalog.resolve_one("tdd-workflow"))
        assert not store.skill_store_dir("tdd-workflow").exists()
        assert lockfile.get_skill("tdd-workflow") is None
        # Put back only the patched step: `monkeypatch.undo()` would also undo
        # the sandbox's $HOME and point the rerun at the real one.
        monkeypatch.setattr(store, step, real)
        assert store.linked_agents("tdd-workflow") == []
        # ...so a plain rerun finishes, with the tap's provenance.
        store.install(catalog.resolve_one("tdd-workflow"))
        row = lockfile.get_skill("tdd-workflow")
        assert row is not None
        assert row["tap"] == tap.name
        assert store.skill_store_dir("tdd-workflow").is_dir()

    def test_an_upgrade_keeps_its_copy_and_row(self, tap, monkeypatch):
        store.install(catalog.resolve_one("tdd-workflow"))
        before = lockfile.get_skill("tdd-workflow")
        _interrupt(monkeypatch, "linked_agents")
        with pytest.raises(KeyboardInterrupt):
            store.install(catalog.resolve_one("tdd-workflow"), force=True)
        assert store.skill_store_dir("tdd-workflow").is_dir()
        assert lockfile.get_skill("tdd-workflow") == before

    def test_an_ordinary_error_rolls_back_too(self, tap, monkeypatch):
        def fail(*_a, **_k):
            raise OSError("disk full")
        monkeypatch.setattr(store, "link_agents", fail)
        with pytest.raises(OSError, match=r"^disk full$"):
            store.install(catalog.resolve_one("tdd-workflow"))
        assert not store.skill_store_dir("tdd-workflow").exists()

    def test_a_recorded_skill_whose_dir_vanished_is_not_rolled_back(
            self, tap, monkeypatch):
        # dest is absent (a "fresh" copy) but the lock still records the
        # skill: the row is the user's record, and the copy it now points at
        # is left for `boost doctor` rather than deleted.
        store.install(catalog.resolve_one("tdd-workflow"))
        before = lockfile.get_skill("tdd-workflow")
        shutil.rmtree(store.skill_store_dir("tdd-workflow"))
        _interrupt(monkeypatch, "linked_agents")
        with pytest.raises(KeyboardInterrupt):
            store.install(catalog.resolve_one("tdd-workflow"), force=True)
        assert store.skill_store_dir("tdd-workflow").is_dir()
        assert lockfile.get_skill("tdd-workflow") == before
