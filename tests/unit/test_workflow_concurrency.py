# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: superseded PR runs are cancelled, releases never are.

Measured over six consecutive successful ``ci`` runs, **31%** of all job time
was spent queueing rather than executing (104 job-minutes against 236). The
median per-job queue swung 29x between runs — 0.1 min when the repo was quiet,
2.9 min when a dozen ``loop/*`` branches and Dependabot PRs were live — so the
cost is driven by concurrent footprint, not by the change under test. Sharding
the mutation gate traded one runner slot for six and made that worse on purpose.

``ci.yml`` is the largest workflow in the repo by a wide margin, and it was the
only one with no ``concurrency`` group at all: every push to a pull request left
the previous run's ~36 checks (six of them mutation shards) running to
completion against nothing.

The dangerous half of the fix is the half these tests pin. Cancelling a
**pull_request** run that a newer push superseded costs nothing. Cancelling a
**push to main** would abandon the run ``publish.yml`` gates the release on, and
cancelling a **merge_group** run would leave a required check permanently
unreported and deadlock the queue — the exact failure mode ci.yml's own comments
describe. So cancellation must be conditional on the event, and that condition
is what a future edit is most likely to get wrong.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"

pytestmark = pytest.mark.skipif(
    not CI.exists(),
    reason=".github/workflows not reachable (e.g. mutation sandbox)")


def concurrency_block(path: Path) -> str:
    """The top-level ``concurrency:`` mapping of a workflow, or ''.

    Top-level only: a job-level block is indented and must not be mistaken for
    the workflow's own policy.
    """
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^concurrency:\s*$\n((?:^[ \t]+\S.*\n|^\s*#.*\n)*)", text, re.M)
    return m.group(1) if m else ""


class TestCiCancelsSupersededRuns:
    def test_ci_declares_a_concurrency_group(self):
        assert concurrency_block(CI), \
            "ci.yml is the biggest workflow here; without a concurrency group " \
            "every superseded push keeps ~36 checks running against nothing"

    def test_the_group_is_per_pull_request(self):
        # Keyed on the PR number so two PRs never cancel each other.
        assert "github.event.pull_request.number" in concurrency_block(CI)

    def test_non_pr_events_group_on_the_commit_not_the_ref(self):
        # THE SUBTLE ONE. `cancel-in-progress: false` does not mean "never
        # cancel" — it means a newer run waits, and GitHub cancels the older
        # *pending* run when a third arrives. Keying main on `github.ref` puts
        # every main push in one group, so three quick merges would leave a
        # middle commit whose ci never completes; publish.yml fires on
        # `workflow_run` of ci, so that commit would never release. A sha is
        # unique per commit, so main and the merge queue never share a group.
        block = concurrency_block(CI)
        assert "github.sha" in block, block
        assert "github.ref" not in block, \
            "grouping non-PR runs on the ref can strand a main commit unreleased"

    def test_cancellation_is_conditional_not_unconditional(self):
        # `cancel-in-progress: true` would cancel main and merge_group runs too.
        block = concurrency_block(CI)
        m = re.search(r"cancel-in-progress:\s*(.+)", block)
        assert m, "no cancel-in-progress in %r" % block
        value = m.group(1).strip()
        assert value not in ("true", "'true'", '"true"'), \
            "unconditional cancel would abandon the run publish.yml gates on"
        assert "pull_request" in value, value

    def test_only_pull_request_events_are_cancelled(self):
        # The whole safety property in one assertion: the guard names
        # pull_request, so push-to-main and merge_group evaluate false.
        value = re.search(r"cancel-in-progress:\s*(.+)",
                          concurrency_block(CI)).group(1)
        assert "github.event_name == 'pull_request'" in value, value


class TestReleasePathIsNeverCancelled:
    def test_publish_does_not_cancel_in_progress(self):
        # Every merge to main cuts a PyPI release; cancelling a release run
        # mid-upload is how you get a tagged version that never shipped.
        block = concurrency_block(WORKFLOWS / "publish.yml")
        assert "cancel-in-progress: false" in block, block

    def test_no_workflow_cancels_a_merge_group_run(self):
        # A required context whose run is cancelled never reports, and the
        # merge queue waits on it forever. Any workflow that both triggers on
        # merge_group and cancels unconditionally is that deadlock waiting to
        # happen.
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            if not re.search(r"^\s*merge_group:", text, re.M):
                continue
            block = concurrency_block(path)
            if re.search(r"cancel-in-progress:\s*true\s*$", block, re.M):
                offenders.append(path.name)
        assert not offenders, \
            "these cancel merge_group runs and would deadlock the queue: %s" \
            % ", ".join(offenders)
