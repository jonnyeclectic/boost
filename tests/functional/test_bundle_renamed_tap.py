# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: a Boostfile tapping a renamed row by its new name.

A machine that tapped a catalogue row before the repository was renamed holds
it under the old name, and `registry.add` refuses to clone it again under the
new one. `boost bundle install` reported that refusal as a failed tap line, so
a Boostfile dumped on a machine that tapped the new name — `tap NEW URL` and
`skill NEW:x` — installed nothing here. The line is already held, and its
skill lines resolve against the tap that holds it. So does a tap line that
spells a held tap's name in another case, or names it by a URL whose name is
not the line's NAME.

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


def test_a_skill_line_resolves_under_the_name_the_tap_line_taps(
        boost, sandbox, held_old):
    """`tap NAME URL` is tapped under the URL's name, not NAME — on a machine
    that clones it, `skill NAME:x` misses (`test_cli_pkg`'s
    `test_dry_run_misses_a_line_naming_the_tap_by_its_boostfile_name`). Held
    under the other name here, it resolves exactly as it would there: by the
    URL's name, and by NAME not at all."""
    bf = _boostfile(sandbox, "tap mine %s" % (GH + NEW),
                    "skill %s:commit-messages" % NEW,
                    "skill mine:brainstorming")
    r = boost("bundle", "install", bf, expect=1)
    assert "brainstorming not found in tap mine" in r.out + r.err
    assert "Installed 1 skill, 1 failed" in r.out
    assert lockfile.get_skill("commit-messages")["tap"] == OLD


def test_a_skill_line_in_another_case_resolves_too(boost, sandbox, held_old):
    """`catalog.find`'s tap filter is case-blind, so on a machine that clones
    `NewOwner/AI-Skills`, `skill newowner/ai-skills:x` installs from it."""
    bf = _boostfile(sandbox, "tap NewOwner/AI-Skills",
                    "skill NewOwner/AI-Skills:brainstorming",
                    "skill %s:commit-messages" % NEW)
    r = boost("bundle", "install", bf)
    assert "Installed 2 skills" in r.out
    assert {lockfile.get_skill(n)["tap"]
            for n in ("brainstorming", "commit-messages")} == {OLD}


@pytest.fixture
def held_new(boost, sandbox, fixture_tap_src, monkeypatch):
    """NEW tapped under its own name: nothing was renamed."""
    cfg = config.load()
    cfg["taps"] = [{"name": NEW, "url": GH + NEW, "curated": False}]
    config.save(cfg)
    tap = registry.get(NEW)
    tap.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture_tap_src, tap.path)
    catalog.rebuild_tap(tap)

    def no_clone(*_a, **_k):
        raise AssertionError("cloned the held repository a second time")
    monkeypatch.setattr(gitutil, "clone_shallow", no_clone)
    return tap


@pytest.mark.parametrize("line", ["tap NewOwner/AI-Skills",
                                  "tap mine %s" % (GH + NEW),
                                  "tap mine git@github.com:%s.git" % NEW])
@pytest.mark.parametrize("dry", [False, True])
def test_a_tap_line_spelling_a_held_tap_otherwise_is_held(
        boost, sandbox, held_new, line, dry):
    """Not only a rename: a tap line in another case, or with a NAME that is
    not its URL's, names a repository tapped here. `registry.add` refused
    those as "already configured", which failed the line and exited 1 on a
    machine where every skill line installed."""
    bf = _boostfile(sandbox, line, "skill %s:brainstorming" % NEW)
    r = boost("bundle", "install", bf, *(["--dry-run"] if dry else []))
    assert "already tapped as %s" % NEW in r.out
    assert "renamed upstream" not in r.out      # nothing was
    assert "failed" not in r.out + r.err
    assert "would tap" not in r.out
    assert _tap_names() == [NEW]
    if not dry:
        assert "Installed 1 skill" in r.out
        assert lockfile.get_skill("brainstorming")["tap"] == NEW
