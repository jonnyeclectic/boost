# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost drift` grades a skill installed `--local`, as verify does.

It walked the user lock only: an edited project copy was absent from the
table and the JSON, the run said "N in-sync" rc 0 while `verify` failed it,
and `boost drift NAME` answered "not installed".
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import integrity, projectlock


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    d = tmp_path / "pdr-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


@pytest.fixture()
def src(boost, fixture_tap_src, tmp_path):
    copy = tmp_path / "pdr-tap"
    shutil.copytree(fixture_tap_src, copy)
    md = copy / "rules" / "house.mdc"
    md.parent.mkdir(parents=True)
    md.write_text("---\nname: house-rule\nversion: 1.0.0\n---\n\n"
                  "Keep it tidy.\n", encoding="utf-8")
    _git(copy, "add", "rules")
    _git(copy, "commit", "-qm", "add rule")
    boost("tap", copy)
    return copy


def _said(r):
    return " ".join((r.out + r.err).split())


def _project_md(repo, name):
    entry = projectlock.get_skill(repo, name)
    assert entry is not None
    d = integrity.project_skill_dir(entry, repo)
    assert d is not None
    return d / "SKILL.md"


class TestDriftSeesProjectSkills:
    def test_an_edited_project_copy_is_local_edits(self, boost, tapped, repo):
        boost("install", "--local", "brainstorming")
        md = _project_md(repo, "brainstorming")
        md.write_text(md.read_text(encoding="utf-8") + "\nlocal edit\n",
                      encoding="utf-8")
        data = json.loads(boost("drift", "--json").out)
        assert data == {"skills": [{
            "name": "brainstorming", "kind": "skill", "scope": "project",
            "status": "local-edits",
            # --local: bare `reinstall` reads the user lock, not this repo.
            "hint": "boost reinstall brainstorming --local to discard local "
                    "edits"}]}
        r = boost("drift")
        assert "brainstorming (project)" in r.out
        assert "1 local-edits" in _said(r)

    def test_naming_a_project_skill_resolves_it(self, boost, tapped, repo):
        boost("install", "--local", "brainstorming")
        data = json.loads(boost("drift", "--json", "brainstorming").out)
        assert data["skills"] == [{
            "name": "brainstorming", "kind": "skill", "scope": "project",
            "status": "in-sync", "hint": ""}]

    def test_both_scopes_are_listed_with_their_scope(self, boost, tapped, repo):
        boost("install", "brainstorming")
        boost("install", "--local", "brainstorming")
        rows = json.loads(boost("drift", "--json").out)["skills"]
        assert [(r["name"], r["scope"], r["status"]) for r in rows] == [
            ("brainstorming", "user", "in-sync"),
            ("brainstorming", "project", "in-sync")]

    def test_an_unnamed_project_skill_is_filtered_out(self, boost, tapped,
                                                      repo):
        boost("install", "brainstorming")
        boost("install", "--local", "cowboy-coding")
        rows = json.loads(boost("drift", "--json", "brainstorming").out)["skills"]
        assert [(r["name"], r["scope"]) for r in rows] == [
            ("brainstorming", "user")]

    def test_a_deleted_project_copy_points_at_sync(self, boost, tapped, repo):
        boost("install", "--local", "brainstorming")
        shutil.rmtree(_project_md(repo, "brainstorming").parent)
        rows = json.loads(boost("drift", "--json").out)["skills"]
        assert [(r["status"], r["hint"]) for r in rows] == [
            ("store-missing", "boost sync")]

    def test_an_upstream_move_is_upstream_moved(self, boost, src, repo):
        boost("install", "--local", "cowboy-coding")
        md = src / "skills" / "cowboy-coding" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "\nmoved\n",
                      encoding="utf-8")
        _git(src, "commit", "-qam", "move cowboy-coding")
        boost("update", "--taps-only")
        rows = json.loads(boost("drift", "--json").out)["skills"]
        assert [(r["name"], r["status"], r["hint"]) for r in rows] == [
            ("cowboy-coding", "upstream-moved", "boost update")]

    def test_an_unlocked_project_row_is_local_edits(self, boost, tapped, repo):
        boost("install", "--local", "brainstorming")
        entry = projectlock.get_skill(repo, "brainstorming")
        del entry["sha256"]
        projectlock.set_skill(repo, "brainstorming", entry)
        rows = json.loads(boost("drift", "--json").out)["skills"]
        assert [r["status"] for r in rows] == ["local-edits"]

    def test_a_local_rule_reports_its_project_scope(self, boost, src, repo):
        boost("install", "--local", "house-rule")
        rows = json.loads(boost("drift", "--json").out)["skills"]
        assert [(r["name"], r["kind"], r["scope"]) for r in rows] == [
            ("house-rule", "rule", "project")]
        assert "house-rule (rule)" in boost("drift").out

    def test_an_unknown_name_still_errors(self, boost, tapped, repo):
        boost("install", "--local", "brainstorming")
        r = boost("drift", "nope-not-here", expect=1)
        assert "not installed: nope-not-here" in _said(r)
