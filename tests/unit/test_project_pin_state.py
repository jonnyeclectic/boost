# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`store.set_project_pin` / `store.project_carried_state`: a project pin holds.

`boost pin` on a skill installed `--local` writes the flag into the repo's
own lock, and a forced re-install rebuilds that row from scratch — so the
pin has to be carried, or `boost reinstall` silently unpins it.
"""
from __future__ import annotations

from boost_cli.core import projectlock, store


def test_carried_state_keeps_a_set_pin_and_commit_pin():
    assert store.project_carried_state(
        {"pinned": True, "commit_pin": "abc", "version": "1.0.0"}) == {
            "pinned": True, "commit_pin": "abc"}


def test_carried_state_drops_an_unset_pin():
    assert store.project_carried_state({"pinned": False}) == {}
    assert store.project_carried_state({"version": "1.0.0"}) == {}
    assert store.project_carried_state(None) == {}


def test_set_project_pin_writes_and_clears(sandbox, tmp_path):
    base = tmp_path / "repo"
    base.mkdir()
    projectlock.set_skill(base, "x", {"version": "1.0.0", "commit_pin": "c1"})
    row = store.set_project_pin(base, "x", True)
    assert row == {"version": "1.0.0", "commit_pin": "c1", "pinned": True}
    assert projectlock.get_skill(base, "x") == row
    row = store.set_project_pin(base, "x", False)
    assert row == {"version": "1.0.0"}
    assert projectlock.get_skill(base, "x") == {"version": "1.0.0"}


def test_set_project_pin_on_a_missing_row_writes_nothing(sandbox, tmp_path):
    base = tmp_path / "repo"
    base.mkdir()
    assert store.set_project_pin(base, "x", True) is None
    assert not projectlock.exists(base)


def test_a_forced_project_install_keeps_the_pin(boost, tapped, tmp_path):
    from boost_cli.core import catalog, scopes
    base = tmp_path / "pin-repo"
    (base / ".git").mkdir(parents=True)
    base = base.resolve()
    entry = next(e for e in catalog.find("brainstorming"))
    store.install(entry, scope=scopes.SCOPE_PROJECT, base=base)
    store.set_project_pin(base, "brainstorming", True)
    store.install(entry, force=True, scope=scopes.SCOPE_PROJECT, base=base)
    row = projectlock.get_skill(base, "brainstorming")
    assert row["pinned"] is True
    store.set_project_pin(base, "brainstorming", False)
    store.install(entry, force=True, scope=scopes.SCOPE_PROJECT, base=base)
    assert "pinned" not in projectlock.get_skill(base, "brainstorming")
