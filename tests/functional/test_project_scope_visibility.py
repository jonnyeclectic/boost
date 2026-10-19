# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Project-scoped skills are visible to `outdated`, `update` and `deps`.

`boost info` and `boost list` read the repo's own lock (`.boost/skill-lock.json`)
and `outdated`, `update` and `deps` did not: in one directory `info` said
"update available" while `outdated` said "everything up to date", `update -y`
left the skill at its old version, and `deps` called a requirement installed in
the same repo "not installed" and hinted at a duplicate user-scope install.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import integrity, lockfile, projectlock, scopes, staleness


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A project directory that looks like a git repo, cd'd into."""
    d = tmp_path / "psv-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


def _own_tap(boost, fixture_tap_src, tmp_path, name):
    """Copy the session fixture into a uniquely named tap and tap it."""
    dest = tmp_path / name
    shutil.copytree(fixture_tap_src, dest)
    boost("tap", dest)
    return dest


def _bump(tap_dir, skill, old, new):
    md = tap_dir / "skills" / skill / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace(
        "version: %s" % old, "version: %s" % new), encoding="utf-8")
    subprocess.run(["git", "-C", str(tap_dir), "commit", "-aqm",
                    "bump %s to %s" % (skill, new)],
                   check=True, capture_output=True)


def _project_skill_md(repo, name):
    entry = projectlock.get_skill(repo, name)
    assert entry is not None
    d = integrity.project_skill_dir(entry, repo)
    assert d is not None
    return d / "SKILL.md"


class TestOutdatedSeesProjectSkills:
    def test_json_lists_project_row_with_scope(self, boost, fixture_tap_src,
                                               tmp_path, repo):
        tap = _own_tap(boost, fixture_tap_src, tmp_path, "psv-outdated-tap")
        boost("install", "--local", "commit-messages")
        _bump(tap, "commit-messages", "1.0.2", "1.1.0")
        boost("update", "--taps-only")
        data = json.loads(boost("outdated", "--json").out)
        assert data == [{"name": "commit-messages", "kind": "skill",
                         "installed": "1.0.2", "latest": "1.1.0",
                         "reason": staleness.VERSION, "latest_commit": None,
                         "tap": "psv-outdated-tap", "pinned": False,
                         "scope": scopes.SCOPE_PROJECT}]
        r = boost("outdated")
        assert "commit-messages (project)" in r.out
        assert "1.1.0" in r.out
        assert "everything up to date" not in r.out

    def test_user_rows_say_user(self, boost, fixture_tap_src, tmp_path, repo):
        tap = _own_tap(boost, fixture_tap_src, tmp_path, "psv-userrow-tap")
        boost("install", "commit-messages")
        _bump(tap, "commit-messages", "1.0.2", "1.1.0")
        boost("update", "--taps-only")
        data = json.loads(boost("outdated", "--json").out)
        assert [(d["name"], d["scope"]) for d in data] == [
            ("commit-messages", scopes.SCOPE_USER)]
        assert "(project)" not in boost("outdated").out

    def test_same_name_in_both_scopes_is_two_rows(self, boost, fixture_tap_src,
                                                  tmp_path, repo):
        tap = _own_tap(boost, fixture_tap_src, tmp_path, "psv-both-tap")
        boost("install", "commit-messages")
        boost("install", "--local", "commit-messages")
        _bump(tap, "commit-messages", "1.0.2", "1.1.0")
        boost("update", "--taps-only")
        data = json.loads(boost("outdated", "--json").out)
        assert sorted((d["name"], d["scope"], d["latest"]) for d in data) == [
            ("commit-messages", scopes.SCOPE_PROJECT, "1.1.0"),
            ("commit-messages", scopes.SCOPE_USER, "1.1.0")]

    def test_current_project_skill_is_not_listed(self, boost, fixture_tap_src,
                                                 tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "psv-current-tap")
        boost("install", "--local", "commit-messages")
        assert json.loads(boost("outdated", "--json").out) == []


