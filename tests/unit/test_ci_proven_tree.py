# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tests for scripts/ci_proven_tree.py, the "may this push skip mutation" decision.

The script answers one question for a push to ``main``: is the code in this
commit already proven by a green ``ci`` run, so the whole-codebase mutation run
may be skipped? A wrong "yes" ships untested code; a wrong "no" costs one
mutation run. So the property worth pinning is a direction, not a value: every
fact that is unknown, missing, errored or ambiguous must come out as
``skip=false`` with a reason, and only one shape may come out as ``true``.

Nothing here touches the network or binds a socket. ``gather`` and ``main`` take
an injected ``api`` callable, and the real HTTP wrapper (``make_api``) takes an
injected opener, so the headers, timeout and error behaviour are asserted
against a fake. Every file goes through ``tmp_path`` and every environment
variable through ``monkeypatch`` or an explicit ``env`` mapping, so the tests
are safe under ``pytest -n auto``.
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import ANY

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci_proven_tree.py"


def _load():
    # Registered in sys.modules before exec: a dataclass whose annotations are
    # strings (``from __future__ import annotations``) looks its own module up
    # there, and a spec-loaded module is not in it. Per-process, so xdist-safe.
    spec = importlib.util.spec_from_file_location("ci_proven_tree_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pt = _load()

SHA = "a" * 40        # the commit that landed on main
HEAD = "b" * 40       # a PR head
HEAD2 = "c" * 40      # another PR head
# Object ids, because the merge commit's tree names the artifact gather asks
# for, and gather refuses to put anything else into a URL.
TREE = "e" * 40
OTHER = "f" * 40

# The clock every test pins. A test that leaves `now` to the real clock would
# pass or fail depending on the day it runs, once a nightly's age matters --
# and a PR run's age now matters on every candidate that is meant to prove.
NOW = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
NOW_ISO = "2026-10-31T09:00:00+00:00"
ARGV = ["--sha", SHA, "--now", NOW_ISO]

# A PR run an hour old: well inside the 13 days a PR run may prove a tree for.
FRESH = NOW - timedelta(hours=1)



def built(tree="T", *, expired=False, run_id=None):
    """A run's artifact listing holding its record of having built ``tree``."""
    return (pt.Artifact(pt.TESTED_TREE_ARTIFACT + tree, expired, run_id),)


GOOD = pt.Candidate("h", "T", 7, "success", run_created_at=FRESH, artifacts=built())


def hours_before_now(hours):
    """A GitHub-style timestamp `hours` before the pinned clock."""
    return (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def nightly(hours, conclusion="success"):
    return pt.Nightly(conclusion, NOW - timedelta(hours=hours))


# --------------------------------------------------------------------------
# decide: the pure decision
# --------------------------------------------------------------------------

def test_skips_when_tree_matches_a_green_pr_and_nightly_is_green():
    assert pt.decide("T", [GOOD], "success", now=NOW) == pt.Decision(True, ANY, 7)


def test_the_skip_reason_names_the_run_and_the_tree():
    cand = pt.Candidate("h" * 40, "T" * 40, 7, "success", run_created_at=FRESH,
                        artifacts=built("T" * 40))
    decision = pt.decide("T" * 40, [cand], "success", now=NOW)
    assert decision.skip is True
    reason = decision.reason
    assert "7" in reason
    assert "T" * 12 in reason


@pytest.mark.parametrize("cands,last", [
    ([], "success"),                                         # direct push, no PR
    ([pt.Candidate("h", "OTHER", 7, "success")], "success"),  # tree differs
    ([pt.Candidate("h", "T", 7, "cancelled")], "success"),   # PR run not green
    ([pt.Candidate("h", "T", None, None)], "success"),       # PR never ran
    ([GOOD], "failure"),                                     # red nightly -> fallback
    ([GOOD], None),                                          # no nightly yet
])
def test_every_missing_fact_means_a_full_run(cands, last):
    decision = pt.decide("T", cands, last)
    assert decision.skip is False
    assert decision.reason
    assert decision.pr_run_id is None


@pytest.mark.parametrize("conclusion", [
    None,              # still running: GitHub reports a null conclusion
    "failure", "cancelled", "skipped", "neutral", "timed_out",
    "action_required", "stale", "startup_failure",
    "",                # empty string is not "success"
    "SUCCESS",         # the comparison is exact, not case-folded
    "success ",        # nor trimmed
])
def test_only_the_exact_word_success_proves_a_pr_run(conclusion):
    decision = pt.decide("T", [pt.Candidate("h", "T", 7, conclusion)], "success")
    assert decision.skip is False


@pytest.mark.parametrize("last", [
    "failure", "cancelled", "skipped", "neutral", "timed_out", "",
    "SUCCESS", "success ",
])
def test_only_the_exact_word_success_proves_the_nightly(last):
    assert pt.decide("T", [GOOD], last).skip is False


@pytest.mark.parametrize("merge_tree,head_tree", [
    ("", ""),          # two unknowns are not a match
    (None, None),
    ("T", ""),
    ("T", None),
    ("", "T"),
])
def test_two_absent_trees_never_match(merge_tree, head_tree):
    decision = pt.decide(merge_tree, [pt.Candidate("h", head_tree, 7, "success")],
                         "success")
    assert decision.skip is False


@pytest.mark.parametrize("position", [0, 11, 12, 20, 38, 39])
def test_trees_that_differ_in_a_single_character_anywhere_are_not_equal(position):
    # Positions 0-11 are what a reason line shows; 12-39 are what an abbreviated
    # comparison (the easy regression: `tree[:12]`) would never look at.
    merge_tree = "0123456789abcdef0123456789abcdef01234567"
    other = merge_tree[:position] + ("f" if merge_tree[position] != "f" else "e") \
        + merge_tree[position + 1:]
    assert len(other) == len(merge_tree) and other != merge_tree
    decision = pt.decide(merge_tree, [pt.Candidate("h", other, 7, "success")], "success")
    assert decision.skip is False
    assert decision.pr_run_id is None


def test_trees_that_differ_only_in_letter_case_are_not_equal():
    # "Identical" means byte-identical: the comparison is not normalised.
    merge_tree = "0123456789abcdef0123456789abcdef01234567"
    cand = pt.Candidate("h", merge_tree.upper(), 7, "success")
    assert pt.decide(merge_tree, [cand], "success").skip is False


def test_a_tree_that_is_only_a_prefix_of_the_merge_tree_is_not_equal():
    merge_tree = "0123456789abcdef0123456789abcdef01234567"
    for prefix in (merge_tree[:12], merge_tree[:39]):
        cand = pt.Candidate("h", prefix, 7, "success")
        assert pt.decide(merge_tree, [cand], "success").skip is False
    # and the identical 40 characters are the one thing that does match
    assert pt.decide(merge_tree, [pt.Candidate("h", merge_tree, 7, "success",
                                               run_created_at=FRESH,
                                               artifacts=built(merge_tree))],
                     "success", now=NOW).skip is True


@pytest.mark.parametrize("bad", [
    {"run_event": "push"},
    {"run_event": "workflow_dispatch"},
    {"run_event": "pull_request_target"},   # a different trust boundary
    {"run_event": ""},
    {"run_head_sha": "some-other-head"},
    {"run_head_sha": ""},                   # unknown is not "same"
    {"run_attempt": 2},                     # a re-run is not first-attempt proof
    {"run_attempt": 0},                     # unknown attempt
])
def test_the_run_must_be_this_heads_first_pull_request_run(bad):
    cand = pt.Candidate("h", "T", 7, "success", **bad)
    decision = pt.decide("T", [cand], "success")
    assert decision.skip is False
    assert "7" in decision.reason


@pytest.mark.parametrize("run_id", [None, True, "7", 7.0])
def test_a_run_id_that_is_not_an_int_is_no_run(run_id):
    # bool is an int subclass, and a JSON `true` must not read as run 1.
    cand = pt.Candidate("h", "T", run_id, "success")
    assert pt.decide("T", [cand], "success").skip is False


def test_a_candidate_without_a_head_sha_is_not_proof():
    assert pt.decide("T", [pt.Candidate("", "T", 7, "success")], "success").skip is False


def test_several_prs_none_matching_is_a_full_run_and_says_why_for_each():
    cands = [pt.Candidate("h1", "X1", 1, "success"),
             pt.Candidate("h2", "X2", 2, "success"),
             pt.Candidate("h3", "T", 3, "failure")]
    decision = pt.decide("T", cands, "success")
    assert decision.skip is False
    for needle in ("h1", "h2", "h3"):
        assert needle in decision.reason


def test_a_later_pr_may_be_the_proof_and_its_run_is_reported():
    cands = [pt.Candidate("h1", "T", 1, "failure"),     # same tree, red run
             pt.Candidate("h2", "X", 2, "success"),     # green run, other tree
             pt.Candidate("h3", "T", 3, "success", run_created_at=FRESH,
                          artifacts=built())]                     # the proof
    assert pt.decide("T", cands, "success", now=NOW) == pt.Decision(True, ANY, 3)


def test_a_proven_tree_with_a_red_nightly_still_runs_everything():
    decision = pt.decide("T", [GOOD], "failure")
    assert decision.skip is False
    assert "failure" in decision.reason


def test_an_unfinished_run_says_it_is_still_running():
    decision = pt.decide("T", [pt.Candidate("h", "T", 7, None)], "success")
    assert decision.skip is False
    assert "still running" in decision.reason


def test_the_reason_for_no_nightly_is_not_blamed_on_the_pr():
    decision = pt.decide("T", [GOOD], None)
    assert decision.skip is False
    assert "nightly" in decision.reason


def test_an_unknown_merge_tree_is_a_full_run():
    decision = pt.decide("", [GOOD], "success")
    assert decision.skip is False
    assert "tree is unknown" in decision.reason


def test_a_long_candidate_list_gives_a_bounded_reason():
    cands = [pt.Candidate("h%d" % i, "X", i + 1, "success") for i in range(40)]
    assert len(pt.decide("T", cands, "success").reason) < 1500


# --------------------------------------------------------------------------
# decide: the nightly has to be recent, not just green
# --------------------------------------------------------------------------
# The age limit is 48 hours: one missed night is tolerated, two are not. Without
# a bound, a nightly that quietly stopped running (a disabled workflow, dropped
# schedules) would keep a months-old green result authorising skips forever.

def test_a_nightly_47_hours_old_still_allows_the_skip():
    assert pt.decide("T", [GOOD], nightly(47), now=NOW) == pt.Decision(True, ANY, 7)


def test_a_nightly_exactly_48_hours_old_is_still_fresh():
    # "More than 48 hours" is the rule, so the boundary itself is on the safe-to-skip side.
    assert pt.decide("T", [GOOD], nightly(48), now=NOW).skip is True


def test_a_nightly_one_second_past_48_hours_is_stale():
    just_over = pt.Nightly("success", NOW - timedelta(hours=48, seconds=1))
    decision = pt.decide("T", [GOOD], just_over, now=NOW)
    assert decision.skip is False
    assert "nightly stale" in decision.reason


def test_a_nightly_49_hours_old_is_stale_and_says_so():
    decision = pt.decide("T", [GOOD], nightly(49), now=NOW)
    assert decision.skip is False
    assert decision.pr_run_id is None
    assert "nightly stale (49h)" in decision.reason


def test_the_age_in_the_reason_never_rounds_down_to_a_fresh_looking_number():
    # 48h and 1s must not be reported as "48h", which reads as not stale.
    just_over = pt.Nightly("success", NOW - timedelta(hours=48, seconds=1))
    assert "nightly stale (48.1h)" in pt.decide("T", [GOOD], just_over, now=NOW).reason
    half = pt.Nightly("success", NOW - timedelta(hours=60, minutes=30))
    assert "nightly stale (60.5h)" in pt.decide("T", [GOOD], half, now=NOW).reason


def test_a_nightly_with_no_creation_time_is_never_fresh():
    decision = pt.decide("T", [GOOD], pt.Nightly("success", None), now=NOW)
    assert decision.skip is False
    assert "nightly age unknown" in decision.reason


def test_a_nightly_dated_in_the_future_is_not_trusted():
    # A few seconds of skew between GitHub's clock and the runner's is normal;
    # a nightly from tomorrow is a corrupt fact, and an unknown one means a full run.
    decision = pt.decide("T", [GOOD], nightly(-24), now=NOW)
    assert decision.skip is False
    assert "future" in decision.reason


def test_a_nightly_a_minute_ahead_of_the_runner_clock_is_just_skew():
    assert pt.decide("T", [GOOD], nightly(-1 / 60), now=NOW).skip is True


def test_a_red_nightly_is_reported_red_and_a_stale_one_stale_and_both_when_both():
    red = pt.decide("T", [GOOD], nightly(1, "failure"), now=NOW)
    assert "failure" in red.reason and "stale" not in red.reason
    both = pt.decide("T", [GOOD], nightly(100, "failure"), now=NOW)
    assert "failure" in both.reason and "nightly stale (100h)" in both.reason


def test_a_stale_nightly_does_not_hide_a_tree_mismatch():
    decision = pt.decide("T", [pt.Candidate("h", "X", 7, "success")], nightly(100), now=NOW)
    assert "differs" in decision.reason and "nightly stale" in decision.reason


def test_decide_reads_the_real_clock_when_not_given_one():
    real_now = datetime.now(UTC)
    fresh = pt.Nightly("success", real_now - timedelta(hours=1))
    old = pt.Nightly("success", real_now - timedelta(hours=100))
    cand = pt.Candidate("h", "T", 7, "success", run_created_at=real_now - timedelta(hours=1),
                        artifacts=built())
    assert pt.decide("T", [cand], fresh).skip is True
    assert pt.decide("T", [cand], old).skip is False
    # ... for the PR run's age as well as the nightly's.
    stale = pt.Candidate("h", "T", 7, "success", run_created_at=real_now - timedelta(days=14),
                         artifacts=built())
    assert pt.decide("T", [stale], fresh).skip is False


# --- the PR run's age: the badge reads its coverage-report ------------------
#
# On a proven push ci.yml's `coverage-badge` downloads `coverage-report` from
# the PR run this script names, and that artifact is kept 14 days. A PR run
# older than 13 days is therefore not proof: the push runs everything, which
# also gives the badge a report of its own. Exactly 13 days still counts, as
# exactly 48 hours does for the nightly.

def pr_run_aged(age, **kwargs):
    kwargs.setdefault("artifacts", built())
    return pt.Candidate("h", "T", 7, "success", run_created_at=NOW - age, **kwargs)


@pytest.mark.parametrize("age, skip", [
    (timedelta(0), True),
    (timedelta(days=12), True),
    (timedelta(days=13), True),
    (timedelta(days=13, seconds=1), False),
    (timedelta(days=14), False),
    (timedelta(days=90), False),
])
def test_a_pr_run_proves_its_tree_for_13_days(age, skip):
    assert pt.decide("T", [pr_run_aged(age)], "success", now=NOW).skip is skip


def test_a_stale_pr_run_says_how_old_it_is_and_why_that_matters():
    reason = pt.decide("T", [pr_run_aged(timedelta(days=14))], "success", now=NOW).reason
    assert "ci run 7" in reason
    assert "14 days old" in reason
    assert "coverage-report" in reason


def test_a_pr_run_just_past_13_days_never_reads_as_13():
    reason = pt.decide("T", [pr_run_aged(timedelta(days=13, seconds=1))], "success",
                       now=NOW).reason
    assert "13.1 days old" in reason


def test_a_pr_run_with_no_creation_time_is_not_proof():
    cand = pt.Candidate("h", "T", 7, "success")     # run_created_at defaults to None
    decision = pt.decide("T", [cand], "success", now=NOW)
    assert decision.skip is False
    assert "created_at unknown" in decision.reason


def test_a_pr_run_dated_in_the_future_is_not_trusted():
    decision = pt.decide("T", [pr_run_aged(-timedelta(hours=2))], "success", now=NOW)
    assert decision.skip is False
    assert "in the future" in decision.reason
    # a minute of skew between GitHub's clock and the runner's is not that
    assert pt.decide("T", [pr_run_aged(-timedelta(minutes=1))], "success",
                     now=NOW).skip is True


def test_a_stale_pr_run_is_judged_after_everything_cheaper_to_explain():
    # A red, stale run is reported red: the age is the last thing checked.
    cand = pt.Candidate("h", "T", 7, "failure", run_created_at=NOW - timedelta(days=30))
    assert "concluded failure" in pt.decide("T", [cand], "success", now=NOW).reason


# --------------------------------------------------------------------------
# a fake GitHub for gather() and main()
# --------------------------------------------------------------------------

class Unrouted(Exception):
    pass


class FakeApi:
    """A path -> value table. A value that is an exception is raised, and a path
    nobody routed fails loudly instead of returning something plausible."""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls: list[str] = []

    def __call__(self, path):
        self.calls.append(path)
        if path not in self.routes:
            raise Unrouted(path)
        value = self.routes[path]
        if isinstance(value, BaseException):
            raise value
        return value


def commit(tree):
    return {"tree": {"sha": tree}}


def pr(head, base="main"):
    return {"number": 1, "head": {"sha": head}, "base": {"ref": base}}


def run(run_id=7, *, conclusion="success", event="pull_request", head_sha=HEAD,
        attempt=1, created="2026-10-30T10:00:00Z", status="completed",
        head_branch=None):
    # A schedule or dispatch run of `ci` belongs to main; a pull_request run's
    # head_branch is the PR's own branch.
    if head_branch is None:
        head_branch = "feature/x" if event == "pull_request" else "main"
    return {"id": run_id, "event": event, "head_sha": head_sha, "status": status,
            "conclusion": conclusion, "run_attempt": attempt, "created_at": created,
            "head_branch": head_branch}


def runs(*items):
    return {"total_count": len(items), "workflow_runs": list(items)}


def pr_runs_path(head):
    return "actions/workflows/ci.yml/runs?head_sha=%s&event=pull_request" % head


def artifacts_path(run_id, tree=TREE):
    return "actions/runs/%d/artifacts?name=tested-tree-%s" % (run_id, tree)


def artifact(tree=TREE, *, run_id=7, expired=False):
    """One entry of a run's artifact listing, as the API spells it."""
    return {"id": 900 + run_id, "name": "tested-tree-%s" % tree, "expired": expired,
            "workflow_run": {"id": run_id, "head_sha": HEAD}}


def artifacts(*items):
    return {"total_count": len(items), "artifacts": list(items)}


def whole_path(event):
    return ("actions/workflows/ci.yml/runs?branch=main&status=completed"
            "&event=%s&per_page=1" % event)


SCHEDULE = whole_path("schedule")
DISPATCH = whole_path("workflow_dispatch")


def green_routes(**overrides):
    """A push that is fully proven: one PR, equal trees, green run, green nightly.

    Every PR run any listing here returns recorded building this commit's
    tree -- the artifact listing for it is filled in unless a test routed it
    itself -- so a test about something else stays about that.
    """
    routes = {
        "git/commits/%s" % SHA: commit(TREE),
        "commits/%s/pulls" % SHA: [pr(HEAD)],
        "git/commits/%s" % HEAD: commit(TREE),
        pr_runs_path(HEAD): runs(run()),
        SCHEDULE: runs(run(100, event="schedule", head_sha=SHA)),
        DISPATCH: runs(),
    }
    routes.update(overrides)
    for path, listing in list(routes.items()):
        if not path.startswith("actions/workflows/ci.yml/runs?head_sha="):
            continue
        found = listing.get("workflow_runs") if isinstance(listing, dict) else None
        for item in found if isinstance(found, list) else ():
            ident = item.get("id") if isinstance(item, dict) else None
            if isinstance(ident, int) and not isinstance(ident, bool):
                routes.setdefault(artifacts_path(ident),
                                  artifacts(artifact(run_id=ident)))
    return routes


# --------------------------------------------------------------------------
# gather: what it asks GitHub, and what it makes of the answers
# --------------------------------------------------------------------------

def test_gather_assembles_the_three_facts_decide_needs():
    api = FakeApi(green_routes())
    merge_tree, cands, last = pt.gather(api, SHA)
    assert merge_tree == TREE
    assert cands == [pt.Candidate(HEAD, TREE, 7, "success", "pull_request", HEAD, 1,
                                  datetime(2026, 10, 30, 10, tzinfo=UTC),
                                  (pt.Artifact("tested-tree-" + TREE, False, 7),))]
    assert last == pt.Nightly("success", datetime(2026, 10, 30, 10, tzinfo=UTC))
    assert pt.decide(merge_tree, cands, last, now=NOW) == pt.Decision(True, ANY, 7)


def test_gather_asks_the_documented_endpoints_and_nothing_else():
    api = FakeApi(green_routes())
    pt.gather(api, SHA)
    assert sorted(api.calls) == sorted([
        "git/commits/%s" % SHA,
        "commits/%s/pulls" % SHA,
        "git/commits/%s" % HEAD,
        pr_runs_path(HEAD),
        artifacts_path(7),
        SCHEDULE,
        DISPATCH,
    ])


def test_gather_picks_the_newest_whole_codebase_run():
    # schedule run 'failure' created later than the dispatch run 'success'
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(2, event="schedule", conclusion="failure",
                           created="2026-10-31T09:30:00Z")),
        DISPATCH: runs(run(1, event="workflow_dispatch", conclusion="success",
                           created="2026-10-30T15:00:00Z")),
    }))
    assert pt.gather(api, SHA)[2].conclusion == "failure"


