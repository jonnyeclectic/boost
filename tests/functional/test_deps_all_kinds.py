# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost deps` with no NAME walks rules and workflows, as `deps NAME` does.

The no-name check iterated the skills section alone, so an installed workflow
with an unmet `requires:` read "no unmet requirements or conflicts" (rc 0)
while `boost deps <workflow>` named the gap (rc 1), and a workflow's
`conflicts:` against an installed skill was never reported at all.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

WORKFLOW = "ship-release"


@pytest.fixture()
def wf_tap(boost, fixture_tap_src, tmp_path):
    """The fixture tap plus a workflow that requires and conflicts."""
    tap = tmp_path / "deps-kinds-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "commands").mkdir()
    (tap / "commands" / ("%s.md" % WORKFLOW)).write_text(
        "---\nname: %s\nversion: 1.0.0\nrequires: [commit-messages]\n"
        "conflicts: [tdd-workflow]\n---\n\nRelease checklist.\n" % WORKFLOW,
        encoding="utf-8")
    subprocess.run(["git", "-C", str(tap), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap), "commit", "-qm", "add workflow"],
                   check=True, capture_output=True)
    boost("tap", tap)
    return tap


def test_workflow_conflict_is_reported(boost, wf_tap):
    boost("install", WORKFLOW)            # pulls in commit-messages
    boost("install", "tdd-workflow")
    data = json.loads(boost("deps", "--json", expect=1).out)
    assert data == {"unmet": [],
                    "conflicts": [{"a": WORKFLOW, "b": "tdd-workflow"}]}
    r = boost("deps", expect=1)
    assert "ship-release conflicts with tdd-workflow" in r.out
    assert "no unmet requirements" not in r.out


def test_workflow_unmet_requirement_is_reported(boost, wf_tap):
    boost("install", WORKFLOW)
    boost("uninstall", "commit-messages")
    data = json.loads(boost("deps", "--json", expect=1).out)
    assert data == {"unmet": [{"skill": WORKFLOW,
                               "requires": {"name": "commit-messages",
                                            "installed": False,
                                            "requires": []}}],
                    "conflicts": []}
    r = boost("deps", expect=1)
    assert "ship-release requires commit-messages ✗ not installed" in r.out
    assert "boost install commit-messages" in r.out + r.err
    # The no-name verdict now agrees with the named one.
    boost("deps", WORKFLOW, expect=1)


def test_clean_mixed_environment_counts_items(boost, wf_tap):
    boost("install", WORKFLOW)
    r = boost("deps")
    assert "✓ no unmet requirements or conflicts across 2 items" in r.out


def test_skill_only_environment_still_says_skills(boost, wf_tap):
    boost("install", "commit-messages")
    r = boost("deps")
    assert "✓ no unmet requirements or conflicts across 1 skill\n" in r.out