class TestUpdateRefreshesProjectSkills:
    def test_update_upgrades_in_the_repo_not_the_user_lock(
            self, boost, fixture_tap_src, tmp_path, repo):
        tap = _own_tap(boost, fixture_tap_src, tmp_path, "psv-update-tap")
        boost("install", "--local", "commit-messages")
        _bump(tap, "commit-messages", "1.0.2", "1.1.0")
        r = boost("update", "-y")
        assert "upgraded commit-messages (project) v1.0.2 → v1.1.0" in r.out
        assert projectlock.get_skill(repo, "commit-messages")["version"] == "1.1.0"
        assert "version: 1.1.0" in _project_skill_md(
            repo, "commit-messages").read_text(encoding="utf-8")
        assert lockfile.get_skill("commit-messages") is None
        assert json.loads(boost("outdated", "--json").out) == []

    def test_edited_project_skill_is_held(self, boost, fixture_tap_src,
                                          tmp_path, repo):
        tap = _own_tap(boost, fixture_tap_src, tmp_path, "psv-held-tap")
        boost("install", "--local", "commit-messages")
        md = _project_skill_md(repo, "commit-messages")
        md.write_text(md.read_text(encoding="utf-8") + "\nmine\n",
                      encoding="utf-8")
        _bump(tap, "commit-messages", "1.0.2", "1.1.0")
        r = boost("update", "-y")
        assert "commit-messages (project) has local edits" in r.out
        assert "boost install commit-messages --local --force" in r.out
        assert "1 item held back" in r.out
        assert projectlock.get_skill(repo, "commit-messages")["version"] == "1.0.2"
        assert md.read_text(encoding="utf-8").endswith("\nmine\n")
        r = boost("update", "-y", "--discard-edits")
        assert "local edits discarded" in r.out
        assert projectlock.get_skill(repo, "commit-messages")["version"] == "1.1.0"
        assert "mine" not in md.read_text(encoding="utf-8")

    def test_pinned_project_skill_is_left_alone(self, boost, fixture_tap_src,
                                                tmp_path, repo):
        tap = _own_tap(boost, fixture_tap_src, tmp_path, "psv-pinned-tap")
        boost("install", "--local", "commit-messages")
        entry = projectlock.get_skill(repo, "commit-messages")
        projectlock.set_skill(repo, "commit-messages", entry | {"pinned": True})
        _bump(tap, "commit-messages", "1.0.2", "1.1.0")
        boost("update", "-y")
        assert projectlock.get_skill(repo, "commit-messages")["version"] == "1.0.2"


class TestDepsSeesProjectSkills:
    def test_named_requirement_met_in_project(self, boost, fixture_tap_src,
                                              tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "psv-deps-tap")
        boost("install", "--local", "commit-messages")
        boost("install", "--local", "jira-integration")
        r = boost("deps", "jira-integration")
        assert "commit-messages ✓ installed" in r.out
        assert "boost install commit-messages" not in r.out + r.err
        data = json.loads(boost("deps", "--json", "jira-integration").out)
        assert [(row["name"], row["installed"]) for row in data["requires"]] == [
            ("commit-messages", True)]

    def test_no_arg_walks_project_skills(self, boost, fixture_tap_src,
                                         tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "psv-depsall-tap")
        boost("install", "--local", "commit-messages")
        boost("install", "--local", "jira-integration")
        r = boost("deps")
        assert "across 2 skills" in r.out
        assert json.loads(boost("deps", "--json").out) == {
            "unmet": [], "conflicts": []}
        # Drop the requirement from the project lock: the project-only
        # dependent must now be reported, which only happens if it is walked.
        projectlock.remove_skill(repo, "commit-messages")
        data = json.loads(boost("deps", "--json", expect=1).out)
        assert [(u["skill"], u["requires"]["name"], u["requires"]["installed"])
                for u in data["unmet"]] == [
            ("jira-integration", "commit-messages", False)]


class TestInstallLocalSeesProjectRequirement:
    def test_requirement_already_in_repo_is_not_replanned(
            self, boost, fixture_tap_src, tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "psv-instdep-tap")
        boost("install", "--local", "commit-messages")
        r = boost("install", "--local", "jira-integration")
        assert "pulling in" not in r.out
        assert "already installed in this project" not in r.out + r.err
        assert sorted(projectlock.installed(repo)) == [
            "commit-messages", "jira-integration"]
        assert lockfile.installed() == {}

    def test_missing_requirement_is_still_pulled_in(
            self, boost, fixture_tap_src, tmp_path, repo):
        _own_tap(boost, fixture_tap_src, tmp_path, "psv-instpull-tap")
        r = boost("install", "--local", "jira-integration")
        assert "pulling in 1 dependency required by your selection: " \
               "commit-messages" in r.out
        assert sorted(projectlock.installed(repo)) == [
            "commit-messages", "jira-integration"]