def test_gather_picks_the_newest_whole_codebase_run_whichever_query_it_came_from():
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(1, event="schedule", conclusion="failure",
                           created="2026-10-30T09:30:00Z")),
        DISPATCH: runs(run(2, event="workflow_dispatch", conclusion="success",
                           created="2026-10-31T11:00:00Z")),
    }))
    assert pt.gather(api, SHA)[2].conclusion == "success"


def test_gather_compares_instants_not_strings():
    # 23:00-05:00 is 04:00Z the next day: later than 01:00Z, though it sorts earlier.
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(1, event="schedule", conclusion="success",
                           created="2026-10-31T01:00:00+00:00")),
        DISPATCH: runs(run(2, event="workflow_dispatch", conclusion="failure",
                           created="2026-10-30T23:00:00-05:00")),
    }))
    assert pt.gather(api, SHA)[2].conclusion == "failure"


def test_gather_uses_the_one_whole_codebase_query_that_has_a_run():
    only_dispatch = FakeApi(green_routes(**{
        SCHEDULE: runs(),
        DISPATCH: runs(run(1, event="workflow_dispatch", conclusion="success")),
    }))
    assert pt.gather(only_dispatch, SHA)[2].conclusion == "success"


def test_gather_reports_no_nightly_when_both_queries_are_empty():
    api = FakeApi(green_routes(**{SCHEDULE: runs(), DISPATCH: runs()}))
    assert pt.gather(api, SHA)[2] is None


def test_one_failing_whole_codebase_query_is_unknown_not_a_fallback():
    # Falling back to the other query would read a stale green nightly as
    # current; the answer is "unknown", which gather expresses by raising.
    api = FakeApi(green_routes(**{
        SCHEDULE: urllib.error.URLError("boom"),
        DISPATCH: runs(run(1, event="workflow_dispatch", conclusion="success")),
    }))
    with pytest.raises(urllib.error.URLError):
        pt.gather(api, SHA)


def test_the_other_whole_codebase_query_failing_is_also_unknown():
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(1, event="schedule", conclusion="success")),
        DISPATCH: urllib.error.URLError("boom"),
    }))
    with pytest.raises(urllib.error.URLError):
        pt.gather(api, SHA)


def test_a_nightly_run_that_is_not_completed_has_no_conclusion():
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(1, event="schedule", conclusion="success",
                           status="in_progress")),
    }))
    assert pt.gather(api, SHA)[2] is None


@pytest.mark.parametrize("path", [SCHEDULE, DISPATCH])
@pytest.mark.parametrize("branch", ["feature/x", "main-old", "refs/heads/main", "Main",
                                    "master", "", None, 7, "missing"])
def test_a_whole_codebase_run_not_on_main_is_unknown_not_a_nightly(path, branch):
    # A workflow_dispatch on a feature branch is a normal thing to do, and its
    # result says nothing about main. The query asks for branch=main; the answer
    # is checked too, and a run with no branch at all is not vouched for either.
    event = "schedule" if path == SCHEDULE else "workflow_dispatch"
    off_main = run(100, event=event)
    if branch == "missing":
        del off_main["head_branch"]
    else:
        off_main["head_branch"] = branch
    api = FakeApi(green_routes(**{path: runs(off_main)}))
    with pytest.raises(ValueError, match="main"):
        pt.gather(api, SHA)


def test_main_a_nightly_from_another_branch_is_a_full_run(gh_env):
    off_main = run(100, event="schedule", head_branch="feature/x",
                   created=hours_before_now(1))
    api = FakeApi(green_routes(**{SCHEDULE: runs(off_main)}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "error: ValueError" in _summary(gh_env)


def test_a_green_dispatch_on_a_feature_branch_does_not_rescue_a_red_nightly(gh_env):
    # The off-main run is newer and green; it must not be read as "the latest".
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(100, event="schedule", conclusion="failure",
                           created=hours_before_now(30))),
        DISPATCH: runs(run(101, event="workflow_dispatch", head_branch="feature/x",
                           created=hours_before_now(1)))}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env)["skip"] == "false"


def test_a_nightly_run_of_the_wrong_event_is_not_trusted():
    api = FakeApi(green_routes(**{SCHEDULE: runs(run(1, event="push"))}))
    with pytest.raises(ValueError):
        pt.gather(api, SHA)


def test_unorderable_whole_codebase_runs_are_an_error_not_a_guess():
    for created in (None, "", "not a date", "2026-10-31T09:30:00"):  # last: no zone
        bad = run(1, event="schedule", created=created)
        if created is None:
            del bad["created_at"]
        api = FakeApi(green_routes(**{
            SCHEDULE: runs(bad),
            DISPATCH: runs(run(2, event="workflow_dispatch")),
        }))
        with pytest.raises(ValueError):
            pt.gather(api, SHA)


def test_a_lone_whole_codebase_run_is_gathered_without_a_usable_timestamp():
    # Gathering records what it found; deciding is what refuses an undated run.
    for created in (None, "", "not a date", "2026-10-31T09:30:00", 12345):
        lone = run(1, event="schedule", conclusion="success", created=created)
        if created is None:
            del lone["created_at"]
        api = FakeApi(green_routes(**{SCHEDULE: runs(lone)}))
        assert pt.gather(api, SHA)[2] == pt.Nightly("success", None)


def test_the_nightly_keeps_its_creation_time_as_an_instant():
    api = FakeApi(green_routes(**{SCHEDULE: runs(run(
        1, event="schedule", created="2026-10-30T23:00:00-05:00"))}))
    assert pt.gather(api, SHA)[2].created_at == datetime(2026, 10, 31, 4, tzinfo=UTC)


