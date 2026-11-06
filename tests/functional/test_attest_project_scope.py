# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""``boost attest`` sees project-scope skills, as ``boost verify`` does.

A skill installed ``--local`` lives in the repo's own lock, and attest only
read the user lock: ``attest NAME`` said "not installed" about a skill
``boost list`` showed, and ``attest --verify`` passed rc 0 over a tampered
repo copy that ``verify`` failed.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import paths


@pytest.fixture()
def project(boost, tapped, monkeypatch):
    proj = paths.home() / "code" / "proj"
    (proj / ".git").mkdir(parents=True)
    monkeypatch.chdir(proj)
    boost("install", "tdd-workflow", "--local")
    return proj


def _tamper(project):
    skill = project / ".claude" / "skills" / "tdd-workflow" / "SKILL.md"
    with skill.open("a", encoding="utf-8") as fh:
        fh.write("tampered\n")


def test_name_finds_a_project_only_install(boost, project):
    r = boost("attest", "tdd-workflow", "--verify")
    assert "tdd-workflow (project)" in r.out
    assert "tdd-workflow (project) attestation OK" in r.out


def test_verify_fails_a_tampered_project_copy(boost, project):
    _tamper(project)
    r = boost("attest", "--verify", expect=1)
    assert ("! tdd-workflow (project): project copy no longer matches the "
            "project lock sha") in r.out
    data = json.loads(boost("attest", "--verify", "--json", expect=1).out)
    assert data["failed"] == 1
    [row] = data["skills"]
    assert (row["name"], row["scope"], row["sha_ok"], row["reason"]) == (
        "tdd-workflow", "project", False, "modified")
    # Without --verify it lists, and grades nothing.
    assert "tdd-workflow (project)" in boost("attest").out


def test_verify_names_a_missing_project_copy(boost, project):
    from boost_cli.core.util import rmtree
    for copy in project.glob("*/skills/tdd-workflow"):
        rmtree(copy)
    r = boost("attest", "tdd-workflow", "--verify", expect=1)
    assert "! tdd-workflow (project): project copy missing (boost sync)" in r.out


def test_a_same_named_user_skill_stays_a_separate_row(boost, project):
    boost("install", "tdd-workflow")
    _tamper(project)
    r = boost("attest", "tdd-workflow", "--verify", expect=1)
    assert "✓ tdd-workflow attestation OK" in r.out
    assert ("! tdd-workflow (project): project copy no longer matches the "
            "project lock sha") in r.out
    data = json.loads(boost("attest", "tdd-workflow", "--verify", "--json",
                            expect=1).out)
    assert [(s["scope"], s["sha_ok"]) for s in data["skills"]] == [
        ("user", True), ("project", False)]


def test_an_unknown_name_is_still_refused(boost, project):
    r = boost("attest", "nosuch", expect=1)
    assert "not installed: nosuch" in r.err
