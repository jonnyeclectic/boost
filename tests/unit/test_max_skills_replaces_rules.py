# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""At ``max_skills``, replacing an installed rule or workflow adds nothing.

A skill's upgrade or reinstall was already exempt (`_count_others`), but
`_install_rule` and `_install_workflow` passed the bare skill count, so at
exactly the cap `boost update` held back every rule and workflow upgrade and
`boost reinstall` of one exited 1 -- while the same call for a skill went
through. A fresh rule or workflow is still weighed against the cap.
"""
from __future__ import annotations

import pytest

from boost_cli.core import catalog, lockfile, policy, registry, store
from boost_cli.errors import BoostError


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


def _item(tap, kind, name, rel, text):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(text, encoding="utf-8")
    return {"name": name, "kind": kind, "tap": tap.name, "version": "1.0.0",
            "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
            "description": "a %s" % kind, "curated": False,
            "meta": {"name": name}}


def _rule(tap, name="strict"):
    return _item(tap, "rule", name, "rules/%s.mdc" % name,
                 "---\ndescription: be strict\n---\n\nNo shortcuts.\n")


def _workflow(tap, name="deploy"):
    return _item(tap, "workflow", name, "commands/%s.md" % name,
                 "---\ndescription: deploy it\n---\n\nShip it.\n")


@pytest.fixture()
def at_cap(tap):
    """Two skills installed and ``max_skills`` set to exactly two."""
    store.install(catalog.resolve_one("brainstorming"))
    store.install(catalog.resolve_one("cowboy-coding"))
    assert len(lockfile.installed()) == 2


@pytest.mark.parametrize("make", [_rule, _workflow], ids=["rule", "workflow"])
class TestReplacingAtTheCap:
    def test_reinstall_of_an_installed_item_goes_through(self, tap, at_cap,
                                                         make):
        item = make(tap)
        store.install(item)
        policy.save({"max_skills": 2})
        store.install(item, force=True)
        getter = (lockfile.get_rule if item["kind"] == "rule"
                  else lockfile.get_workflow)
        assert getter(item["name"]) is not None

    def test_a_fresh_item_is_still_refused(self, tap, at_cap, make):
        item = make(tap, name="fresh")
        policy.save({"max_skills": 2})
        with pytest.raises(BoostError) as ei:
            store.install(item)
        assert ei.value.message == (
            "policy blocks installing fresh: max_skills limit (2) reached")
        assert ei.value.hint == "inspect with `boost policy list`"

    def test_replacing_over_the_cap_is_still_refused(self, tap, at_cap, make):
        # Exempt exactly as a skill is: replacing adds none, but a cap already
        # exceeded (lowered under what is installed) still refuses.
        item = make(tap)
        store.install(item)
        policy.save({"max_skills": 1})
        with pytest.raises(BoostError) as ei:
            store.install(item, force=True)
        assert ei.value.message == (
            "policy blocks installing %s: max_skills limit (1) reached"
            % item["name"])


def test_count_others_takes_the_replaced_record_from_the_caller():
    skills = {"a": {}, "b": {}}
    assert store._count_others(skills, "r", replaces=True) == 1
    assert store._count_others(skills, "r", replaces=False) == 2
    # An explicit answer wins over the name lookup in both directions.
    assert store._count_others(skills, "a", replaces=False) == 2
    assert store._count_others(skills, "r") == 2
    assert store._count_others(skills, "a") == 1