def test_the_newest_pr_run_wins_by_timestamp_not_by_list_position():
    older_green = run(1, conclusion="success", created="2026-10-30T10:00:00Z")
    newer_running = run(2, conclusion=None, status="in_progress",
                        created="2026-10-30T11:00:00Z")
    for listing in ([older_green, newer_running], [newer_running, older_green]):
        api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(*listing)}))
        _, cands, _ = pt.gather(api, SHA)
        assert cands[0].run_id == 2
        assert cands[0].conclusion is None
        assert pt.decide(TREE, cands, "success").skip is False


def test_a_newer_red_run_beats_an_older_green_one():
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(
        run(2, conclusion="failure", created="2026-10-30T11:00:00Z"),
        run(1, conclusion="success", created="2026-10-30T10:00:00Z"))}))
    _, cands, _ = pt.gather(api, SHA)
    assert pt.decide(TREE, cands, "success").skip is False


def test_equal_timestamps_are_broken_by_run_id():
    stamp = "2026-10-30T10:00:00Z"
    for listing in ([run(5, conclusion="failure", created=stamp),
                     run(9, conclusion="success", created=stamp)],
                    [run(9, conclusion="success", created=stamp),
                     run(5, conclusion="failure", created=stamp)]):
        api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(*listing)}))
        assert pt.gather(api, SHA)[1][0].run_id == 9


@pytest.mark.parametrize("wrong", [
    {"event": "push"},
    {"event": "workflow_dispatch"},
    {"head_sha": HEAD2},
    {"attempt": 2},
])
def test_a_run_the_query_should_not_have_returned_is_rejected_by_decide(wrong):
    # The query filters by head_sha and event; the answer is checked anyway.
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(run(**wrong))}))
    merge_tree, cands, last = pt.gather(api, SHA)
    assert pt.decide(merge_tree, cands, last, now=NOW).skip is False


@pytest.mark.parametrize("missing", ["event", "head_sha", "run_attempt"])
def test_a_run_missing_a_fact_decide_checks_is_not_proof(missing):
    # Absent is unknown, and unknown is never defaulted into "fine".
    bare = run()
    del bare[missing]
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(bare)}))
    merge_tree, cands, last = pt.gather(api, SHA)
    assert pt.decide(merge_tree, cands, last, now=NOW).skip is False


# GitHub's run `status` values besides "completed". A stale `conclusion` riding on
# any of them (a re-run resets the status first) must not be read as a result.
NOT_COMPLETED = ["queued", "waiting", "requested", "pending", "in_progress",
                 "", "banana", "COMPLETED"]


@pytest.mark.parametrize("status", NOT_COMPLETED)
def test_a_pr_run_in_any_status_but_completed_is_unfinished(status):
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(
        run(conclusion="success", status=status))}))
    merge_tree, cands, last = pt.gather(api, SHA)
    assert cands[0].conclusion is None
    decision = pt.decide(merge_tree, cands, last, now=NOW)
    assert decision.skip is False
    assert "still running" in decision.reason


@pytest.mark.parametrize("status", NOT_COMPLETED)
def test_a_nightly_in_any_status_but_completed_is_not_a_result(status):
    api = FakeApi(green_routes(**{SCHEDULE: runs(
        run(100, event="schedule", conclusion="success", status=status))}))
    merge_tree, cands, last = pt.gather(api, SHA)
    assert last is None
    assert pt.decide(merge_tree, cands, last, now=NOW).skip is False


@pytest.mark.parametrize("status", NOT_COMPLETED)
def test_main_a_run_in_any_status_but_completed_is_a_full_run(tmp_path, status):
    for name, routes in (
            ("pr", green_routes(**{pr_runs_path(HEAD): runs(run(status=status))})),
            ("nightly", green_routes(**{SCHEDULE: runs(
                run(100, event="schedule", status=status))}))):
        env = {"GITHUB_OUTPUT": str(tmp_path / name)}
        assert pt.main(ARGV, api=FakeApi(routes), env=env) == 0
        assert _outputs(env) == {"skip": "false", "pr_run_id": ""}


def test_a_pr_run_that_is_not_completed_has_no_conclusion():
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(
        run(conclusion="success", status="in_progress"))}))
    assert pt.gather(api, SHA)[1][0].conclusion is None


def test_a_pr_run_without_an_integer_id_is_no_run():
    for bad_id in (None, "7", True, 7.5):
        broken = run()
        broken["id"] = bad_id
        api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(broken)}))
        assert pt.gather(api, SHA)[1][0].run_id is None


def test_a_head_that_never_ran_ci_is_a_candidate_without_a_run():
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs()}))
    assert pt.gather(api, SHA)[1] == [pt.Candidate(HEAD, TREE, None, None)]


def test_several_prs_each_get_their_own_tree_and_run():
    api = FakeApi(green_routes(**{
        "commits/%s/pulls" % SHA: [pr(HEAD), pr(HEAD2)],
        "git/commits/%s" % HEAD2: commit(OTHER),
        pr_runs_path(HEAD2): runs(run(8, head_sha=HEAD2, conclusion="failure")),
    }))
    _, cands, _ = pt.gather(api, SHA)
    assert [(c.head_sha, c.head_tree, c.run_id) for c in cands] == [
        (HEAD, TREE, 7), (HEAD2, OTHER, 8)]


def test_two_prs_with_one_head_are_asked_about_once():
    api = FakeApi(green_routes(**{"commits/%s/pulls" % SHA: [pr(HEAD), pr(HEAD)]}))
    assert len(pt.gather(api, SHA)[1]) == 1
    assert api.calls.count("git/commits/%s" % HEAD) == 1


def test_no_associated_pr_is_a_direct_push():
    api = FakeApi(green_routes(**{"commits/%s/pulls" % SHA: []}))
    _, cands, _ = pt.gather(api, SHA)
    assert cands == []
    assert not any(c.startswith("git/commits/%s" % HEAD) for c in api.calls)


@pytest.mark.parametrize("base", [
    {"ref": "release/1.x"}, {"ref": "master"}, {"ref": "Main"}, {"ref": "main-old"},
    {"ref": "refs/heads/main"}, {"ref": ""}, {"ref": None}, {"ref": 7}, {},
    None, "main",
])
def test_a_pr_into_another_branch_is_not_a_candidate(base):
    # A pull_request run builds the PR merged into ITS base, so a PR aimed at
    # another branch tested a different tree and proves nothing about main's.
    aimed_elsewhere = {"number": 1, "head": {"sha": HEAD}, "base": base}
    api = FakeApi(green_routes(**{"commits/%s/pulls" % SHA: [aimed_elsewhere]}))
    _, cands, _ = pt.gather(api, SHA)
    assert cands == []
    assert not any("git/commits/%s" % HEAD in c or HEAD in c for c in api.calls)


def test_a_pr_with_no_base_at_all_is_not_a_candidate():
    api = FakeApi(green_routes(**{
        "commits/%s/pulls" % SHA: [{"number": 1, "head": {"sha": HEAD}}]}))
    assert pt.gather(api, SHA)[1] == []


def test_only_the_prs_into_main_are_asked_about():
    api = FakeApi(green_routes(**{
        "commits/%s/pulls" % SHA: [pr(HEAD, base="release/1.x"), pr(HEAD2)],
        "git/commits/%s" % HEAD2: commit(TREE),
        pr_runs_path(HEAD2): runs(run(8, head_sha=HEAD2)),
    }))
    _, cands, _ = pt.gather(api, SHA)
    assert [c.head_sha for c in cands] == [HEAD2]
    assert "git/commits/%s" % HEAD not in api.calls
    assert pr_runs_path(HEAD) not in api.calls


