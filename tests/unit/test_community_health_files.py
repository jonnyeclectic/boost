# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit test: the GitHub community-health files exist and are wired up.

A malformed issue form does not error anywhere a human will see — GitHub just
silently falls back to a blank issue, and the template quietly stops existing.
Same for a PR template GitHub cannot find because it was moved. These are the
cheap structural checks that catch that class of breakage.

Read by hand rather than with PyYAML, which is not a dependency of this repo;
``scripts/check_required_checks.py`` sets the same precedent for workflow YAML.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"

pytestmark = pytest.mark.skipif(
    not (ROOT / ".github").is_dir(),
    reason="repo-root .github not reachable (e.g. mutation sandbox)")

# The set GitHub actually renders. A typo here ("textbox", "check") is accepted
# by no parser and reported by nothing — the field just vanishes from the form.
FIELD_TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}

FORMS = ["bug_report.yml", "feature_request.yml"]


def form_text(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", FORMS)
def test_each_issue_form_exists_and_is_named(name):
    text = form_text(name)
    # GitHub requires both at the top level; without them the file is ignored.
    assert re.search(r"^name:\s*\S", text, re.M), "%s has no name:" % name
    assert re.search(r"^description:\s*\S", text, re.M), "%s has no description:" % name
    assert re.search(r"^body:\s*$", text, re.M), "%s has no body:" % name


@pytest.mark.parametrize("name", FORMS)
def test_every_field_declares_a_type_github_renders(name):
    types = re.findall(r"^  - type:\s*(\S+)\s*$", form_text(name), re.M)
    assert types, "%s declares no fields" % name
    assert set(types) <= FIELD_TYPES, "unknown field type in %s: %s" % (
        name, sorted(set(types) - FIELD_TYPES))


@pytest.mark.parametrize("name", FORMS)
def test_field_ids_are_unique(name):
    # Duplicate ids make GitHub drop one of the fields, silently.
    ids = re.findall(r"^    id:\s*(\S+)\s*$", form_text(name), re.M)
    assert len(ids) == len(set(ids)), "duplicate field id in %s" % name


def test_the_bug_form_asks_for_the_diagnostics_that_make_a_bug_reproducible():
    # The whole point of the form over a blank issue: `boost doctor` and the
    # exact command are required, so triage does not start with two questions.
    text = form_text("bug_report.yml")
    assert "boost doctor" in text
    assert "boost log --crashes" in text
    assert text.count("required: true") >= 4


def test_security_reports_are_routed_away_from_public_issues():
    advisory = "security/advisories/new"
    assert advisory in form_text("bug_report.yml"), \
        "the bug form must say where a vulnerability goes instead"
    assert advisory in (TEMPLATES / "config.yml").read_text(encoding="utf-8")


def test_the_pr_template_is_where_github_looks_for_it():
    template = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
    assert template.is_file(), "GitHub only auto-fills from this exact path"
    text = template.read_text(encoding="utf-8")
    assert "make check" in text
    # The generated-file checklist is the item that most often sends a PR back.
    for generated in ("build_roadmap.py", "build_command_reference.py",
                      "build_registries.py"):
        assert generated in text


def test_the_code_of_conduct_is_linked_from_contributing():
    assert (ROOT / "CODE_OF_CONDUCT.md").is_file()
    assert "CODE_OF_CONDUCT.md" in (ROOT / "CONTRIBUTING.md").read_text(
        encoding="utf-8"), "an unlinked code of conduct is one nobody reads"
