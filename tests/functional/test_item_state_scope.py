# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A held or project-scoped skill reads as what it is, and stays that way.

Measured before these fixes, in a sandbox over the fixture tap:

* a quarantined skill showed ``missing quarantined`` in `boost list` and
  ``[missing from store]`` in `boost info`, both naming `boost heal` — which
  answered "nothing to heal", because a held copy is away on purpose;
* `boost focus --clear` and `boost context disable` restored and relinked a
  skill quarantined while sidelined, the lock still saying quarantined;
* `boost pin` with a user and a project copy of one name pinned the user row
  alone, so `boost update` moved the repo's copy, and a pinned project row
  showed no pin in `list` or `info`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from boost_cli.core import lockfile, paths, projectlock, store, util


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


def _said(r):
    return " ".join((r.out + r.err).split())


def _row(out: str, name: str) -> str:
    return next(ln for ln in out.splitlines() if ln.startswith(name + " "))


def _link(name: str):
    return paths.home() / ".claude" / "skills" / name


# ── quarantined: not "missing", no heal hint ─────────────────────────────


@pytest.fixture()
def quarantined(boost, tapped):
    boost("install", "brainstorming", "tdd-workflow")
    boost("quarantine", "brainstorming")
    return "brainstorming"


class TestQuarantinedIsNotMissing:
    def test_list_flags_it_quarantined_only(self, boost, quarantined):
        r = boost("list")
        assert _row(r.out, "brainstorming").split()[-1] == "quarantined"
        assert "missing" not in r.out
        assert "boost heal" not in r.out

    def test_list_json_does_not_mark_it_missing(self, boost, quarantined):
        data = json.loads(boost("list", "--json").out)
        assert "missing_from_store" not in data["skills"]["brainstorming"]

    def test_info_names_the_release(self, boost, quarantined):
        r = boost("info", "brainstorming")
        assert "[installed] [quarantined]" in r.out
        assert "missing" not in r.out
        assert "boost heal" not in r.out
        assert ("store held aside — `boost quarantine --release brainstorming` "
                "puts it back") in _said(r)
        data = json.loads(boost("info", "brainstorming", "--json").out)
        assert (data["missing_from_store"], data["store"]) == (False, None)

    def test_a_sidelined_copy_is_not_missing_either(self, boost, tapped):
        boost("install", "brainstorming", "tdd-workflow")
        boost("focus", "brainstorming")
        r = boost("list")
        assert _row(r.out, "tdd-workflow").split()[-1] == "sidelined:focus"
        assert "boost heal" not in r.out
        r = boost("info", "tdd-workflow")
        assert ("store held aside — `boost focus --clear` puts it back"
                in _said(r))

    def test_a_gone_held_copy_is_still_missing(self, boost, tapped):
        # The guard is "held", not "quarantined": a quarantined skill whose
        # copy was never held (none to hold) is still reported.
        boost("install", "brainstorming")
        util.rmtree(store.skill_store_dir("brainstorming"))
        boost("quarantine", "brainstorming")
        assert not store.is_held(lockfile.get_skill("brainstorming"))
        r = boost("list")
        assert "missing" in _row(r.out, "brainstorming")


class TestMissingFromStore:
    def test_held_present_and_absent(self, sandbox):
        store.skill_store_dir("x").mkdir(parents=True)
        assert store.missing_from_store("x", {}) is False
        assert store.missing_from_store("y", {}) is True
        assert store.missing_from_store("y", None) is True
        assert store.missing_from_store("y", {store.HELD_KEY: "/h/y"}) is False

    def test_held_reason(self):
        assert store.held_reason("x", {"quarantined": True}) == (
            "quarantined", "`boost quarantine --release x` puts it back")
        assert store.held_reason("x", {"sidelined_by": "context"}) == (
            "sidelined by `boost context`",
            "`boost context disable` puts it back")
        assert store.held_reason("x", {}) == (
            "sidelined", "relinking it puts it back")


# ── un-sidelining never brings a quarantined skill back ──────────────────


def _assert_still_quarantined(name: str):
    entry = lockfile.get_skill(name)
    assert entry["quarantined"] is True
    assert "sidelined_by" not in entry
    assert entry["agents"] == []
    assert not os.path.lexists(_link(name))
    assert not os.path.lexists(paths.store_dir() / name)
    assert (paths.held_skills_dir() / name / "SKILL.md").is_file()


