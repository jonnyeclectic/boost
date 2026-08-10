"""Unit tests: a PR-triggered workflow never shares one concurrency group.

``demo.yml`` declared::

    concurrency:
      group: demo
      cancel-in-progress: true

A **constant** group name puts every run of that workflow — every pull request,
and ``main`` — into one queue, and ``cancel-in-progress`` then means each new run
kills whichever other PR's run was in flight. The cancellation is not a flake and
not a timeout; it is the configuration working exactly as written.

Observed on 2026-08-10: #498 and #504 both touch ``boost_cli/cli.py``, which is
in demo.yml's path filter, so both triggered it. Each showed ``record
CANCELLED`` and neither could merge — and re-running the job just moved the
cancellation to the other PR. A cancelled check reports no conclusion, so it is
indistinguishable from a failing one at the merge button, and the PR that
cancelled yours is not mentioned anywhere on your PR.

``ci.yml`` already has the correct shape and its own test file
(``test_workflow_concurrency.py``) explains the other half of it — why non-PR
runs must key on ``github.sha`` rather than ``github.ref``, so three quick
merges cannot strand a middle commit unreleased. This file covers the property
that file does not: that the group is **per-run at all**, across every workflow
rather than in ci.yml alone.

The two failure modes are opposite and both real, which is why the assertions
are split: a group that is too broad cancels other people's runs, and a
``cancel-in-progress`` that is unconditional cancels the release path. Neither
is visible by reading one workflow.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

pytestmark = pytest.mark.skipif(
    not WORKFLOWS.exists(),
    reason=".github/workflows not reachable (e.g. mutation sandbox)")

#: Expressions that make a group name vary per run. Any one of them is enough.
_PER_RUN = ("github.event.pull_request.number", "github.sha", "github.ref",
            "github.run_id", "github.head_ref")


def _top_level_block(text: str, key: str) -> str:
    """A top-level mapping under ``key:``, or ''.

    Top-level only: a job-level block is indented and is a different policy.
    """
    m = re.search(r"^%s:\s*$\n((?:^[ \t]+\S.*\n|^\s*#.*\n)*)" % key, text, re.M)
    return m.group(1) if m else ""


def pr_triggered(text: str) -> bool:
    """True when this workflow runs on ``pull_request``."""
    return bool(re.search(r"^\s*pull_request(_target)?:", text, re.M))


def push_triggered(text: str) -> bool:
    """True when this workflow runs on a ``push`` (i.e. lands on ``main``).

    The distinction matters for the second property below. A schedule- or
    PR-only workflow has no main run to strand, so cancelling within a ref
    group is harmless there and flagging it would be noise.
    """
    return bool(re.search(r"^\s*push:", text, re.M))


def workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def _pr_workflows() -> list[Path]:
    return [p for p in workflows()
            if pr_triggered(p.read_text(encoding="utf-8"))]


class TestTheGuardCanActuallySee:
    """The assertions below pass vacuously if the parser stops matching."""

    def test_workflows_are_found(self):
        assert len(workflows()) > 5, "the workflow glob matched almost nothing"

    def test_some_workflow_is_pr_triggered(self):
        assert _pr_workflows(), "no workflow parsed as pull_request-triggered"

    def test_ci_is_recognised_as_pr_triggered(self):
        # The known-good example. If ci.yml stops being seen, the trigger
        # detection is broken and every assertion here is meaningless.
        assert (WORKFLOWS / "ci.yml") in _pr_workflows()

    def test_a_constant_group_is_recognised_as_constant(self):
        # Feed the parser demo.yml's exact old value and require a verdict of
        # "shared", so a fix to the tree cannot silently disarm this file.
        assert not any(tok in "  group: demo\n" for tok in _PER_RUN)


@pytest.mark.parametrize("path", _pr_workflows(), ids=lambda p: p.name)
class TestPullRequestRunsDoNotCancelEachOther:
    def test_the_concurrency_group_varies_per_run(self, path):
        block = _top_level_block(path.read_text(encoding="utf-8"), "concurrency")
        if not block:
            # No group at all means no cross-PR cancellation — wasteful, but
            # not the bug this file is about. test_workflow_concurrency.py
            # separately requires ci.yml (the expensive one) to have one.
            pytest.skip("%s declares no concurrency group" % path.name)
        group = re.search(r"group:\s*(.+)", block)
        assert group, block
        value = group.group(1).strip()
        assert any(tok in value for tok in _PER_RUN), (
            "%s groups every run under a constant name (%s), so one PR's run "
            "cancels another's — #498 and #504 both showed `record CANCELLED` "
            "and neither could merge" % (path.name, value))

    def test_a_main_push_is_not_cancelled_by_the_next_one(self, path):
        # The opposite error, and only reachable for a workflow that actually
        # runs on `push`. Keying main's runs on `github.ref` puts every main
        # commit in ONE group, so with unconditional cancellation a quick
        # second merge kills the first commit's run — the shape
        # test_workflow_concurrency.py pins for ci.yml, where it would strand a
        # commit unreleased. A schedule- or PR-only workflow has no main run to
        # strand, which is why the trigger is checked before the group.
        text = path.read_text(encoding="utf-8")
        if not push_triggered(text):
            pytest.skip("%s never runs on a push to main" % path.name)
        block = _top_level_block(text, "concurrency")
        cancel = re.search(r"cancel-in-progress:\s*(.+)", block)
        if not cancel:
            pytest.skip("%s does not cancel in progress" % path.name)
        value = cancel.group(1).strip()
        if value in ("false", "'false'", '"false"'):
            return
        group = re.search(r"group:\s*(.+)", block)
        keyed_per_commit = bool(group) and "github.sha" in group.group(1)
        assert "pull_request" in value or keyed_per_commit, (
            "%s runs on push and cancels unconditionally under a group every "
            "main commit shares, so a quick second merge cancels the first "
            "commit's run" % path.name)