def test_main_a_green_pr_into_another_branch_does_not_prove_a_push_to_main(gh_env):
    api = FakeApi(green_routes(**{
        "commits/%s/pulls" % SHA: [pr(HEAD, base="release/1.x")]}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "no pull request into main" in _summary(gh_env)


def test_a_pr_entry_with_no_usable_head_is_dropped_not_queried():
    junk = [{"head": {}}, {"head": None}, {"number": 3}, "junk", None, 7,
            {"head": {"sha": "../../etc/passwd"}}, {"head": {"sha": "short"}},
            {"head": {"sha": 123}}, pr(HEAD)]
    api = FakeApi(green_routes(**{"commits/%s/pulls" % SHA: junk}))
    _, cands, _ = pt.gather(api, SHA)
    assert [c.head_sha for c in cands] == [HEAD]
    assert all(c in api.routes for c in api.calls)   # nothing outside the table


@pytest.mark.parametrize("answer", [
    {},                                   # no tree at all
    {"tree": {}},
    {"tree": {"sha": ""}},
    {"tree": {"sha": None}},
    {"tree": {"sha": 5}},
    {"tree": None},
    {"tree": "abc"},
    [],
    "text",
    None,
])
def test_a_missing_tree_sha_is_an_error_for_the_merge_commit(answer):
    api = FakeApi(green_routes(**{"git/commits/%s" % SHA: answer}))
    with pytest.raises(ValueError, match="tree"):
        pt.gather(api, SHA)


def test_a_missing_tree_sha_is_an_error_for_a_pr_head_too():
    api = FakeApi(green_routes(**{"git/commits/%s" % HEAD: {"tree": {}}}))
    with pytest.raises(ValueError, match="tree"):
        pt.gather(api, SHA)


@pytest.mark.parametrize("answer", [
    {"message": "API rate limit exceeded"},   # an error body that arrived as a 200
    None,
    "nope",
    {"workflow_runs": None},
    {"workflow_runs": "x"},
    {},
    {"workflow_runs": [1, 2]},
])
def test_a_malformed_listing_is_an_error_not_an_empty_list(answer):
    for path in ("commits/%s/pulls" % SHA, pr_runs_path(HEAD), SCHEDULE, DISPATCH):
        api = FakeApi(green_routes(**{path: answer}))
        with pytest.raises(ValueError):
            pt.gather(api, SHA)


def test_gather_does_not_swallow_api_errors():
    for exc in (urllib.error.HTTPError("u", 404, "Not Found", None, None),
                TimeoutError("slow"), json.JSONDecodeError("bad", "x", 0)):
        api = FakeApi(green_routes(**{"git/commits/%s" % SHA: exc}))
        with pytest.raises(type(exc)):
            pt.gather(api, SHA)


# --------------------------------------------------------------------------
# main: the CLI contract, driven through an injected api
# --------------------------------------------------------------------------

@pytest.fixture
def gh_env(tmp_path):
    """An explicit environment mapping: nothing leaks in from the runner."""
    out = tmp_path / "github_output"
    summary = tmp_path / "step_summary"
    return {"GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary)}


def _outputs(env):
    text = Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8")
    pairs = dict(line.split("=", 1) for line in text.splitlines())
    assert text.endswith("\n")
    assert len(text.splitlines()) == len(pairs) == 2
    return pairs


def _summary(env):
    return Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")


def test_main_writes_skip_true_and_the_run_id_for_a_proven_tree(gh_env):
    rc = pt.main(ARGV, api=FakeApi(green_routes()), env=gh_env)
    assert rc == 0
    assert _outputs(gh_env) == {"skip": "true", "pr_run_id": "7"}
    assert "7" in _summary(gh_env)


@pytest.mark.parametrize("exc", [
    urllib.error.HTTPError("u", 404, "Not Found", None, None),
    urllib.error.HTTPError("u", 403, "rate limit exceeded", None, None),
    urllib.error.HTTPError("u", 429, "Too Many Requests", None, None),
    urllib.error.HTTPError("u", 500, "Server Error", None, None),
    urllib.error.URLError("no route to host"),
    TimeoutError("timed out"),
    ConnectionResetError("reset"),
    json.JSONDecodeError("Expecting value", "<html>", 0),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
    KeyError("tree"),
    ValueError("odd"),
    RuntimeError("anything at all"),
])
def test_api_errors_mean_a_full_run(gh_env, exc):
    api = FakeApi(green_routes(**{"git/commits/%s" % SHA: exc}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "error: %s" % type(exc).__name__ in _summary(gh_env)


def test_an_error_late_in_gathering_still_means_a_full_run(gh_env):
    # The PR was proven; the nightly lookup then fails. Nothing partial counts.
    api = FakeApi(green_routes(**{DISPATCH: urllib.error.URLError("boom")}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env)["skip"] == "false"


def test_the_error_reason_is_exactly_error_and_the_type(gh_env):
    api = FakeApi(green_routes(**{"git/commits/%s" % SHA:
                                  urllib.error.HTTPError("u", 403, "x", None, None)}))
    pt.main(ARGV, api=api, env=gh_env)
    assert "reason: error: HTTPError\n" in _summary(gh_env)


def test_an_unproven_push_writes_skip_false_with_its_reason(gh_env):
    api = FakeApi(green_routes(**{"commits/%s/pulls" % SHA: []}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "no pull request" in _summary(gh_env)


def test_main_appends_to_the_output_file_instead_of_replacing_it(gh_env):
    Path(gh_env["GITHUB_OUTPUT"]).write_text("earlier=step\n", encoding="utf-8")
    pt.main(ARGV, api=FakeApi(green_routes()), env=gh_env)
    text = Path(gh_env["GITHUB_OUTPUT"]).read_text(encoding="utf-8")
    assert text.startswith("earlier=step\n")
    assert text.endswith("skip=true\npr_run_id=7\n")


def test_api_sourced_text_cannot_add_lines_to_the_outputs_the_log_or_the_summary(
        gh_env, capsys):
    hostile = "failure\nskip=true\n::error::injected\n## pwned\r\n more"
    api = FakeApi(green_routes(**{SCHEDULE: runs(run(1, event="schedule",
                                                     conclusion=hostile))}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    summary = _summary(gh_env)
    assert "injected" in summary                       # the facts are kept ...
    assert "\r" not in summary and " " not in summary
    reason_lines = [ln for ln in summary.splitlines() if ln.startswith("- reason:")]
    assert len(reason_lines) == 1                      # ... on a single line
    assert not any(ln.startswith(("## pwned", "skip=", "::"))
                   for ln in summary.splitlines())
    captured = capsys.readouterr()
    assert not any(ln.startswith("::") for ln in captured.out.splitlines())
    assert len(captured.out.strip().splitlines()) == 1


def test_oneline_flattens_every_kind_of_line_break_and_control_character():
    assert pt._oneline("a\nb\r\n\tc d e\x85f\x00g\x1bh") == "a b c d e f g h"
    assert pt._oneline("  spaced   out  ") == "spaced out"
    assert pt._oneline("") == ""


def test_oneline_bounds_the_length():
    assert len(pt._oneline("x" * 10_000)) <= 600


def test_without_github_output_the_outputs_go_to_stdout(capsys):
    env: dict[str, str] = {}
    assert pt.main(ARGV, api=FakeApi(green_routes()), env=env) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "skip=true" in lines and "pr_run_id=7" in lines


def test_an_unwritable_output_path_still_exits_zero(tmp_path, capsys):
    env = {"GITHUB_OUTPUT": str(tmp_path), "GITHUB_STEP_SUMMARY": str(tmp_path)}  # dirs
    assert pt.main(ARGV, api=FakeApi(green_routes()), env=env) == 0
    assert "GITHUB_OUTPUT" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    [],                                  # no --sha
    ["--sha"],
    ["--sha", ""],
    ["--sha", "main"],                   # a ref, not a commit
    ["--sha", "A" * 40],                 # GitHub's shas are lower-case
    ["--sha", "a" * 39],
    ["--sha", "../../x"],
    ["--sha", SHA, "--surprise"],
])
def test_a_bad_command_line_is_a_full_run_not_a_crash(gh_env, argv):
    api = FakeApi({})   # any request at all would raise Unrouted
    assert pt.main(argv, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert api.calls == []


# --- the run must have recorded building THIS tree --------------------------
#
# A PR run is found by its head SHA, and a pull_request run builds that head
# merged into whichever base the PR had when the run started. A PR retargeted
# to main afterwards (a base change starts no run), or the same head open into
# a second base, leaves a green run on the head whose head tree equals the
# tree that landed -- while the run built that head plus another branch. Only
# the run's own `tested-tree-<tree>` artifact says which tree it built.

def test_decide_does_not_skip_on_a_run_that_never_said_what_it_built():
    bare = pt.Candidate("h", "T", 7, "success", run_created_at=FRESH)
    decision = pt.decide("T", [bare], "success", now=NOW)
    assert decision.skip is False
    assert "ci run 7 left no tested-tree-T artifact" in decision.reason


@pytest.mark.parametrize("record", [
    built("OTHER"),                                   # it built another tree
    built("T", expired=True),                         # the record is gone
    (pt.Artifact("tested-tree-T", None),),            # no `expired` is not live
    built("T", run_id=8),                             # another run's record
    (pt.Artifact("tested-tree-Tx", False),),          # not exactly the name
    (pt.Artifact("TESTED-TREE-T", False),),
    (pt.Artifact("", False),),
])
def test_only_this_runs_live_record_of_this_tree_proves_it(record):
    cand = pt.Candidate("h", "T", 7, "success", run_created_at=FRESH, artifacts=record)
    assert pt.decide("T", [cand], "success", now=NOW).skip is False


def test_an_expired_record_is_reported_as_expired():
    cand = pt.Candidate("h", "T", 7, "success", run_created_at=FRESH,
                        artifacts=built("T", expired=True))
    assert "tested-tree-T artifact has expired" in pt.decide(
        "T", [cand], "success", now=NOW).reason


def test_one_live_record_among_others_is_enough():
    record = (*built("OTHER"), *built("T", expired=True), *built("T", run_id=7))
    cand = pt.Candidate("h", "T", 7, "success", run_created_at=FRESH, artifacts=record)
    assert pt.decide("T", [cand], "success", now=NOW) == pt.Decision(True, ANY, 7)


def test_main_a_run_that_recorded_building_this_tree_proves_it(gh_env):
    api = FakeApi(green_routes())
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "true", "pr_run_id": "7"}
    # asked of run 7, for exactly this commit's tree
    assert artifacts_path(7, TREE) in api.calls


def test_main_a_pr_retargeted_to_main_after_its_run_is_a_full_run(gh_env):
    # Run 7 built HEAD merged into loop/foo, whose commits HEAD lacks: its record
    # is tested-tree-OTHER. The PR was then retargeted to main (no new run),
    # and the squash landed HEAD's own tree, TREE, which no run built.
    for listing in (artifacts(),                        # asked for TREE: none
                    artifacts(artifact(OTHER))):        # a filter the server ignored
        api = FakeApi(green_routes(**{artifacts_path(7): listing}))
        assert pt.main(ARGV, api=api, env=gh_env) == 0
        assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
        assert "ci run 7 left no tested-tree-%s artifact" % TREE[:12] in _summary(gh_env)
        Path(gh_env["GITHUB_OUTPUT"]).unlink()


def test_main_a_twin_pr_whose_run_tested_another_tree_is_a_full_run(gh_env):
    # One head, two PRs: #1 into main and #2 into loop/foo. Run 7 served #1 and
    # built TREE; run 9 served #2, is newer, and built HEAD + loop/foo. The
    # newest run on the head is the one judged, and it never built TREE.
    twin = {"number": 2, "head": {"sha": HEAD}, "base": {"ref": "loop/foo"}}
    api = FakeApi(green_routes(**{
        "commits/%s/pulls" % SHA: [pr(HEAD), twin],
        pr_runs_path(HEAD): runs(run(7, created="2026-10-30T10:00:00Z"),
                                 run(9, created="2026-10-30T11:00:00Z")),
        artifacts_path(9): artifacts(),
    }))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "ci run 9 left no tested-tree-" in _summary(gh_env)


def test_main_a_run_with_no_tested_tree_artifact_is_a_full_run(gh_env):
    # A run from before ci.yml uploaded the record, or a lint job that died
    # before it: the run never said what it built.
    api = FakeApi(green_routes(**{artifacts_path(7): artifacts()}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}


def test_main_an_expired_tested_tree_artifact_is_a_full_run(gh_env):
    api = FakeApi(green_routes(**{artifacts_path(7): artifacts(artifact(expired=True))}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "artifact has expired" in _summary(gh_env)


@pytest.mark.parametrize("exc", [
    urllib.error.HTTPError("u", 404, "Not Found", None, None),
    urllib.error.HTTPError("u", 403, "rate limit exceeded", None, None),
    urllib.error.HTTPError("u", 500, "Server Error", None, None),
    urllib.error.URLError("no route to host"),
    TimeoutError("timed out"),
])
def test_main_an_artifact_listing_that_errors_is_a_full_run(gh_env, exc):
    api = FakeApi(green_routes(**{artifacts_path(7): exc}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "error: %s" % type(exc).__name__ in _summary(gh_env)


@pytest.mark.parametrize("answer", [
    {"message": "Not Found"},            # an error body that arrived as a 200
    None,
    "nope",
    [],
    {},
    {"artifacts": None},
    {"artifacts": "x"},
    {"artifacts": [1, 2]},
])
def test_a_malformed_artifact_listing_is_an_error_not_no_artifact(gh_env, answer):
    api = FakeApi(green_routes(**{artifacts_path(7): answer}))
    with pytest.raises(ValueError, match="artifacts"):
        pt.gather(api, SHA)
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "error: ValueError" in _summary(gh_env)


@pytest.mark.parametrize("entry", [
    {"name": 7, "expired": False},
    {"name": "tested-tree-" + TREE, "expired": "false"},
    {"name": "tested-tree-" + TREE},
    {"name": "tested-tree-" + TREE, "expired": False, "workflow_run": {"id": 8}},
])
def test_an_odd_artifact_entry_is_kept_and_refused_by_decide(entry):
    api = FakeApi(green_routes(**{artifacts_path(7): artifacts(entry)}))
    merge_tree, cands, last = pt.gather(api, SHA)
    assert len(cands[0].artifacts) == 1
    assert pt.decide(merge_tree, cands, last, now=NOW).skip is False


@pytest.mark.parametrize("tree", ["T" * 40, TREE.upper(), TREE[:39], "../x", TREE + "\n"])
def test_a_merge_tree_that_is_not_an_object_id_is_an_error(tree):
    api = FakeApi(green_routes(**{"git/commits/%s" % SHA: commit(tree)}))
    with pytest.raises(ValueError, match="object id"):
        pt.gather(api, SHA)
    assert not any("artifacts" in c for c in api.calls)


# --- the nightly's age, end to end -----------------------------------------

def _routes_with_nightly(created, **extra):
    return green_routes(**{SCHEDULE: runs(run(100, event="schedule", head_sha=SHA,
                                              created=created)), **extra})


@pytest.mark.parametrize("hours,skip", [(1, "true"), (47, "true"), (48, "true"),
                                        (49, "false"), (500, "false")])
def test_main_skips_only_while_the_nightly_is_recent(gh_env, hours, skip):
    api = FakeApi(_routes_with_nightly(hours_before_now(hours)))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env)["skip"] == skip
    if skip == "false":
        assert "nightly stale (%dh)" % hours in _summary(gh_env)


@pytest.mark.parametrize("days,skip", [(12, "true"), (13, "true"), (14, "false")])
def test_main_skips_only_while_the_pr_runs_coverage_report_exists(gh_env, days, skip):
    api = FakeApi(green_routes(**{
        pr_runs_path(HEAD): runs(run(created=hours_before_now(24 * days)))}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": skip, "pr_run_id": "7" if skip == "true" else ""}
    if skip == "false":
        assert "%d days old" % days in _summary(gh_env)


@pytest.mark.parametrize("created", ["garbage", "2026-10-30T10:00:00", None])
def test_main_a_pr_run_without_a_usable_created_at_is_a_full_run(gh_env, created):
    lone = run()
    lone["created_at"] = created
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(lone)}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "created_at unknown" in _summary(gh_env)


def test_main_a_nightly_without_created_at_is_a_full_run(gh_env):
    lone = run(100, event="schedule", head_sha=SHA)
    del lone["created_at"]
    api = FakeApi(green_routes(**{SCHEDULE: runs(lone)}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "nightly age unknown" in _summary(gh_env)


@pytest.mark.parametrize("created", ["", "garbage", "yesterday", "2026-13-45T99:99:99Z",
                                     "2026-10-30T10:00:00", 1761818400, None])
def test_main_a_malformed_created_at_is_a_full_run(gh_env, created):
    lone = run(100, event="schedule", head_sha=SHA)
    lone["created_at"] = created
    api = FakeApi(green_routes(**{SCHEDULE: runs(lone)}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "age unknown" in _summary(gh_env)


def test_main_two_nightlies_one_undated_cannot_be_ordered_so_it_is_a_full_run(gh_env):
    undated = run(100, event="schedule", head_sha=SHA, created="garbage")
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(undated),
        DISPATCH: runs(run(101, event="workflow_dispatch", created=hours_before_now(1)))}))
    assert pt.main(ARGV, api=api, env=gh_env) == 0
    assert _outputs(gh_env)["skip"] == "false"
    assert "error: ValueError" in _summary(gh_env)


def test_main_ages_the_newer_of_the_two_whole_codebase_runs(gh_env):
    fresh_dispatch = FakeApi(green_routes(**{
        SCHEDULE: runs(run(100, event="schedule", created=hours_before_now(60))),
        DISPATCH: runs(run(101, event="workflow_dispatch", created=hours_before_now(5)))}))
    assert pt.main(ARGV, api=fresh_dispatch, env=gh_env) == 0
    assert _outputs(gh_env)["skip"] == "true"


def test_main_two_old_whole_codebase_runs_are_as_stale_as_the_newer_one(tmp_path):
    env = {"GITHUB_OUTPUT": str(tmp_path / "o"), "GITHUB_STEP_SUMMARY": str(tmp_path / "s")}
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(100, event="schedule", created=hours_before_now(60))),
        DISPATCH: runs(run(101, event="workflow_dispatch", created=hours_before_now(70)))}))
    assert pt.main(ARGV, api=api, env=env) == 0
    assert _outputs(env)["skip"] == "false"
    assert "nightly stale (60h)" in _summary(env)


def test_the_clock_defaults_to_the_real_one_on_the_command_line(tmp_path):
    real_now = datetime.now(UTC)

    def verdict(hours_old, name):
        env = {"GITHUB_OUTPUT": str(tmp_path / name)}     # one file per call: it appends
        created = (real_now - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert pt.main(["--sha", SHA], api=FakeApi(_routes_with_nightly(created)), env=env) == 0
        return _outputs(env)["skip"]

    assert verdict(2, "fresh") == "true"
    assert verdict(72, "old") == "false"


@pytest.mark.parametrize("now", ["2026-10-31T09:00:00Z", "2026-10-31T09:00:00+00:00",
                                 "2026-10-31T04:00:00-05:00"])
def test_now_accepts_any_zoned_iso_timestamp(gh_env, now):
    api = FakeApi(_routes_with_nightly(hours_before_now(47)))
    assert pt.main(["--sha", SHA, "--now", now], api=api, env=gh_env) == 0
    assert _outputs(gh_env)["skip"] == "true"


@pytest.mark.parametrize("now", ["", "soon", "2026-10-31T09:00:00", "2026-10-31", "1761900000"])
def test_a_now_that_is_unparseable_or_has_no_zone_is_a_full_run(gh_env, now):
    api = FakeApi({})   # nothing may be requested on a usage error
    assert pt.main(["--sha", SHA, "--now", now], api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert api.calls == []


# --- credentials -----------------------------------------------------------

@pytest.fixture
def no_network(monkeypatch):
    def refuse(*_a, **_k):
        pytest.fail("the network was reached")
    monkeypatch.setattr(pt, "make_api", refuse)


@pytest.mark.parametrize("env_extra,named", [
    ({}, "GITHUB_TOKEN"),
    ({"GITHUB_REPOSITORY": "o/r"}, "GITHUB_TOKEN"),
    ({"GITHUB_TOKEN": ""}, "GITHUB_TOKEN"),
    ({"GITHUB_TOKEN": "   ", "GITHUB_REPOSITORY": "o/r"}, "GITHUB_TOKEN"),
    ({"GITHUB_TOKEN": "t"}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": ""}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "no-slash"}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "a/b/c"}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "a b/c"}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "../x"}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/.."}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "./r"}, "GITHUB_REPOSITORY"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r?x=1"}, "GITHUB_REPOSITORY"),
])
def test_missing_or_malformed_credentials_mean_a_full_run_before_any_request(
        gh_env, no_network, env_extra, named):
    env = {**gh_env, **env_extra}
    assert pt.main(ARGV, env=env) == 0
    assert _outputs(env) == {"skip": "false", "pr_run_id": ""}
    assert named in _summary(env)


def test_the_environment_wires_repo_and_token_into_the_requests(gh_env, monkeypatch):
    seen = []
    table = FakeApi(green_routes())

    def opener_for(path_to_body):
        class Opener:
            def open(self, req, timeout=None):
                seen.append((req.full_url, req.get_header("Authorization"), timeout))
                path = req.full_url.removeprefix("https://api.github.com/repos/o/r/")
                return io.BytesIO(json.dumps(path_to_body(path)).encode())
        return Opener()

    monkeypatch.setattr(pt, "_default_opener", lambda: opener_for(table))
    env = {**gh_env, "GITHUB_TOKEN": "s3cret", "GITHUB_REPOSITORY": "o/r"}
    assert pt.main(ARGV, env=env) == 0
    assert _outputs(env) == {"skip": "true", "pr_run_id": "7"}
    assert seen and all(url.startswith("https://api.github.com/repos/o/r/")
                        for url, _, _ in seen)
    assert {auth for _, auth, _ in seen} == {"Bearer s3cret"}
    assert {t for _, _, t in seen} == {pt.TIMEOUT}


def test_the_token_never_reaches_the_log_or_the_summary(gh_env, capsys, monkeypatch):
    class Opener:
        def open(self, req, timeout=None):
            # A transport error that quotes the request it failed on.
            raise urllib.error.URLError("refused: Authorization: Bearer s3cret-token")

    monkeypatch.setattr(pt, "_default_opener", lambda: Opener())
    env = {**gh_env, "GITHUB_TOKEN": "s3cret-token", "GITHUB_REPOSITORY": "o/r"}
    pt.main(ARGV, env=env)
    captured = capsys.readouterr()
    assert "s3cret-token" not in captured.out + captured.err + _summary(env)
    assert "URLError" in captured.err      # the detail is still logged, scrubbed


# --------------------------------------------------------------------------
# make_api: the real HTTP wrapper, against an injected opener
# --------------------------------------------------------------------------

class RecordingOpener:
    def __init__(self, body=b"{}", error=None):
        self.body, self.error, self.requests, self.timeouts = body, error, [], []

    def open(self, req, timeout=None):
        self.requests.append(req)
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return io.BytesIO(self.body)


def test_make_api_sends_a_bounded_authenticated_request_to_the_repo():
    opener = RecordingOpener(b'{"ok": true}')
    api = pt.make_api("owner/name", "tok", opener=opener)
    assert api("commits/%s/pulls" % SHA) == {"ok": True}
    (req,) = opener.requests
    assert req.full_url == "https://api.github.com/repos/owner/name/commits/%s/pulls" % SHA
    assert req.get_header("Authorization") == "Bearer tok"
    assert req.get_header("Accept") == "application/vnd.github+json"
    assert req.get_header("X-github-api-version")
    assert req.get_header("User-agent")
    assert req.get_method() == "GET"
    assert opener.timeouts == [pt.TIMEOUT]
    assert 0 < pt.TIMEOUT <= 30


def test_make_api_passes_query_strings_through_verbatim():
    opener = RecordingOpener()
    pt.make_api("o/r", "t", opener=opener)(SCHEDULE)
    assert opener.requests[0].full_url.endswith("?branch=main&status=completed"
                                                "&event=schedule&per_page=1")


@pytest.mark.parametrize("body,exc", [
    (b"<html>502 Bad Gateway</html>", json.JSONDecodeError),
    (b"", json.JSONDecodeError),
    (b'{"truncated": ', json.JSONDecodeError),
    (b"\xff\xfe\xfa", ValueError),         # UnicodeDecodeError is a ValueError
])
def test_make_api_lets_a_malformed_body_raise(body, exc):
    api = pt.make_api("o/r", "t", opener=RecordingOpener(body))
    with pytest.raises(exc):
        api("x")


@pytest.mark.parametrize("error", [
    urllib.error.HTTPError("u", 404, "Not Found", None, None),
    urllib.error.HTTPError("u", 403, "Forbidden", None, None),
    urllib.error.HTTPError("u", 429, "Too Many Requests", None, None),
    urllib.error.URLError("unreachable"),
    TimeoutError("timed out"),
])
def test_make_api_lets_transport_errors_raise(error):
    api = pt.make_api("o/r", "t", opener=RecordingOpener(error=error))
    with pytest.raises(type(error)):
        api("x")


def test_the_default_opener_refuses_redirects_so_the_token_stays_on_github():
    opener = pt._default_opener()
    assert any(isinstance(h, pt._NoRedirect) for h in opener.handlers)
    req = urllib.request.Request("https://api.github.com/repos/o/r/x",
                                 headers={"Authorization": "Bearer tok"})
    handler = pt._NoRedirect()
    assert handler.redirect_request(
        req, io.BytesIO(), 301, "Moved", {}, "https://evil.example/steal") is None


# --------------------------------------------------------------------------
# the script as GitHub runs it
# --------------------------------------------------------------------------

def test_run_as_a_script_with_no_credentials_exits_zero_with_skip_false(tmp_path):
    out = tmp_path / "out"
    # A scrubbed environment: on a runner GITHUB_TOKEN is set, and this test
    # must not depend on (or reach the network with) it.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
    env["GITHUB_OUTPUT"] = str(out)
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--sha", SHA],
        env=env, capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    assert out.read_text(encoding="utf-8") == "skip=false\npr_run_id=\n"


# ==========================================================================
# ci.yml wiring: which job runs on which event
# ==========================================================================
#
# The script above only decides. What its `skip=true` may switch off is
# ci.yml's business, and the failure worth pinning there is a quiet one: a job
# that is SKIPPED reports as passing, so a required check that a skipped
# `proven` drags down with it (every pull request, where `proven` never runs)
# would turn green without testing anything. GitHub evaluates a job-level
# `if:` with no status function as `success() && <if>`, and that `success()`
# looks at every ANCESTOR, not only the jobs named in `needs`
# (actions/runner#491) -- so the grandchild of a skipped job is skipped too.
#
# Grepping conditions cannot see that, so these tests evaluate them: a small
# interpreter for the subset of GitHub's expression language the job
# conditions use, and a walk of the job graph that applies the implicit
# `success()` rule. It refuses anything it does not understand -- an unknown
# function, an unknown context name, a `needs.X` the job does not declare --
# so a new construct fails here rather than being approximated.

WORKFLOWS = ROOT / ".github" / "workflows"
CI_YML = WORKFLOWS / "ci.yml"
REFRESH_YML = WORKFLOWS / "mutation-weights-refresh.yml"
PUBLISH_YML = WORKFLOWS / "publish.yml"


@pytest.fixture(scope="module")
def ci():
    # Not a module-level importorskip: the CLI tests above need no PyYAML, and
    # mutmut's sandbox carries no .github directory.
    yaml = pytest.importorskip("yaml")
    if not CI_YML.exists():
        pytest.skip(".github/workflows not reachable (e.g. mutation sandbox)")
    return yaml.safe_load(CI_YML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(ci):
    return ci["jobs"]


_EXPR_TOKEN = re.compile(r"""\s*(?:
      (?P<op>&&|\|\||==|!=|!|\(|\)|,)
    | '(?P<str>(?:[^']|'')*)'
    | (?P<num>\d+(?:\.\d+)?)
    | (?P<name>[A-Za-z_][A-Za-z0-9_.*-]*)
    )""", re.X)

_STATUS_FUNCTIONS = ("always", "cancelled", "success", "failure")
_STATUS_CALL = re.compile(r"\b(%s)\s*\(" % "|".join(_STATUS_FUNCTIONS))


def _truthy(value) -> bool:
    # GitHub's falsy set is false, 0, -0, '' and null -- exactly Python's.
    return bool(value)


def _as_number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool | int | float):
        return float(value)
    text = value.strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return math.nan


def _render(value) -> str:
    """A value as GitHub prints it into a string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format(template, *args) -> str:
    # GitHub's format(): `{N}` is the Nth argument, `{{` and `}}` are literal
    # braces. A placeholder past the last argument is an error there too.
    def sub(m):
        if m.group(0) in ("{{", "}}"):
            return m.group(0)[0]
        return _render(args[int(m.group(1))])
    return re.sub(r"\{\{|\}\}|\{(\d+)\}", sub, _render(template))


def _equal(a, b) -> bool:
    # Strings compare case-insensitively; mixed types are coerced to numbers
    # (so null == '' is true, as it is on GitHub).
    if isinstance(a, str) and isinstance(b, str):
        return a.casefold() == b.casefold()
    if type(a) is type(b):
        return a == b
    return _as_number(a) == _as_number(b)


class _Expression:
    """One expression, evaluated against a lookup and the status functions."""

    def __init__(self, text: str, lookup, status: dict):
        body = text.strip()
        if body.startswith("${{") and body.endswith("}}"):
            body = body[3:-2]
        self.tokens = []
        pos = 0
        while body[pos:].strip():
            m = _EXPR_TOKEN.match(body, pos)
            if not m or m.end() == pos:
                raise SyntaxError("cannot read %r at %d" % (body, pos))
            kind = m.lastgroup
            self.tokens.append((kind, m.group(kind)))
            pos = m.end()
        self.i = 0
        self.lookup = lookup
        self.status = status

    def value(self):
        out = self._or()
        if self.i != len(self.tokens):
            raise SyntaxError("trailing tokens: %r" % (self.tokens[self.i:],))
        return out

    def _peek(self):
        if self.i < len(self.tokens) and self.tokens[self.i][0] == "op":
            return self.tokens[self.i][1]
        return None

    def _take(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _expect(self, op):
        if self._peek() != op:
            raise SyntaxError("expected %r at token %d" % (op, self.i))
        self.i += 1

    # Precedence, loosest first: ||, &&, == / !=, !, primary.
    def _or(self):
        left = self._and()
        while self._peek() == "||":
            self.i += 1
            right = self._and()
            left = left if _truthy(left) else right
        return left

    def _and(self):
        left = self._compare()
        while self._peek() == "&&":
            self.i += 1
            right = self._compare()
            left = right if _truthy(left) else left
        return left

    def _compare(self):
        left = self._unary()
        if self._peek() in ("==", "!="):
            op = self._take()[1]
            same = _equal(left, self._unary())
            return same if op == "==" else not same
        return left

    def _unary(self):
        if self._peek() == "!":
            self.i += 1
            return not _truthy(self._unary())
        return self._primary()

    def _primary(self):
        kind, text = self._take()
        if kind == "op" and text == "(":
            inner = self._or()
            self._expect(")")
            return inner
        if kind == "str":
            return text.replace("''", "'")
        if kind == "num":
            return float(text)
        if kind != "name":
            raise SyntaxError("unexpected %r" % text)
        if self._peek() == "(":
            self.i += 1
            args = []
            if self._peek() != ")":
                args.append(self._or())
                while self._peek() == ",":
                    self.i += 1
                    args.append(self._or())
            self._expect(")")
            if text in _STATUS_FUNCTIONS and not args:
                return self.status[text]
            if text == "format" and args:
                return _format(*args)
            raise ValueError("this interpreter does not implement %s()" % text)
        if text in ("true", "false"):
            return text == "true"
        if text == "null":
            return None
        return self.lookup(text)


def evaluate(text: str, lookup, status: dict | None = None):
    return _Expression(text, lookup, status or {}).value()


def interpolate(text: str, lookup) -> str:
    """A string with `${{ }}` holes, as GitHub renders it."""
    def render(m):
        return _render(evaluate(m.group(1), lookup))
    return re.sub(r"\$\{\{(.*?)\}\}", render, text)


def _needs(job: dict) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def _ancestors(jobs: dict, name: str) -> set[str]:
    seen: set[str] = set()
    todo = list(_needs(jobs[name]))
    while todo:
        dep = todo.pop()
        if dep not in seen:
            seen.add(dep)
            todo.extend(_needs(jobs[dep]))
    return seen


def _topological(jobs: dict) -> list[str]:
    order: list[str] = []
    while len(order) < len(jobs):
        ready = [n for n in jobs if n not in order
                 and all(d in order for d in _needs(jobs[n]))]
        assert ready, "the job graph has a cycle or an unknown need"
        order.extend(sorted(ready))
    return order


#: The seven situations the plan cares about, in the column order of the
#: table below. `proven` is (result, skip output, pr_run_id output) for the
#: pushes; on every other event the job's own `if:` decides it never runs.
SCENARIOS = {
    "pull_request": {"event": "pull_request", "ref": "refs/pull/7/merge"},
    "merge_group": {"event": "merge_group",
                    "ref": "refs/heads/gh-readonly-queue/main/pr-7-abc"},
    "push, proven skip=true": {"event": "push", "ref": "refs/heads/main",
                               "proven": ("success", "true", "41")},
    "push, proven skip=false": {"event": "push", "ref": "refs/heads/main",
                                "proven": ("success", "false", "")},
    "push, proven job failed": {"event": "push", "ref": "refs/heads/main",
                                "proven": ("failure", "", "")},
    "schedule": {"event": "schedule", "ref": "refs/heads/main"},
    "workflow_dispatch": {"event": "workflow_dispatch", "ref": "refs/heads/main"},
}

#: What each job's outputs are when it runs. The planner's matrix is a model
#: of its `write the plan` step -- empty exactly when `proven` said skip -- and
#: that step's bash is run against the same inputs in test_mutation_plan.py.
ONE_SHARD = '[{"set":"full","index":0}]'
ONE_DIFF_SHARD = '[{"set":"diff","index":0}]'


def _outcome(name: str, scenario: dict) -> tuple[str, dict]:
    if name == "proven":
        result, skip, run_id = scenario["proven"]
        if result != "success":
            return result, {}       # a failed job's outputs are empty
        return result, {"skip": skip, "pr_run_id": run_id}
    if name == "mutation-plan":
        proven = scenario.get("proven", ("", "", ""))
        if proven[1] == "true":
            return "success", {"matrix": "[]", "gate_set": ""}
        # A PR or queue entry binds on its diff set; everything else is full.
        if scenario["event"] in ("pull_request", "merge_group"):
            return "success", {"matrix": ONE_DIFF_SHARD, "gate_set": "diff"}
        return "success", {"matrix": ONE_SHARD, "gate_set": "full"}
    return "success", {}


def job_runs(jobs: dict, name: str, results: dict, outputs: dict,
             scenario: dict) -> bool:
    """Does GitHub start this job, given what its ancestors did?"""
    job = jobs[name]
    direct = _needs(job)

    def lookup(ident: str):
        if ident == "github.event_name":
            return scenario["event"]
        if ident == "github.ref":
            return scenario["ref"]
        parts = ident.split(".")
        if parts[0] == "needs":
            assert len(parts) >= 3 and parts[1] in direct, (
                "%s reads %s but does not `needs:` %s" % (name, ident, parts[1]))
            if parts[2:] == ["result"]:
                return results[parts[1]]
            if parts[2] == "outputs" and len(parts) == 4:
                return outputs[parts[1]].get(parts[3], "")
        raise KeyError("%s: no context value %r in this model" % (name, ident))

    upstream = [results[a] for a in _ancestors(jobs, name)]
    status = {"always": True, "cancelled": False,
              "success": all(r == "success" for r in upstream),
              "failure": any(r == "failure" for r in upstream)}
    cond = job.get("if")
    if cond is None:
        return status["success"]
    text = cond if isinstance(cond, str) else str(cond).lower()
    value = _truthy(evaluate(text, lookup, status))
    if _STATUS_CALL.search(text):
        return value
    return status["success"] and value


def simulate(jobs: dict, scenario: dict) -> dict[str, str]:
    """``{job: result}`` for one event, walking the graph in order."""
    results: dict[str, str] = {}
    outputs: dict[str, dict] = {}
    for name in _topological(jobs):
        if job_runs(jobs, name, results, outputs, scenario):
            results[name], outputs[name] = _outcome(name, scenario)
        else:
            results[name], outputs[name] = "skipped", {}
    return results


#: Who runs where. One row per ci.yml job, one column per SCENARIOS entry.
#: A new job fails test_every_job_has_a_row until someone decides its row.
R, S = "runs", "skipped"
EXPECTED = {
    #                  PR  queue  skip=T  skip=F  failed  sched  dispatch
    "proven":         (S,  S,     R,      R,      R,      S,     S),
    "lint":           (R,  R,     R,      R,      R,      S,     S),
    "evals":          (R,  R,     R,      R,      R,      S,     S),
    "tests":          (R,  R,     S,      R,      R,      S,     S),
    "coverage-badge": (S,  S,     R,      R,      R,      S,     S),
    "mutation-plan":  (R,  R,     R,      R,      R,      R,     R),
    "mutation-shard": (R,  R,     S,      R,      R,      R,     R),
    "mutation":       (R,  R,     R,      R,      R,      R,     R),
    "install-smoke":  (R,  R,     R,      R,      R,      S,     S),
    "patch-coverage": (R,  S,     S,      S,      S,      S,     S),
    "canary":         (R,  S,     S,      S,      S,      S,     S),
    "bdd":            (R,  R,     R,      R,      R,      S,     S),
    "onnx-inference": (R,  R,     R,      R,      R,      S,     S),
}

#: The only jobs a nightly or a dispatch may start: the whole-codebase run.
WHOLE_CODEBASE_JOBS = {"mutation-plan", "mutation-shard", "mutation"}


def run_table(jobs: dict) -> dict[str, tuple[str, ...]]:
    """The simulated EXPECTED: ``{job: (runs|skipped per scenario)}``."""
    sims = [simulate(jobs, sc) for sc in SCENARIOS.values()]
    return {name: tuple(R if sim[name] != "skipped" else S for sim in sims)
            for name in jobs}


def render_table(jobs: dict) -> str:
    """The table as Markdown -- what the task report carries, never hand-typed."""
    head = "| job | " + " | ".join(SCENARIOS) + " |"
    rule = "|---" * (len(SCENARIOS) + 1) + "|"
    rows = ["| `%s` | %s |" % (name, " | ".join(cells))
            for name, cells in run_table(jobs).items()]
    return "\n".join([head, rule, *rows])


def test_every_job_has_a_row(jobs):
    assert set(jobs) == set(EXPECTED)


def test_each_job_runs_exactly_where_the_table_says(jobs):
    table = run_table(jobs)
    wrong = {name: (table[name], EXPECTED[name]) for name in jobs
             if table[name] != EXPECTED[name]}
    assert not wrong, "\n" + "\n".join(
        "%s: simulated %s, expected %s" % (n, got, want)
        for n, (got, want) in wrong.items())


def test_the_table_renders_every_scenario(jobs):
    text = render_table(jobs)
    for column in SCENARIOS:
        assert column in text
    assert text.count("\n") == len(jobs) + 1


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
def test_a_whole_codebase_run_starts_only_the_mutation_jobs(jobs, event):
    ran = {n for n, r in simulate(jobs, SCENARIOS[event]).items() if r != "skipped"}
    assert ran == WHOLE_CODEBASE_JOBS, sorted(ran ^ WHOLE_CODEBASE_JOBS)


def test_a_proven_push_still_runs_every_non_test_check(jobs):
    # The spec keeps lint (with zizmor), the eval harness, install-smoke, bdd
    # and onnx-inference on a proven push; only the suite, the shards and the
    # coverage collection are what the PR run already did.
    sim = simulate(jobs, SCENARIOS["push, proven skip=true"])
    skipped = {n for n, r in sim.items() if r == "skipped"}
    assert skipped == {"tests", "mutation-shard", "patch-coverage", "canary"}


def test_every_job_downstream_of_proven_names_a_status_function(jobs):
    # The implicit `success()` reaches every ancestor, so a job anywhere below
    # `proven` without one is skipped on every pull request.
    below = [n for n in jobs if "proven" in _ancestors(jobs, n)]
    assert {"tests", "mutation-plan", "mutation-shard", "coverage-badge"} <= set(below)
    for name in below:
        cond = str(jobs[name].get("if", ""))
        assert _STATUS_CALL.search(cond), (
            "%s is downstream of `proven`, which is skipped on every pull "
            "request; with no status function in its `if:` it is skipped too" % name)


def test_a_job_that_needs_proven_is_not_cancelled_rather_than_succeeded(jobs):
    # `!cancelled()`: it runs when `proven` was skipped (PRs), when it failed
    # (empty output, so a full run), and never after a cancel.
    for name, job in jobs.items():
        if "proven" not in _needs(job):
            continue
        cond = job["if"]
        if name == "coverage-badge":
            assert cond.startswith("${{ always() && "), cond
            continue
        assert cond.startswith("${{ !cancelled()"), (name, cond)
        assert cond.endswith("}}"), (name, cond)


TESTS_IF = ("${{ !cancelled() && github.event_name != 'schedule'"
            " && github.event_name != 'workflow_dispatch'"
            " && needs.proven.outputs.skip != 'true' }}")


def test_the_suite_is_skipped_only_on_an_explicit_true(jobs):
    assert jobs["tests"]["if"] == TESTS_IF
    assert _needs(jobs["tests"]) == ["proven"]


@pytest.mark.parametrize("event, skip, proven_result, runs", [
    ("pull_request", "", "skipped", True),       # proven never ran: test
    ("merge_group", "", "skipped", True),
    ("push", "true", "success", False),          # the one way to skip
    ("push", "false", "success", True),
    ("push", "", "failure", True),               # proven failed: empty output, test
    ("push", "TRUE", "success", False),          # GitHub's == folds case
    ("push", "yes", "success", True),            # only `true` skips
    ("schedule", "", "skipped", False),
    ("workflow_dispatch", "", "skipped", False),
])
def test_the_suite_condition_case_by_case(jobs, event, skip, proven_result, runs):
    scenario = {"event": event, "ref": "refs/heads/main"}
    got = job_runs(jobs, "tests", {"proven": proven_result},
                   {"proven": {"skip": skip}}, scenario)
    assert got is runs


def test_the_shards_check_the_planner_result_now_that_they_say_not_cancelled(jobs):
    # `!cancelled()` drops the implicit success(), so the planner's own result
    # has to be stated -- else a failed planner's empty matrix would start a
    # shard from `fromJSON('')`.
    shard = jobs["mutation-shard"]
    assert shard["if"] == ("${{ !cancelled() && needs.mutation-plan.result == 'success'"
                           " && needs.mutation-plan.outputs.matrix != '[]' }}")
    for plan_result, matrix, runs in [("success", ONE_SHARD, True),
                                      ("success", "[]", False),
                                      ("failure", "", False),
                                      ("cancelled", "", False)]:
        got = job_runs(jobs, "mutation-shard", {"mutation-plan": plan_result,
                                                "proven": "skipped"},
                       {"mutation-plan": {"matrix": matrix}},
                       SCENARIOS["pull_request"])
        assert got is runs, (plan_result, matrix)


def test_the_interpreter_applies_the_implicit_success_to_grandparents():
    # Pins the rule the whole section rests on: a job whose `if:` has no
    # status function is skipped when ANY ancestor was skipped, even though
    # its direct need succeeded. Without it, the simulation would wave
    # through the regression it exists to catch.
    graph = {"a": {"if": "github.event_name == 'push'"},
             "b": {"needs": "a", "if": "${{ !cancelled() }}"},
             "c": {"needs": "b", "if": "github.event_name == 'pull_request'"},
             "d": {"needs": "b", "if": "${{ !cancelled() && github.event_name == 'pull_request' }}"}}
    sim = simulate(graph, {"event": "pull_request", "ref": "refs/pull/1/merge"})
    assert sim == {"a": "skipped", "b": "success", "c": "skipped", "d": "success"}


@pytest.mark.parametrize("text, expected", [
    ("'a' == 'A'", True),
    ("null == ''", True),
    ("!('x' != 'x')", True),
    ("'' || 'fallback'", "fallback"),
    ("'x' && ''", ""),
    ("!cancelled() && always()", True),
    ("'it''s' == 'IT''S'", True),
])
def test_the_interpreter_follows_githubs_rules(text, expected):
    status = {"always": True, "cancelled": False}
    assert evaluate(text, lambda name: pytest.fail(name), status) == expected


@pytest.mark.parametrize("text, expected", [
    ("format('a-{0}-{1}', 'x', 7)", "a-x-7"),
    ("format('{{{0}}}', 'x')", "{x}"),          # doubled braces are literal
    ("format('{0}{0}', null)", ""),             # null renders empty
    ("format('{0}', true)", "true"),
])
def test_the_interpreter_formats_as_github_does(text, expected):
    assert evaluate(text, lambda name: pytest.fail(name), {}) == expected


def test_a_format_placeholder_without_an_argument_is_an_error():
    with pytest.raises(IndexError):
        evaluate("format('{1}', 'only-one')", lambda name: pytest.fail(name), {})


@pytest.mark.parametrize("text", ["contains(github.ref, 'main')", "github.ref == ",
                                  "fromJSON('[]')"])
def test_the_interpreter_refuses_what_it_does_not_implement(text):
    with pytest.raises((SyntaxError, ValueError, IndexError)):
        evaluate(text, lambda name: "refs/heads/main", {})


# --------------------------------------------------------------------------
# triggers and concurrency
# --------------------------------------------------------------------------

def _on(ci) -> dict:
    # PyYAML reads the bare key `on` as the boolean True (YAML 1.1).
    return ci.get("on", ci.get(True))


def test_ci_runs_nightly_and_on_dispatch(ci):
    on = _on(ci)
    assert on["schedule"] == [{"cron": "30 9 * * *"}]
    assert "workflow_dispatch" in on
    # The triggers that already existed are unchanged.
    assert on["push"] == {"branches": ["main"]}
    assert "pull_request" in on and "merge_group" in on


def _group_for(ci, event, sha, pr=None):
    block = ci["concurrency"]
    ctx = {"github.event_name": event, "github.sha": sha,
           "github.event.pull_request.number": pr}
    return (interpolate(block["group"], ctx.__getitem__),
            _truthy(evaluate(block["cancel-in-progress"], ctx.__getitem__)))


def test_a_nightly_never_shares_a_group_with_the_push_of_the_same_commit(ci):
    # Same group + cancel-in-progress: false means the later run WAITS, and a
    # third arrival cancels the pending one: a release run stuck behind a
    # two-hour nightly, or cancelled by a dispatch.
    groups = {event: _group_for(ci, event, SHA)[0]
              for event in ("push", "schedule", "workflow_dispatch", "merge_group")}
    assert len(set(groups.values())) == len(groups), groups


def test_two_main_commits_never_share_a_group(ci):
    assert _group_for(ci, "push", SHA)[0] != _group_for(ci, "push", HEAD)[0]
    assert _group_for(ci, "schedule", SHA)[0] != _group_for(ci, "schedule", HEAD)[0]


def test_a_pull_requests_runs_still_share_one_group_and_cancel(ci):
    first = _group_for(ci, "pull_request", SHA, pr=7)
    second = _group_for(ci, "pull_request", HEAD, pr=7)
    assert first == second and first[1] is True
    assert _group_for(ci, "pull_request", SHA, pr=8)[0] != first[0]


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch", "merge_group"])
def test_nothing_but_a_pull_request_is_cancelled(ci, event):
    assert _group_for(ci, event, SHA)[1] is False


# --------------------------------------------------------------------------
# the `proven` job
# --------------------------------------------------------------------------

def _all_run_text(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job.get("steps", []))


def test_proven_runs_only_on_push_with_read_only_scopes(jobs):
    job = jobs["proven"]
    assert job["if"] == "github.event_name == 'push'"
    assert job["permissions"] == {"contents": "read", "actions": "read",
                                  "pull-requests": "read"}
    assert set(job["outputs"]) == {"skip", "pr_run_id"}
    assert "timeout-minutes" in job


def test_proven_runs_the_script_with_the_token_through_env(jobs):
    job = jobs["proven"]
    step = next(s for s in job["steps"] if "ci_proven_tree.py" in s.get("run", ""))
    assert 'scripts/ci_proven_tree.py --sha "$GITHUB_SHA"' in step["run"]
    # --now is for tests; the workflow is judged against the real clock.
    assert "--now" not in step["run"]
    assert step["env"]["GITHUB_TOKEN"] == "${{ github.token }}"  # noqa: S105  (an expression, not a secret)
    outputs = job["outputs"]
    assert outputs["skip"] == "${{ steps.%s.outputs.skip }}" % step["id"]
    assert outputs["pr_run_id"] == "${{ steps.%s.outputs.pr_run_id }}" % step["id"]
    # The script always exits 0; a step-level escape hatch would hide a crash.
    assert "continue-on-error" not in step


def test_no_new_job_expands_an_expression_inside_run(jobs):
    for name in ("proven", "coverage-badge", "tests"):
        for step in jobs[name]["steps"]:
            run = step.get("run", "")
            if name == "tests" and step.get("name", "").startswith("job summary"):
                continue   # predates this change; matrix values only
            assert "${{" not in run, (name, step.get("name"))


# --------------------------------------------------------------------------
# coverage-badge
# --------------------------------------------------------------------------

def test_the_badge_left_the_test_matrix(jobs):
    tests = jobs["tests"]
    assert tests["permissions"] == {"contents": "read"}
    assert "badges" not in _all_run_text(tests)


def test_only_the_badge_job_may_write_contents(jobs):
    writers = sorted(n for n, j in jobs.items()
                     if (j.get("permissions") or {}).get("contents") == "write")
    assert writers == ["coverage-badge"]
    assert jobs["coverage-badge"]["permissions"] == {"contents": "write",
                                                     "actions": "read"}


def test_the_badge_runs_on_main_pushes_whatever_upstream_did(jobs):
    job = jobs["coverage-badge"]
    assert set(_needs(job)) == {"proven", "tests"}
    assert job["if"] == ("${{ always() && github.event_name == 'push'"
                         " && github.ref == 'refs/heads/main' }}")
    assert "timeout-minutes" in job


def test_a_failed_badge_is_red_but_never_holds_a_release(jobs):
    # The badge is cosmetic: a red badge job shows on the run, and the run
    # (which publish.yml releases on) still concludes on the real gates. Its
    # own checks are steps with no continue-on-error, so they still fail it.
    job = jobs["coverage-badge"]
    assert job["continue-on-error"] is True
    for step in job["steps"]:
        assert "continue-on-error" not in step, step.get("name")


def _badge_step(jobs, needle):
    found = [s for s in jobs["coverage-badge"]["steps"] if needle in s.get("run", "")]
    assert len(found) == 1, needle
    return found[0]


def _badge_downloads(jobs):
    return [s for s in jobs["coverage-badge"]["steps"]
            if s.get("uses", "").startswith("actions/download-artifact")]


def test_the_badge_judges_its_source_before_downloading(jobs):
    steps = jobs["coverage-badge"]["steps"]
    check = _badge_step(jobs, "$TESTS")
    assert check["env"]["TESTS"] == "${{ needs.tests.result }}"
    assert check["env"]["SKIP"] == "${{ needs.proven.outputs.skip }}"
    assert check["env"]["PR_RUN_ID"] == "${{ needs.proven.outputs.pr_run_id }}"
    # Always runs, never tolerated: it is what keeps an always() job honest.
    assert "if" not in check and not check.get("continue-on-error")
    first_download = min(steps.index(s) for s in _badge_downloads(jobs))
    assert steps.index(check) < first_download


DOWNLOAD_ARTIFACT_V8_0_2 = ("actions/download-artifact@"
                            "9000827ccba6bdab643e8b6fd33ac0654aef8333")


def test_the_badge_downloads_from_this_run_or_the_proving_one(jobs):
    downloads = {s["if"]: s for s in _badge_downloads(jobs)}
    check_id = _badge_step(jobs, "$TESTS")["id"]
    this = downloads["steps.%s.outputs.from == 'this'" % check_id]
    pr = downloads["steps.%s.outputs.from == 'pr'" % check_id]
    assert this["with"] == {"name": "coverage-report"}
    assert pr["with"] == {"name": "coverage-report",
                          "run-id": "${{ needs.proven.outputs.pr_run_id }}",
                          "github-token": "${{ github.token }}"}
    for step in (this, pr):
        assert not step.get("continue-on-error"), "a missing artifact must fail the job"
        # The pin mutation-weights-refresh.yml already drives with run-id and
        # github-token (v8.0.2), so the cross-run inputs are known to exist.
        assert step["uses"] == DOWNLOAD_ARTIFACT_V8_0_2


needs_bash = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash"),
    reason="runs a workflow step's bash")


def _run_step(step: dict, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    # `bash -e {0}`: what an ubuntu runner runs a `run:` with when the job
    # sets no `shell:`.
    script = cwd / "step.sh"
    script.write_text(step["run"], encoding="utf-8")
    full = {"PATH": os.environ["PATH"], "HOME": str(cwd)}
    full.update(env)
    return subprocess.run(["bash", "-e", str(script)], cwd=cwd, env=full,
                          capture_output=True, text=True, check=False)


@needs_bash
@pytest.mark.parametrize("tests, skip, run_id, source", [
    ("success", "false", "", "this"),        # the suite ran here and passed
    ("success", "", "", "this"),             # proven failed, so the suite ran
    ("skipped", "true", "41", "pr"),         # proven: the PR run measured it
    ("failure", "false", "", None),          # red suite: no badge, red job
    ("cancelled", "false", "", None),
    ("skipped", "", "", None),               # neither ran: nothing to publish
    ("skipped", "false", "", None),
    ("skipped", "true", "", None),           # skip without a run to read from
    ("success", "true", "41", None),         # contradiction: refuse, do not guess
])
def test_the_badge_source_check_case_by_case(jobs, tmp_path, tests, skip, run_id, source):
    step = _badge_step(jobs, "$TESTS")
    out = tmp_path / "out"
    out.write_text("", encoding="utf-8")
    proc = _run_step(step, tmp_path, {"TESTS": tests, "SKIP": skip,
                                      "PR_RUN_ID": run_id, "GITHUB_OUTPUT": str(out)})
    if source is None:
        assert proc.returncode != 0, proc.stdout
        assert "::error::" in proc.stdout
        assert "from=" not in out.read_text(encoding="utf-8")
    else:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert out.read_text(encoding="utf-8") == "from=%s\n" % source


@needs_bash
def test_the_badge_publish_step_pushes_the_same_badge_as_before(jobs, tmp_path):
    step = _badge_step(jobs, "badges:badges")
    assert step["env"] == {"GH_TOKEN": "${{ github.token }}",
                           "REPO": "${{ github.repository }}"}
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 93.62}}), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "git.log"
    git = bin_dir / "git"
    git.write_text('#!/bin/bash\necho "git $*" >> "%s"\n' % calls, encoding="utf-8")
    git.chmod(0o755)
    runner_temp = tmp_path / "rt"
    runner_temp.mkdir()
    proc = _run_step(step, tmp_path, {
        "PATH": "%s%s%s" % (bin_dir, os.pathsep, os.environ["PATH"]),
        "GH_TOKEN": "tok", "REPO": "o/r", "RUNNER_TEMP": str(runner_temp)})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    badge = json.loads((runner_temp / "badges" / "coverage.json").read_text(encoding="utf-8"))
    assert badge == {"schemaVersion": 1, "label": "coverage", "message": "94%",
                     "color": "brightgreen"}
    log = calls.read_text(encoding="utf-8").splitlines()
    assert "git init -q -b badges" in log
    assert "git commit -qm coverage 94%" in log
    assert log[-1] == "git push -qf https://x-access-token:tok@github.com/o/r badges:badges"


# --------------------------------------------------------------------------
# the record each pull_request run leaves of the tree it built
# --------------------------------------------------------------------------
# `proven` only skips on a PR run that carries `tested-tree-<pushed tree>`, so
# the upload is half of the proof: pinned here, and its bash run for real.

UPLOAD_ARTIFACT_V7_0_2 = ("actions/upload-artifact@"
                          "cf430e030ddbb5b0abf93d22962f4752f3646cd9")


def _tested_tree_upload(jobs):
    """``(job name, its steps, the upload step, the step that names the tree)``."""
    found = [(name, job["steps"], step) for name, job in jobs.items()
             for step in job.get("steps", [])
             if step.get("uses", "").startswith("actions/upload-artifact")
             and str((step.get("with") or {}).get("name", "")).startswith(
                 pt.TESTED_TREE_ARTIFACT)]
    assert len(found) == 1, [f[0] for f in found]
    name, steps, upload = found[0]
    m = re.fullmatch(r"%s\$\{\{ steps\.([A-Za-z0-9_-]+)\.outputs\.tree \}\}"
                     % re.escape(pt.TESTED_TREE_ARTIFACT), upload["with"]["name"])
    assert m, upload["with"]["name"]
    (tree_step,) = [s for s in steps if s.get("id") == m.group(1)]
    return name, steps, upload, tree_step


def _event_lookup(event):
    def lookup(ident):
        if ident == "github.event_name":
            return event
        raise KeyError(ident)
    return lookup


def test_every_pull_request_run_uploads_the_tree_it_built(jobs):
    name, steps, upload, tree_step = _tested_tree_upload(jobs)
    job = jobs[name]
    # A job that runs on every pull request and counts toward the run's verdict.
    assert simulate(jobs, SCENARIOS["pull_request"])[name] == "success"
    assert not job.get("continue-on-error")
    assert "strategy" not in job, "an artifact name is unique per run: no matrix"
    # The record, and the step that computes it, on a pull_request run only.
    for step in (tree_step, upload):
        assert not step.get("continue-on-error")
        for event in ("pull_request", "push", "merge_group", "schedule",
                      "workflow_dispatch"):
            assert _truthy(evaluate(step["if"], _event_lookup(event))) is (
                event == "pull_request"), (step.get("name"), event)
    # Pinned to the commit every other upload in ci.yml uses.
    assert upload["uses"] == UPLOAD_ARTIFACT_V7_0_2
    others = {s["uses"] for j in jobs.values() for s in j.get("steps", [])
              if s.get("uses", "").startswith("actions/upload-artifact")}
    assert others == {UPLOAD_ARTIFACT_V7_0_2}
    spec = upload["with"]
    assert spec["if-no-files-found"] == "error"
    # Kept at least as long as a PR run may prove a tree for, plus the day of
    # margin the coverage-report already has, so it never expires first.
    assert int(spec["retention-days"]) >= pt.MAX_PR_RUN_AGE.days + 1
    # The name comes through a step output; nothing is expanded inside `run:`.
    assert "${{" not in tree_step["run"]
    assert steps.index(tree_step) < steps.index(upload)
    # ... computed after the job's one checkout, of github.sha: no `ref:` and
    # no `repository:`, so HEAD is the merge commit the whole run builds.
    checkouts = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
    assert len(checkouts) == 1
    assert steps.index(checkouts[0]) < steps.index(tree_step)
    assert not {"ref", "repository"} & set(checkouts[0].get("with") or {})


@needs_bash
def test_the_recorded_tree_is_the_checked_out_merge_commits_tree(jobs, tmp_path):
    _, _, upload, tree_step = _tested_tree_upload(jobs)
    repo = tmp_path / "repo"
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
           "-c", "commit.gpgsign=false"]
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

    def sh(*args):
        return subprocess.run([*git, *args], check=True, capture_output=True,
                              text=True, env=env).stdout.strip()

    # refs/pull/N/merge: the PR head merged into its base, a tree neither has.
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, env=env)
    (repo / "a").write_text("1\n", encoding="utf-8")
    sh("add", "-A")
    sh("commit", "-qm", "base")
    sh("checkout", "-qb", "pr")
    (repo / "b").write_text("2\n", encoding="utf-8")
    sh("add", "-A")
    sh("commit", "-qm", "head")
    head_tree = sh("rev-parse", "HEAD^{tree}")
    sh("checkout", "-q", "main")
    (repo / "c").write_text("3\n", encoding="utf-8")
    sh("add", "-A")
    sh("commit", "-qm", "base moved")
    sh("merge", "-q", "--no-ff", "-m", "merge", "pr")
    merge_tree = sh("rev-parse", "HEAD^{tree}")
    assert merge_tree != head_tree

    temp = tmp_path / "runner-temp"
    temp.mkdir()
    out = tmp_path / "github-output"
    out.write_text("", encoding="utf-8")
    proc = _run_step(tree_step, repo, {"RUNNER_TEMP": str(temp),
                                       "GITHUB_OUTPUT": str(out)})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.read_text(encoding="utf-8") == "tree=%s\n" % merge_tree
    # ... and the file the upload sends holds the same tree.
    path = interpolate(upload["with"]["path"],
                       lambda ident: str(temp) if ident == "runner.temp" else None)
    assert Path(path).read_text(encoding="utf-8") == merge_tree + "\n"
    # The name is exactly the one ci_proven_tree.py asks for.
    name = interpolate(upload["with"]["name"],
                       lambda ident: merge_tree if ident.endswith(".outputs.tree") else None)
    assert name == pt.TESTED_TREE_ARTIFACT + merge_tree


# --------------------------------------------------------------------------
# mutation-weights-refresh.yml: weights come only from full whole-codebase runs
# --------------------------------------------------------------------------

def _refresh_if():
    yaml = pytest.importorskip("yaml")
    if not REFRESH_YML.exists():
        pytest.skip(".github/workflows not reachable (e.g. mutation sandbox)")
    wf = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    return wf["jobs"]["rebalance"]["if"]


def _refresh_accepts(name="workflow_run", *, event="push", conclusion="success",
                     branch="main", repo="o/boost"):
    run = {"conclusion": conclusion, "event": event, "head_branch": branch,
           "head_repository.full_name": repo}

    def lookup(ident):
        if ident == "github.event_name":
            return name
        if ident == "github.repository":
            return "o/boost"
        prefix = "github.event.workflow_run."
        if ident.startswith(prefix):
            return run.get(ident[len(prefix):]) if name == "workflow_run" else None
        raise KeyError(ident)
    return _truthy(evaluate(_refresh_if(), lookup, {"success": True}))


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_the_refresh_follows_every_full_run_on_main(event):
    # A proven push uploads no weights (its plan is `none`), so without the
    # nightly and the dispatch the refresh would never see a measurement.
    assert _refresh_accepts(event=event)


@pytest.mark.parametrize("kwargs", [
    {"event": "pull_request"},             # a fork PR from a branch named main
    {"event": "merge_group"},
    {"repo": "fork/boost"},
    {"conclusion": "failure"},
    {"conclusion": "cancelled"},
    {"event": "workflow_dispatch", "branch": "feature"},  # dispatched elsewhere
    {"event": "schedule", "branch": "release"},
])
def test_the_refresh_refuses_anything_else(kwargs):
    assert not _refresh_accepts(**kwargs)


def test_the_refresh_can_still_be_run_by_hand():
    assert _refresh_accepts("workflow_dispatch")


# --- the manual path: which run's weights --------------------------------
#
# On a dispatch of the refresh itself there is no triggering run, so the step
# looks one up. "The newest green ci on main" now usually names a proven push,
# which uploads no weights, so it asks the artifacts API run by run for one
# that still holds a live `mutation-weights` artifact. The stub `gh` applies
# the step's own `-q` jq programs to fixture JSON, so the filters are real.

def _refresh_steps():
    yaml = pytest.importorskip("yaml")
    if not REFRESH_YML.exists():
        pytest.skip(".github/workflows not reachable (e.g. mutation sandbox)")
    wf = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    return wf["jobs"]["rebalance"]["steps"]


def _refresh_step(step_id):
    found = [s for s in _refresh_steps() if s.get("id") == step_id]
    assert len(found) == 1, step_id
    return found[0]


needs_jq = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash") or not shutil.which("jq"),
    reason="runs a workflow step's bash, which needs bash and jq")

_GH_STUB = r"""#!/bin/bash
echo "gh $*" >> "$CALLS"
q=""; prev=""
for a in "$@"; do [ "$prev" = "-q" ] && q="$a"; prev="$a"; done
if [ "$1 $2" = "run list" ]; then
  jq -r "$q" "$FIXTURES/runs.json"; exit $?
fi
if [ "$1" = api ]; then
  id="$(echo "$2" | sed -E 's#.*/runs/([0-9]+)/artifacts.*#\1#')"
  f="$FIXTURES/artifacts-$id.json"
  [ -f "$f" ] || { echo "gh: Not Found (HTTP 404)" >&2; exit 1; }
  jq -r "$q" "$f"; exit $?
fi
exit 99
"""


def _artifacts(*expired):
    return {"total_count": len(expired),
            "artifacts": [{"name": "mutation-weights", "expired": e} for e in expired]}


@pytest.fixture
def pick_run(tmp_path):
    step = _refresh_step("source")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(_GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    calls = tmp_path / "gh.log"

    def run(listed, artifacts, triggering="", ok=True):
        (fixtures / "runs.json").write_text(json.dumps(listed), encoding="utf-8")
        for run_id, body in artifacts.items():
            (fixtures / ("artifacts-%d.json" % run_id)).write_text(
                json.dumps(body), encoding="utf-8")
        out = tmp_path / "out"
        out.write_text("", encoding="utf-8")
        calls.write_text("", encoding="utf-8")
        proc = _run_step(step, tmp_path, {
            "PATH": "%s%s%s" % (bin_dir, os.pathsep, os.environ["PATH"]),
            "CALLS": str(calls), "FIXTURES": str(fixtures), "GITHUB_OUTPUT": str(out),
            "GH_TOKEN": "t", "REPO": "o/boost", "TRIGGERING": triggering})
        if not ok:
            return proc, out.read_text(encoding="utf-8")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        got = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
        return got["run-id"], calls.read_text(encoding="utf-8").splitlines(), proc.stdout
    return run


@needs_jq
def test_the_manual_path_skips_runs_that_uploaded_no_weights(pick_run):
    listed = [{"databaseId": 30, "event": "push"},          # proven: no weights
              {"databaseId": 20, "event": "push"},          # docs-only: none either
              {"databaseId": 10, "event": "schedule"}]      # the nightly: weights
    run_id, calls, _ = pick_run(listed, {30: _artifacts(), 20: _artifacts(),
                                         10: _artifacts(False)})
    assert run_id == "10"
    assert [c for c in calls if c.startswith("gh api ")] == [
        "gh api repos/o/boost/actions/runs/%d/artifacts?name=mutation-weights -q %s"
        % (n, "[.artifacts[] | select(.expired | not)] | length") for n in (30, 20, 10)]


@needs_jq
def test_the_manual_path_takes_whichever_event_actually_has_them(pick_run):
    # No event is assumed to carry weights: an unproven push does too.
    listed = [{"databaseId": 31, "event": "push"}, {"databaseId": 11, "event": "schedule"}]
    run_id, _, _ = pick_run(listed, {31: _artifacts(False), 11: _artifacts(False)})
    assert run_id == "31"


@needs_jq
def test_an_expired_artifact_is_not_a_measurement(pick_run):
    listed = [{"databaseId": 32, "event": "workflow_dispatch"},
              {"databaseId": 12, "event": "schedule"}]
    run_id, _, _ = pick_run(listed, {32: _artifacts(True), 12: _artifacts(True, False)})
    assert run_id == "12"


@needs_jq
@pytest.mark.parametrize("event", ["pull_request", "merge_group"])
def test_the_manual_path_never_takes_a_pull_requests_weights(pick_run, event):
    # `--branch main` matches a fork PR raised from a branch called main, and a
    # PR's shadow run uploads weights of a tree that is not main's. The same
    # three events the workflow_run guard accepts, and no others.
    listed = [{"databaseId": 40, "event": event}, {"databaseId": 13, "event": "schedule"}]
    run_id, calls, _ = pick_run(listed, {40: _artifacts(False), 13: _artifacts(False)})
    assert run_id == "13"
    assert not any("/runs/40/" in c for c in calls)


@needs_jq
def test_no_run_with_weights_is_reported_not_guessed(pick_run):
    run_id, _, stdout = pick_run([{"databaseId": 33, "event": "push"}], {33: _artifacts()})
    assert run_id == ""
    assert "mutation-weights" in stdout


@needs_jq
def test_an_unreadable_artifact_list_fails_the_step_rather_than_skipping_on(pick_run):
    # A 403/5xx on run 34's artifacts says nothing about whether it holds
    # weights. Moving on to 14 would apply an older measurement while a newer
    # one may exist, so the step goes red (an issue, since this workflow is
    # watched) and names no run.
    listed = [{"databaseId": 34, "event": "schedule"}, {"databaseId": 14, "event": "schedule"}]
    proc, output = pick_run(listed, {14: _artifacts(False)}, ok=False)
    assert proc.returncode != 0
    assert "run-id=" not in output


@needs_jq
def test_a_triggering_run_is_taken_as_is(pick_run):
    run_id, calls, _ = pick_run([], {}, triggering="777")
    assert run_id == "777"
    assert calls == []


def test_the_download_waits_for_a_run_id_and_its_absence_is_reported():
    fetch = _refresh_step("fetch")
    assert fetch["if"] == "steps.source.outputs.run-id != ''"
    assert fetch["with"]["run-id"] == "${{ steps.source.outputs.run-id }}"
    report = next(s for s in _refresh_steps() if s.get("name") == "no measurement to apply")
    # `skipped` is not `success`, so a dispatch that found no run still says so.
    assert report["if"] == "steps.fetch.outcome != 'success'"


# --------------------------------------------------------------------------
# publish.yml: only a push run may queue for the release
# --------------------------------------------------------------------------
#
# publish.yml fires on EVERY completed `ci` on main, and that now includes the
# nightly and every dispatch. Each such run joins the workflow's concurrency
# group before its guard skips it, and GitHub keeps one running and one pending
# run per group: a third arrival cancels the pending one. With a constant
# `release` group, a nightly completing while merge B's release waited behind
# merge A's cancelled B's release, and B shipped with the next merge. So only
# the runs that can release -- a push run, or the manual release button --
# share `release`; every other run gets a group of its own.

RELEASE_GROUP = ("${{ (github.event_name == 'workflow_dispatch' "
                 "|| github.event.workflow_run.event == 'push') "
                 "&& 'release' || format('release-ignored-{0}', github.run_id) }}")


@pytest.fixture(scope="module")
def publish():
    yaml = pytest.importorskip("yaml")
    if not PUBLISH_YML.exists():
        pytest.skip(".github/workflows not reachable (e.g. mutation sandbox)")
    return yaml.safe_load(PUBLISH_YML.read_text(encoding="utf-8"))


def _publish_lookup(name="workflow_run", *, event="push", run_id="9001",
                    conclusion="success", repo="o/boost"):
    run = {"event": event, "conclusion": conclusion,
           "head_repository.full_name": repo}

    def lookup(ident):
        if ident == "github.event_name":
            return name
        if ident == "github.run_id":
            return run_id
        if ident == "github.repository":
            return "o/boost"
        prefix = "github.event.workflow_run."
        if ident.startswith(prefix):
            # A dispatch of publish.yml itself carries no workflow_run payload.
            return run.get(ident[len(prefix):]) if name == "workflow_run" else None
        raise KeyError(ident)
    return lookup


def test_the_release_group_is_one_pinned_expression(publish):
    # `cancel-in-progress: false` is unchanged and still means what it did for
    # a push run: same group name, so a release is never cancelled mid-upload
    # and push runs still serialise against each other and the manual button.
    assert publish["concurrency"] == {"group": RELEASE_GROUP, "cancel-in-progress": False}


@pytest.mark.parametrize("name, event, group", [
    ("workflow_run", "push", "release"),
    ("workflow_dispatch", None, "release"),            # the manual release button
    ("workflow_run", "schedule", "release-ignored-9001"),
    ("workflow_run", "workflow_dispatch", "release-ignored-9001"),
    ("workflow_run", "pull_request", "release-ignored-9001"),  # fork PR from `main`
])
def test_only_a_run_that_can_release_queues_for_the_release(publish, name, event, group):
    lookup = _publish_lookup(name, event=event)
    assert evaluate(publish["concurrency"]["group"], lookup) == group


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch", "pull_request"])
def test_two_ignored_runs_never_share_a_group(publish, event):
    expr = publish["concurrency"]["group"]
    first = evaluate(expr, _publish_lookup(event=event, run_id="1"))
    second = evaluate(expr, _publish_lookup(event=event, run_id="2"))
    assert first != second
    assert "release" not in (first, second)


@pytest.mark.parametrize("name", ["workflow_run", "workflow_dispatch"])
@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch", "pull_request"])
@pytest.mark.parametrize("conclusion", ["success", "failure"])
@pytest.mark.parametrize("repo", ["o/boost", "fork/boost"])
def test_every_run_the_guard_lets_release_is_in_the_release_group(
        publish, name, event, conclusion, repo):
    # The group and the guard must agree: a run in its own group could release
    # concurrently with another and race it for the next version and tag.
    lookup = _publish_lookup(name, event=event, conclusion=conclusion, repo=repo)
    guard = publish["jobs"]["guard"]["if"]
    if _truthy(evaluate(guard, lookup, {"success": True})):
        assert evaluate(publish["concurrency"]["group"], lookup) == "release"