class TestUnsidelineRespectsQuarantine:
    def test_quarantine_takes_over_a_sideline(self, boost, tapped):
        boost("install", "brainstorming", "tdd-workflow")
        boost("focus", "brainstorming")
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "focus"
        boost("quarantine", "tdd-workflow")
        _assert_still_quarantined("tdd-workflow")

    def test_focus_clear_leaves_it_held(self, boost, tapped):
        boost("install", "brainstorming", "tdd-workflow", "commit-messages")
        boost("focus", "brainstorming")
        boost("quarantine", "tdd-workflow")
        r = boost("focus", "--clear")
        assert "focus cleared — 1 skill(s) restored" in r.out
        _assert_still_quarantined("tdd-workflow")
        assert _link("commit-messages").is_symlink()

    def test_focus_clear_skips_a_lock_with_both_flags(self, boost, tapped):
        # A lock written before quarantine dropped the sideline.
        boost("install", "brainstorming", "tdd-workflow")
        boost("focus", "brainstorming")
        boost("quarantine", "tdd-workflow")

        def both(e):
            e["sidelined_by"] = "focus"
        lockfile.update_skill("tdd-workflow", both)
        r = boost("focus", "--clear")
        assert "focus cleared — 0 skill(s) restored" in r.out
        assert not os.path.lexists(_link("tdd-workflow"))
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "focus"

    def test_unsideline_on_a_quarantined_row_only_drops_the_flag(
            self, boost, tapped):
        boost("install", "brainstorming", "tdd-workflow")
        boost("focus", "brainstorming")
        boost("quarantine", "tdd-workflow")

        def both(e):
            e["sidelined_by"] = "context"
        lockfile.update_skill("tdd-workflow", both)
        res = store.unsideline("tdd-workflow")
        assert (res.name, res.linked) == ("tdd-workflow", [])
        _assert_still_quarantined("tdd-workflow")

    def test_context_disable_leaves_it_held(
            self, boost, tapped, tmp_path, monkeypatch):
        boost("install", "brainstorming", "tdd-workflow")
        repo = tmp_path / "ctx-work"
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        _git(repo, "branch", "-m", "main")
        monkeypatch.chdir(repo)
        boost("context", "map", "main", "brainstorming")
        boost("context", "map", "feature/*", "tdd-workflow")
        boost("context", "enable")
        assert lockfile.get_skill("tdd-workflow")["sidelined_by"] == "context"
        boost("quarantine", "tdd-workflow")
        r = boost("context", "disable")
        assert "branch-aware activation disabled — 0 skill(s) relinked" in r.out
        _assert_still_quarantined("tdd-workflow")


# ── pin / unpin pick a scope ─────────────────────────────────────────────


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    d = tmp_path / "pin-scope-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


@pytest.fixture()
def src(boost, fixture_tap_src, tmp_path):
    copy = tmp_path / "pin-scope-tap"
    shutil.copytree(fixture_tap_src, copy)
    boost("tap", copy)
    return copy


@pytest.fixture()
def both(boost, src, repo):
    boost("install", "cowboy-coding")
    boost("install", "--local", "cowboy-coding")
    return "cowboy-coding"


def _project_pinned(repo):
    return projectlock.get_skill(repo, "cowboy-coding").get("pinned")


