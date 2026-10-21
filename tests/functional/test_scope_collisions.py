# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One skill name installed in both scopes, from two different taps.

A user ``brainstorming`` from ``sc-a`` beside a project ``brainstorming`` from
``sc-b`` is where every bare-name remedy and every scope-blind lookup picks the
wrong copy: a tap-qualified ``--local`` uninstall checked its qualifier against
the user row, ``untap`` warned about user dependents only, drift's local-edits
hint reinstalled the user copy, and the "already installed" refusal named a
command that acted on the other tap's copy.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from boost_cli.core import integrity, lockfile, projectlock


@pytest.fixture()
def twin(boost, fixture_tap_src, tmp_path, monkeypatch):
    """User brainstorming v1.4.0 from sc-a, project v1.5.0 from sc-b."""
    for name in ("sc-a", "sc-b"):
        shutil.copytree(fixture_tap_src, tmp_path / name)
    md = tmp_path / "sc-b" / "skills" / "brainstorming" / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace(
        "version: 1.4.0", "version: 1.5.0"), encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path / "sc-b"), "commit", "-aqm",
                    "bump"], check=True, capture_output=True)
    boost("tap", tmp_path / "sc-a")
    boost("tap", tmp_path / "sc-b")
    repo = tmp_path / "sc-repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    boost("install", "sc-a:brainstorming")
    boost("install", "sc-b:brainstorming", "--local")
    repo = repo.resolve()
    assert lockfile.get_skill("brainstorming")["tap"] == "sc-a"
    assert projectlock.get_skill(repo, "brainstorming")["tap"] == "sc-b"
    return repo


def _project_md(repo):
    entry = projectlock.get_skill(repo, "brainstorming")
    d = integrity.project_skill_dir(entry, repo)
    assert d is not None
    return d / "SKILL.md"


class TestQualifiedLocalActsOnTheProjectRow:
    def test_uninstall_the_project_taps_copy(self, boost, twin):
        boost("uninstall", "sc-b:brainstorming", "--local", "-y")
        assert projectlock.get_skill(twin, "brainstorming") is None
        assert lockfile.get_skill("brainstorming")["tap"] == "sc-a"

    def test_uninstall_with_the_user_taps_qualifier_refuses(self, boost, twin):
        r = boost("uninstall", "sc-a:brainstorming", "--local", "-y",
                  expect=1)
        assert ("sc-a:brainstorming is not installed in this repo — "
                "brainstorming is installed from sc-b, not sc-a"
                in " ".join(r.err.split()))
        assert projectlock.get_skill(twin, "brainstorming")["tap"] == "sc-b"

    def test_reinstall_the_project_taps_copy(self, boost, twin):
        r = boost("reinstall", "sc-b:brainstorming", "--local")
        assert "reinstalled brainstorming v1.5.0 (this repo)" in r.out

    def test_reinstall_with_the_user_taps_qualifier_keeps_the_edit(
            self, boost, twin):
        md = _project_md(twin)
        md.write_text(md.read_text(encoding="utf-8") + "\nEDIT\n",
                      encoding="utf-8")
        r = boost("reinstall", "sc-a:brainstorming", "--local", expect=1)
        assert "not installed in this repo" in " ".join(r.err.split())
        assert md.read_text(encoding="utf-8").endswith("\nEDIT\n")

    def test_global_with_the_project_taps_qualifier_refuses(self, boost, twin):
        r = boost("uninstall", "sc-b:brainstorming", "--global", "-y",
                  expect=1)
        assert ("sc-b:brainstorming is not installed in your user config — "
                "brainstorming is installed from sc-a, not sc-b"
                in " ".join(r.err.split()))
        assert lockfile.get_skill("brainstorming")["tap"] == "sc-a"


class TestUntapCountsProjectDependents:
    def test_a_project_only_dependent_asks_first(self, boost, twin,
                                                 monkeypatch):
        monkeypatch.delenv("BOOST_ASSUME_YES")
        r = boost("untap", "sc-b", expect=1)
        assert ("1 installed item(s) from sc-b: brainstorming (project)"
                in r.out)
        assert "cancelled" in r.out
        assert "sc-b" in boost("taps").out

    def test_force_untaps_past_it(self, boost, twin):
        r = boost("untap", "sc-b", "--force")
        assert "1 installed item(s) from sc-b: brainstorming (project)" in r.out
        assert "untapped sc-b" in r.out


class TestProjectEditRemedyCarriesLocal:
    def test_drift_hint_and_following_it_discards_the_edit(self, boost, twin):
        md = _project_md(twin)
        md.write_text(md.read_text(encoding="utf-8") + "\nLOCAL EDIT\n",
                      encoding="utf-8")
        r = boost("drift")
        assert ("boost reinstall brainstorming --local to discard local edits"
                in r.out)
        boost("reinstall", "brainstorming", "--local")
        assert "LOCAL EDIT" not in md.read_text(encoding="utf-8")
        assert "local-edits" not in boost("drift").out

    def test_doctor_names_the_local_reinstall(self, boost, twin):
        md = _project_md(twin)
        md.write_text(md.read_text(encoding="utf-8") + "\nLOCAL EDIT\n",
                      encoding="utf-8")
        r = boost("doctor", expect=None)
        assert ("project skill brainstorming modified since install — run "
                "`boost reinstall brainstorming --local` to discard local "
                "edits" in " ".join(r.out.split()))


class TestAlreadyInstalledNamesTheTap:
    def test_project_scope(self, boost, twin):
        r = boost("install", "sc-a:brainstorming", "--local", expect=1)
        err = " ".join(r.err.split())
        assert ("brainstorming is already installed in this project (v1.5.0) "
                "from sc-b, not sc-a" in err)
        assert "`boost install sc-a:brainstorming --local --force`" in err

    def test_user_scope(self, boost, twin):
        r = boost("install", "sc-b:brainstorming", expect=1)
        err = " ".join(r.err.split())
        assert ("brainstorming is already installed (v1.4.0) from sc-a, not "
                "sc-b" in err)
        assert "`boost install sc-b:brainstorming --force`" in err
        # The hint runs, and takes the tap that was asked for.
        boost("install", "sc-b:brainstorming", "--force")
        assert lockfile.get_skill("brainstorming")["tap"] == "sc-b"
