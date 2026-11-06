# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost recommend` leaves out what is already installed.

It ranked every catalog row and never read a lock, so in a python project
with `python-style` and a python rule installed both came back as "because:
python" suggestions, unmarked, each taking a `--limit` slot from something
the user did not have.
"""
from __future__ import annotations

import json
import subprocess

import pytest


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture()
def rec_tap(boost, tmp_path):
    root = tmp_path / "rec-tap"
    for name, desc, tags in (
            ("python-style", "Idiomatic Python formatting with pytest",
             "[python, pytest]"),
            ("python-lint", "Python lint fixes", "[python]"),
            ("react-patterns", "Component patterns for React apps",
             "[react, javascript]")):
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: %s\ndescription: %s\nversion: 1.0.0\ntags: %s\n---\n\n"
            "# %s\n\nBody.\n" % (name, desc, tags, name), encoding="utf-8")
    (root / "rules").mkdir()
    (root / "rules" / "strict-typing.mdc").write_text(
        "---\nname: strict-typing\ndescription: Always use strict typing in "
        "python and pytest\n---\n\nType everything.\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "items")
    boost("tap", root)
    return root


@pytest.fixture()
def py_project(tmp_path):
    proj = tmp_path / "py-proj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\naddopts = '-q'\n", encoding="utf-8")
    return proj


def _names(boost, proj, *extra):
    data = json.loads(boost("recommend", "--path", proj, "--json", *extra).out)
    return [r["name"] for r in data["recommendations"]]


def test_baseline_ranks_all_three(boost, rec_tap, py_project):
    assert _names(boost, py_project) == [
        "python-style", "python-lint", "strict-typing"]


def test_installed_skill_and_rule_are_left_out(boost, rec_tap, py_project):
    boost("install", "python-style")
    boost("install", "strict-typing")
    assert _names(boost, py_project) == ["python-lint"]
    r = boost("recommend", "--path", py_project)
    assert "python-lint" in r.out
    assert "python-style" not in r.out
    assert "strict-typing" not in r.out


def test_installed_item_does_not_take_a_limit_slot(boost, rec_tap, py_project):
    boost("install", "python-style")
    assert _names(boost, py_project, "--limit", "1") == ["python-lint"]


def test_project_scope_install_of_the_path_is_left_out(
        boost, rec_tap, py_project, monkeypatch):
    monkeypatch.chdir(py_project)
    boost("install", "--local", "python-style")
    elsewhere = py_project.parent / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    # The project --path names is the one whose lock counts, not the cwd's.
    assert _names(boost, py_project) == ["python-lint", "strict-typing"]


def test_curated_fallback_leaves_out_installed(boost, fixture_tap_src,
                                               tmp_path):
    boost("tap", fixture_tap_src, "--curated")
    proj = tmp_path / "empty-proj"
    proj.mkdir()
    before = _names(boost, proj)
    assert "brainstorming" in before
    boost("install", "brainstorming")
    after = _names(boost, proj)
    assert after == [n for n in before if n != "brainstorming"]