class TestPinScope:
    @pytest.mark.parametrize("verb", ["pin", "unpin"])
    def test_both_scopes_unscoped_is_refused(self, boost, both, repo, verb):
        r = boost(verb, "cowboy-coding", expect=1)
        assert ("cowboy-coding is installed in your user config and in this "
                "repo — say which to %s" % verb) in _said(r)
        assert ("`boost %s cowboy-coding --global` or `boost %s cowboy-coding "
                "--local`" % (verb, verb)) in _said(r)
        assert lockfile.get_skill("cowboy-coding")["pinned"] is False
        assert _project_pinned(repo) is None

    def test_both_scopes_commit_pin_hint_keeps_commit(self, boost, both,
                                                       repo):
        # The hint dropped --commit, so running it set a version pin and no
        # commit pin. --local is not offered: --commit is refused there.
        r = boost("pin", "cowboy-coding", "--commit", expect=1)
        assert _said(r) == (
            "Error: cowboy-coding is installed in your user config and in "
            "this repo — say which to pin hint: `boost pin cowboy-coding "
            "--commit --global` — --commit applies to user-scope installs")
        assert lockfile.get_skill("cowboy-coding")["pinned"] is False
        boost("pin", "cowboy-coding", "--commit", "--global")
        row = lockfile.get_skill("cowboy-coding")
        assert row["pinned"] is True
        assert row["commit_pin"] == row["commit"]
        assert _project_pinned(repo) is None

    def test_local_pins_the_project_row_only(self, boost, both, repo, src):
        r = boost("pin", "cowboy-coding", "--local")
        assert ("pinned cowboy-coding (project) at v0.1.0 — `boost update` "
                "will skip it") in _said(r)
        assert _project_pinned(repo) is True
        assert lockfile.get_skill("cowboy-coding")["pinned"] is False
        md = src / "skills" / "cowboy-coding" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8")
                      .replace("version: 0.1.0", "version: 0.2.0"),
                      encoding="utf-8")
        _git(src, "commit", "-qam", "bump")
        boost("update")
        assert projectlock.get_skill(repo, "cowboy-coding")["version"] == "0.1.0"
        assert lockfile.get_skill("cowboy-coding")["version"] == "0.2.0"

    def test_scope_project_spelling_and_unpin(self, boost, both, repo):
        boost("pin", "cowboy-coding", "--scope", "project")
        assert _project_pinned(repo) is True
        r = boost("unpin", "cowboy-coding", "--local")
        assert ("unpinned cowboy-coding (project) (v0.1.0) — updates apply "
                "again") in _said(r)
        assert _project_pinned(repo) is None

    def test_global_pins_the_user_row_only(self, boost, both, repo):
        r = boost("pin", "cowboy-coding", "--global")
        assert ("pinned cowboy-coding at v0.1.0 — `boost update` will skip it"
                in _said(r))
        assert lockfile.get_skill("cowboy-coding")["pinned"] is True
        assert _project_pinned(repo) is None
        boost("unpin", "cowboy-coding", "--scope", "user")
        assert lockfile.get_skill("cowboy-coding")["pinned"] is False

    def test_commit_pin_with_local_is_refused(self, boost, both, repo):
        r = boost("pin", "--commit", "cowboy-coding", "--local", expect=1)
        assert ("cowboy-coding is installed at project scope — --commit "
                "applies to user-scope installs") in _said(r)
        # The bare `boost pin NAME` is refused while a user copy exists.
        assert "`boost pin cowboy-coding --local` holds it" in _said(r)
        assert _project_pinned(repo) is None

    def test_local_with_no_project_row(self, boost, src, repo):
        boost("install", "cowboy-coding")
        r = boost("pin", "cowboy-coding", "--local", expect=1)
        assert "cowboy-coding is not installed in this repo" in _said(r)

    def test_global_with_no_user_row(self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        r = boost("unpin", "cowboy-coding", "--global", expect=1)
        assert "cowboy-coding is not installed in your user config" in _said(r)

    def test_local_from_home_is_not_a_project(self, boost, tapped,
                                              monkeypatch):
        # $HOME is the one directory project scope never resolves to.
        monkeypatch.chdir(paths.home())
        boost("install", "brainstorming")
        r = boost("pin", "brainstorming", "--local", expect=1)
        assert ("not in a project — --local pins what this repo has "
                "installed") in _said(r)
        assert lockfile.get_skill("brainstorming")["pinned"] is False


class TestProjectPinShows:
    def test_list_and_info_show_the_pin(self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        r = boost("list")
        assert "FLAGS" in r.out
        assert "pinned" not in _row(r.out, "cowboy-coding")
        r = boost("info", "cowboy-coding")
        assert "pinned no" in " ".join(r.out.split())
        boost("pin", "cowboy-coding")
        r = boost("list")
        assert _row(r.out, "cowboy-coding").split()[-1] == "pinned"
        r = boost("info", "cowboy-coding")
        assert "[installed in this project] [pinned]" in r.out
        assert "pinned yes" in " ".join(r.out.split())
