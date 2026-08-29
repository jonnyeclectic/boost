# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: every unattended workflow is watched by the failure alerting.

``ci-failure-issue.yml`` opens a tracking issue when a watched workflow fails on
``main``. Its own header states the rule::

    Any workflow that runs on main and nobody watches belongs here.

It watched two: ``ci`` and ``demo``. Twenty-four run unattended — fourteen on a
cron, ten on a push to ``main`` — so the rule was written down and not applied,
which is the most expensive kind of convention.

Two outages measured this session are exactly what that gap costs:

* ``fuzz`` failed **three scheduled runs out of three** (2026-07-25, 08-01,
  08-08), writing the same libFuzzer reproducer each time. It had found a real
  defect in ``registry.parse_spec`` and been ignored for three weeks.
* ``shards`` failed **both** of its scheduled runs and published zero artifacts,
  which is how a feature reached a state where it had never once worked.

Neither produced a notification, a red badge anyone looks at, or a comment on a
pull request. A cron job's failure is a red square on a page nobody opens.

The list is enforced rather than curated: a new scheduled workflow fails this
test until it is either watched or added to ``EXPECTED_UNWATCHED`` with a
reason. That is the same shape as ``test_action_pin_lockstep``'s parametrised
family check — the convention stays falsifiable instead of decaying the moment
the person who wrote it stops looking.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
ALERT = WORKFLOWS / "ci-failure-issue.yml"

pytestmark = pytest.mark.skipif(
    not ALERT.exists(),
    reason=".github/workflows not reachable (e.g. mutation sandbox)")

#: Unattended workflows deliberately NOT watched, each with its reason.
#: Empty today. An entry here is a claim that a failure is expected noise
#: rather than news, and it should be rare enough to argue about.
EXPECTED_UNWATCHED: dict[str, str] = {}


def workflow_name(text: str, fallback: str) -> str:
    """The workflow's `name:`, which is what `workflow_run` matches on."""
    m = re.search(r"^name:\s*(.+)$", text, re.M)
    return m.group(1).strip().strip("\"'") if m else fallback


def runs_unattended(text: str) -> bool:
    """True for a workflow that runs with nobody waiting on the result.

    A cron run has no author watching by construction. A push to ``main`` runs
    after the pull request's checks are already green and merged, so its failure
    surfaces only on a commit list — which is how ``demo`` failed six runs out
    of six before a manual audit found it.
    """
    return bool(re.search(r"^\s*schedule:", text, re.M)
                or re.search(r"^\s*push:", text, re.M))


def watched() -> set[str]:
    """The workflow names ci-failure-issue.yml subscribes to."""
    m = re.search(r"workflows:\s*\[([^\]]*)\]", ALERT.read_text(encoding="utf-8"))
    assert m, "could not find the workflows: list in ci-failure-issue.yml"
    return {w.strip().strip("\"'") for w in m.group(1).split(",") if w.strip()}


def unattended() -> dict[str, str]:
    """``{workflow name: file name}`` for every unattended workflow."""
    out = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        name = workflow_name(text, path.stem)
        # The alerting workflow itself is triggered by workflow_run, never by a
        # schedule or a push, and watching itself would be a loop.
        if name == "ci-failure-alert":
            continue
        if runs_unattended(text):
            out[name] = path.name
    return out


class TestTheGuardCanActuallySee:
    """Every assertion below is vacuous if the parsing silently breaks."""

    def test_the_watch_list_is_found_and_non_empty(self):
        assert watched(), "parsed an empty watch list"

    def test_unattended_workflows_are_found(self):
        assert len(unattended()) > 5, unattended()

    def test_the_two_original_watchers_are_still_there(self):
        # `demo` is in the list because it failed six of six runs unnoticed.
        # Losing either entry would be a silent regression of that fix.
        assert {"ci", "demo"} <= watched()

    def test_a_known_cron_workflow_is_classified_as_unattended(self):
        assert "fuzz" in unattended(), unattended()


class TestEveryUnattendedWorkflowIsWatched:
    @pytest.mark.parametrize("name", sorted(unattended()))
    def test_it_is_watched_or_documented(self, name):
        if name in EXPECTED_UNWATCHED:
            assert EXPECTED_UNWATCHED[name].strip(), \
                "%s is excluded without a reason" % name
            return
        assert name in watched(), (
            "%s (%s) runs unattended on main but nothing alerts when it fails "
            "— fuzz was red for three scheduled runs and shards for two, both "
            "unnoticed. Add it to ci-failure-issue.yml's `workflows:` list, or "
            "to EXPECTED_UNWATCHED with a reason."
            % (name, unattended()[name]))

    def test_the_exclusion_list_has_no_stale_entries(self):
        # An entry for a workflow that no longer runs unattended is a licence
        # nobody re-examined.
        stale = sorted(set(EXPECTED_UNWATCHED) - set(unattended()))
        assert not stale, stale

    def test_nothing_watched_has_disappeared(self):
        # A watch entry naming a workflow that no longer exists silently
        # watches nothing, and reads as coverage.
        names = {workflow_name(p.read_text(encoding="utf-8"), p.stem)
                 for p in WORKFLOWS.glob("*.yml")}
        assert watched() <= names, sorted(watched() - names)


class TestTheAlertCanStandDown:
    """An alert that cannot close is only half an alert.

    The tracker opened issues, commented on repeats, and never closed one — so
    its own closing line, "close this once CI is green again", was a manual step
    nobody had a reason to take. `visual` stayed open through four consecutive
    green runs, and a list that mixes live outages with fixed ones makes every
    entry in it read as equally suspect.
    """

    def test_a_success_on_main_closes_the_tracker(self):
        text = ALERT.read_text(encoding="utf-8")
        assert "conclusion == 'success'" in text, (
            "nothing reacts to a watched workflow going green, so every "
            "tracker this file opens stays open until someone closes it")
        assert "state: 'closed'" in text

    def test_closing_is_keyed_by_workflow_like_opening(self):
        """A `ci` success must not close a `demo` tracker.

        The opener keys its marker on the workflow name for exactly this
        reason; a closer that matched any `ci-failure` issue would undo that.
        """
        text = ALERT.read_text(encoding="utf-8")
        assert text.count("ci-failure-tracker:${run.name}") >= 2, (
            "the closing half must use the same per-workflow marker the "
            "opening half writes")

    def test_only_main_can_close_it(self):
        """`workflow_run` fires for the default branch, but the opener still
        checks — and an asymmetry here would let a non-main success close a
        tracker for a failure that is still live on main."""
        text = ALERT.read_text(encoding="utf-8")
        assert text.count("head_branch == 'main'") >= 2

    def test_permissions_are_not_granted_workflow_wide(self):
        """`issues: write` at the top reaches every job, including any added
        later. zizmor's excessive-permissions audit fails the build on it."""
        text = ALERT.read_text(encoding="utf-8")
        assert re.search(r"^permissions:\s*\{\}\s*$", text, re.M), \
            "workflow-level permissions must be empty; each job asks for its own"
        assert text.count("issues: write") >= 2
