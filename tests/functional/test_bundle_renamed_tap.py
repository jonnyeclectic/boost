# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: a Boostfile tapping a renamed row by its new name.

A machine that tapped a catalogue row before the repository was renamed holds
it under the old name, and `registry.add` refuses to clone it again under the
new one. `boost bundle install` reported that refusal as a failed tap line, so
a Boostfile dumped on a machine that tapped the new name — `tap NEW URL` and
`skill NEW:x` — installed nothing here. The line is already held, and its
skill lines resolve against the tap that holds it.

Offline: the catalogue is monkeypatched, the old-name tap is a copy of the
fixture repo at the path a clone would take, and a clone is an error.
"""
from __future__ import annotations

import shutil

import pytest

from boost_cli.core import catalog, config, gitutil, lockfile, registry

OLD, NEW = "oldowner/claude-skills", "newowner/ai-skills"
GH = "https://github.com/"
RENAMED = "%s already tapped as %s (one repository, renamed upstream)" % (
    NEW, OLD)


@pytest.fixture
def held_old(boost, sandbox, fixture_tap_src, monkeypatch):
    """The repository tapped under OLD; the catalogue now calls it NEW."""
    rows = [{"name": NEW, "url": GH + NEW, "type": "skill",
             "category": "infra", "formerly": [OLD]}]
    monkeypatch.setattr(config, "load_registry_catalog", lambda: list(rows))
    cfg = config.load()
    cfg["taps"] = [{"name": OLD, "url": GH + OLD, "curated": False}]
    config.save(cfg)
    tap = registry.get(OLD)
    tap.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture_tap_src, tap.path)
    catalog.rebuild_tap(tap)

    def no_clone(*_a, **_k):
        raise AssertionError("cloned the held repository a second time")
    monkeypatch.setattr(gitutil, "clone_shallow", no_clone)
    return tap


def _boostfile(sandbox, *lines):
    path = sandbox / "Boostfile"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _tap_names():
    return [t["name"] for t in config.get("taps")]


def test_the_new_name_is_held_and_its_skill_installs(boost, sandbox,
                                                     held_old):
    bf = _boostfile(sandbox, "tap %s %s" % (NEW, GH + NEW),
                    "skill %s:brainstorming" % NEW)
    r = boost("bundle", "install", bf)
    assert RENAMED in r.out
    assert "failed" not in r.out + r.err
    assert "Installed 1 skill" in r.out
    assert "added" not in r.out          # no tap counted as new
    assert lockfile.get_skill("brainstorming")["tap"] == OLD
    assert _tap_names() == [OLD]


def test_a_bare_tap_line_is_held_too(boost, sandbox, held_old):
    bf = _boostfile(sandbox, "tap %s" % NEW, "skill %s:brainstorming" % NEW)
    r = boost("bundle", "install", bf)
    assert RENAMED in r.out
    assert lockfile.get_skill("brainstorming")["tap"] == OLD


def test_a_second_run_finds_it_present_not_drifted(boost, sandbox, held_old):
    """The lock records OLD; the line says NEW. One repository, so the
    reproduction is faithful rather than "installed from OLD, wants NEW"."""
    bf = _boostfile(sandbox, "tap %s" % NEW, "skill %s:brainstorming" % NEW)
    boost("bundle", "install", bf)
    r = boost("bundle", "install", bf)
    assert "1 already present" in r.out
    assert "differ" not in r.out


def test_the_dry_run_previews_what_the_run_does(boost, sandbox, held_old):
    bf = _boostfile(sandbox, "tap %s" % NEW, "skill %s:brainstorming" % NEW)
    r = boost("bundle", "install", bf, "--dry-run")
    assert RENAMED in r.out
    assert "would tap" not in r.out
    assert "cannot resolve yet" not in r.out
    assert "would install brainstorming" in r.out
    assert "would install 1 skill" in r.out and "add " not in r.out


def test_a_pin_the_held_tap_is_not_on_differs(boost, sandbox, held_old):
    head = gitutil.head_commit(held_old.path)
    bf = _boostfile(sandbox, "tap %s --at %s" % (NEW, "0" * 40))
    r = boost("bundle", "install", bf)
    # The warning folds to the pane; the claim is the words, not the breaks.
    assert "tap %s is at %s, Boostfile wants --at 0000000" % (
        OLD, head[:7]) in " ".join(r.out.split())
    assert "1 differs" in r.out
    bf = _boostfile(sandbox, "tap %s --at %s" % (NEW, head))
    r = boost("bundle", "install", bf)
    assert "differ" not in r.out


def test_an_unrelated_line_is_untouched(boost, sandbox, held_old):
    """A skill line naming a tap no line aliased still misses by that name."""
    bf = _boostfile(sandbox, "skill %s:brainstorming" % NEW)
    r = boost("bundle", "install", bf, expect=1)
    assert "brainstorming not found in tap %s" % NEW in r.out + r.err


def test_a_line_naming_its_own_alias_resolves_both_names(boost, sandbox,
                                                         held_old):
    """`tap NAME URL` is tapped under the URL's name, so a skill line may
    qualify with either; each finds the held tap."""
    bf = _boostfile(sandbox, "tap mine %s" % (GH + NEW),
                    "skill mine:brainstorming",
                    "skill %s:commit-messages" % NEW)
    r = boost("bundle", "install", bf)
    assert "Installed 2 skills" in r.out
    assert {lockfile.get_skill(n)["tap"]
            for n in ("brainstorming", "commit-messages")} == {OLD}
