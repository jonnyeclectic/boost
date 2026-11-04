# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""An idle nightly: when may ci's ``schedule`` run plan no mutation run?

Run 41512174636 (2026-11-02) mutated ``b294d51c`` in full and passed, and run
41682296301 (2026-11-03) mutated the same commit again, every shard, because
nothing had merged in between. ``ci_proven_tree.idle`` lets such a night plan
``none`` -- and the direction is the whole point, exactly as for the proven
push: a wrong "idle" reports green over bytes no mutation run scored this
week, a wrong "not idle" costs one full run. So every branch pinned here that
is not the one green shape comes out ``idle=false``, and the same walk, re-run
by ``_last_whole``, decides whether a skip may satisfy fact 3.

Nothing touches the network: the walk takes an injected ``api`` (``GitHub``
below, a model of the four listings it reads that raises on any other path),
and the CLI takes the same. The workflow tests read ci.yml and run its steps'
bash in temporary directories.
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci_idle_nightly.py"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load("ci_idle_nightly_under_test", SCRIPT)
pt = cli.pt      # the very module the CLI calls, so its dataclasses compare equal

SHA = "a" * 40          # main's tip, tonight and (on an idle night) at R
MOVED = "b" * 40        # main's tip before a push moved it
TREE = "e" * 40
OTHER_TREE = "f" * 40
TREES = {SHA: TREE, MOVED: OTHER_TREE}

TONIGHT = 41900000001   # this nightly's run id
R = 41682296301         # the real run it may inherit (the 2026-11-03 run's id)
T0 = datetime(2026, 11, 10, 17, 14, 31, tzinfo=UTC)     # tonight's created_at
NOW = T0 + timedelta(minutes=1)                         # when the step asks
FLOOR = "2026-11-02"                                    # (NOW - 8 days).date()


def iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def before(days=0, hours=0, seconds=0) -> datetime:
    return T0 - timedelta(days=days, hours=hours, seconds=seconds)


def mutation_job(run_id, *, status="completed", conclusion="success", name="mutation"):
    return {"id": 7, "name": name, "run_id": run_id, "status": status,
            "conclusion": conclusion}


def mutated(run_id, tree=TREE, *, expired=False):
    return {"id": 1, "name": pt.MUTATED_TREE_ARTIFACT + tree, "expired": expired,
            "workflow_run": {"id": run_id}}


def inherited(run_id, source, tree=TREE, *, expired=False):
    return {"id": 2, "name": "%s%s-from-%d" % (pt.INHERITED_TREE_ARTIFACT, tree, source),
            "expired": expired, "workflow_run": {"id": run_id}}


def shard_artifact(run_id):
    return {"id": 3, "name": "mutation-full-shard-5", "expired": False,
            "workflow_run": {"id": run_id}}


def wrun(ident, created, *, event="schedule", sha=SHA, status="completed",
         conclusion="success", attempt=1, branch="main", markers=(), jobs=None):
    """A whole-codebase run of ci.yml, with its artifacts and jobs alongside."""
    return {"id": ident, "event": event, "head_branch": branch, "head_sha": sha,
            "status": status, "conclusion": conclusion, "run_attempt": attempt,
            "created_at": iso(created) if isinstance(created, datetime) else created,
            "_markers": [shard_artifact(ident), *markers],
            "_jobs": [mutation_job(ident)] if jobs is None else list(jobs)}


def real(ident, created, *, tree=TREE, **kw):
    return wrun(ident, created, markers=[mutated(ident, tree)], **kw)


def skip(ident, created, source, *, tree=TREE, **kw):
    return wrun(ident, created, markers=[inherited(ident, source, tree)], **kw)


def tonight(created=T0, **kw):
    kw.setdefault("status", "in_progress")
    kw.setdefault("conclusion", None)
    return wrun(TONIGHT, created, **kw)


class Unmodelled(Exception):
    pass


class GitHub:
    """ci.yml's whole-codebase runs on main, answered the way the API does.

    It models the four questions the walk asks -- a commit's tree, the
    windowed and the liveness run listings, a run's artifacts, a run's jobs --
    and filters the way the server does. ``routes`` answers a path verbatim
    (a value, or an exception to raise) ahead of the model, for a server that
    answers wrongly. Any other path raises, so an unplanned request fails.
    """

    def __init__(self, *runs, routes=None, trees=None):
        self.runs = list(runs)
        self.routes = dict(routes or {})
        self.trees = dict(TREES if trees is None else trees)
        self.calls: list[str] = []

    @staticmethod
    def public(run):
        return {k: v for k, v in run.items() if not k.startswith("_")}

    def _run(self, ident):
        found = [r for r in self.runs if r["id"] == ident]
        if len(found) != 1:
            raise Unmodelled("run %d" % ident)
        return found[0]

    def __call__(self, path):
        self.calls.append(path)
        if path in self.routes:
            value = self.routes[path]
            if isinstance(value, BaseException):
                raise value
            return value
        url = urlsplit(path)
        query = {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        if m := re.fullmatch(r"git/commits/([0-9a-f]+)", url.path):
            return {"sha": m[1], "tree": {"sha": self.trees[m[1]]}}
        if url.path == "actions/workflows/ci.yml/runs":
            if set(query) == {"branch", "event", "created", "per_page"}:
                assert query["created"].startswith(">=") and query["per_page"] == "100"
                floor = query["created"][2:]
                found = [r for r in self.runs if r["event"] == query["event"]
                         and r["head_branch"] == query["branch"]
                         and str(r["created_at"])[:10] >= floor]
            elif set(query) == {"branch", "status", "event", "per_page"}:
                found = [r for r in self.runs if r["event"] == query["event"]
                         and r["head_branch"] == query["branch"]
                         and r["status"] == query["status"]]
            else:
                raise Unmodelled(path)
            found.sort(key=lambda r: str(r["created_at"]), reverse=True)
            found = found[:int(query["per_page"])]
            return {"total_count": len(found), "workflow_runs": [self.public(r) for r in found]}
        if (m := re.fullmatch(r"actions/runs/(\d+)/artifacts", url.path)) and query == {
                "per_page": "100"}:
            items = self._run(int(m[1]))["_markers"]
            return {"total_count": len(items), "artifacts": items}
        if (m := re.fullmatch(r"actions/runs/(\d+)/jobs", url.path)) and query == {
                "filter": "latest", "per_page": "100"}:
            items = self._run(int(m[1]))["_jobs"]
            return {"total_count": len(items), "jobs": items}
        raise Unmodelled(path)


def window_path(event, floor=FLOOR):
    return ("actions/workflows/ci.yml/runs?branch=main&event=%s&created=%%3E%%3D%s"
            "&per_page=100" % (event, floor))


def artifacts_path(run_id):
    return "actions/runs/%d/artifacts?per_page=100" % run_id


def jobs_path(run_id):
    return "actions/runs/%d/jobs?filter=latest&per_page=100" % run_id


def liveness_path(event):
    return ("actions/workflows/ci.yml/runs?branch=main&status=completed"
            "&event=%s&per_page=1" % event)


def ask(api, *, attempt=1, now=NOW, sha=SHA, run_id=TONIGHT):
    return pt.idle(api, sha, run_id, attempt, now)


def idle_night(*older):
    """Tonight on SHA, and what came before it (default: R, real, a day back)."""
    return GitHub(tonight(), *(older or (real(R, before(days=1)),)))


# --------------------------------------------------------------------------
# the walk: the one green shape
# --------------------------------------------------------------------------

def test_an_idle_night_inherits_the_real_run_and_names_it():
    api = idle_night()
    got = ask(api)
    assert got == pt.Idle(True, got.reason, R, TREE, before(days=1))
    assert got.reason == (
        "idle nightly: main is still %s, tree %s; inherits run %d (schedule), created "
        "2026-11-09T17:14:31Z, which mutated tree %s in full with mutation green, 1 "
        "days earlier; inherited, not re-measured, until 2026-11-16T17:14:31Z"
        % (SHA[:12], TREE[:12], R, TREE[:12]))


def test_an_idle_night_asks_exactly_these_and_never_about_itself():
    # Tonight's own run is in the window, in progress, and is passed over
    # before anything is asked about it -- not one request for it.
    api = idle_night()
    ask(api)
    assert api.calls == ["git/commits/%s" % SHA, window_path("schedule"),
                         window_path("workflow_dispatch"), artifacts_path(R), jobs_path(R)]


def test_the_window_floor_is_a_day_before_the_inheritance_age():
    # Just after midnight, the oldest inheritable real run is 7 days back to
    # the second; the floor is a UTC date, a day earlier, so it is listed.
    assert timedelta(days=7) == pt.MAX_INHERIT_AGE
    t0 = datetime(2026, 11, 10, 0, 0, 0, tzinfo=UTC)
    api = GitHub(tonight(created=t0), real(R, t0 - timedelta(days=7) + timedelta(seconds=1)))
    got = ask(api, now=t0 + timedelta(seconds=1))
    assert (got.idle, got.source_run) == (True, R)
    assert api.calls[1:3] == [window_path("schedule", "2026-11-02"),
                              window_path("workflow_dispatch", "2026-11-02")]


def test_skips_are_walked_past_to_the_real_run_they_name():
    api = idle_night(skip(102, before(days=1), R), skip(101, before(days=2), R),
                     real(R, before(days=3)))
    got = ask(api)
    assert (got.idle, got.source_run) == (True, R)
    assert "3 days earlier" in got.reason
    assert api.calls[3:] == [artifacts_path(102), artifacts_path(101), artifacts_path(R),
                             jobs_path(R)]


def test_a_dispatch_is_a_real_run_like_a_nightly():
    # The two listings are merged by created_at, not by which came back first.
    api = idle_night(skip(102, before(days=1), R),
                     real(R, before(days=2), event="workflow_dispatch"),
                     real(50, before(days=3)))
    got = ask(api)
    assert (got.idle, got.source_run) == (True, R)
    assert "run %d (workflow_dispatch)" % R in got.reason


# --------------------------------------------------------------------------
# the 7-day clock runs from the real run
# --------------------------------------------------------------------------

@pytest.mark.parametrize("age, idle", [
    (timedelta(days=7) - timedelta(seconds=1), True),
    (timedelta(days=7), False),                         # "less than": exactly 7 is out
    (timedelta(days=7, seconds=1), False),
])
def test_a_real_run_is_inherited_for_less_than_seven_days(age, idle):
    got = ask(idle_night(real(R, T0 - age)))
    assert got.idle is idle
    if not idle:
        assert "a real run is inherited for less than 7" in got.reason


def test_a_fresh_skip_does_not_restart_the_clock():
    # S1 is a day old, but what it inherited is seven days and a second old.
    got = ask(idle_night(skip(101, before(days=1), R),
                         real(R, before(days=7, seconds=1))))
    assert got.idle is False
    assert "run %d (schedule), the newest real whole-codebase run, was created 7.1 days" % R \
        in got.reason


def test_six_daily_skips_then_a_full_run():
    # Day 1 is real; days 2-7 skip; day 8 (7 days after R) is full.
    history = [real(R, before(days=7))] + [skip(100 + d, before(days=7 - d), R)
                                           for d in range(1, 7)]
    assert ask(GitHub(tonight(), *history)).idle is False
    later = GitHub(tonight(created=before(days=1)), *history[:-1])
    assert ask(later, now=before(days=1) + timedelta(minutes=1)).idle is True


# --------------------------------------------------------------------------
# red is never looked past; anything unfinished stops the walk
# --------------------------------------------------------------------------

@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "skipped",
                                        "neutral", "startup_failure", None, "Success"])
def test_a_red_real_run_plans_full_and_nothing_behind_it_is_asked(conclusion):
    api = idle_night(real(R, before(days=1), conclusion=conclusion),
                     real(50, before(days=2)))
    got = ask(api)
    assert got.idle is False
    assert "never looked past" in got.reason
    assert artifacts_path(R) not in api.calls        # judged on the run alone
    assert artifacts_path(50) not in api.calls       # and the green one behind is not reached


@pytest.mark.parametrize("marks", ["real", "skip", "none"])
def test_a_red_run_stops_the_walk_whatever_it_carries(marks):
    markers = {"real": [mutated(101)], "skip": [inherited(101, R)], "none": []}[marks]
    got = ask(idle_night(wrun(101, before(days=1), conclusion="failure", markers=markers),
                         real(R, before(days=2))))
    assert got.idle is False
    assert "run 101 (schedule) concluded failure" in got.reason


@pytest.mark.parametrize("status", ["in_progress", "queued", "waiting", "requested",
                                    "pending", None])
def test_an_older_run_still_going_stops_the_walk(status):
    got = ask(idle_night(wrun(101, before(hours=3), event="workflow_dispatch",
                              status=status, conclusion=None),
                         real(R, before(days=1))))
    assert got.idle is False
    assert "run 101 (workflow_dispatch) is %s" % (status or "unknown") in got.reason


def test_a_run_started_after_tonight_has_no_bearing():
    late = wrun(101, T0 + timedelta(seconds=30), event="workflow_dispatch",
                status="in_progress", conclusion=None)
    api = idle_night(late, real(R, before(days=1)))
    assert ask(api).idle is True
    assert artifacts_path(101) not in api.calls


def test_a_run_created_in_the_same_second_is_ordered_by_id():
    lower = real(TONIGHT - 1, T0, conclusion="failure")
    higher = real(TONIGHT + 1, T0, conclusion="failure")
    assert ask(idle_night(higher, real(R, before(days=1)))).idle is True
    assert ask(idle_night(lower, real(R, before(days=1)))).idle is False


def test_a_red_run_after_a_skip_was_taken_still_stops_the_next_one():
    # Real R, a skip, then a dispatch that ran in full and went red: tonight
    # meets the red dispatch first.
    got = ask(idle_night(real(102, before(hours=5), event="workflow_dispatch",
                              conclusion="failure"),
                         skip(101, before(days=1), R), real(R, before(days=2))))
    assert got.idle is False
    assert "run 102 (workflow_dispatch) concluded failure" in got.reason


@pytest.mark.parametrize("status, conclusion", [("in_progress", None),
                                                ("completed", "failure")],
                         ids=["still-going", "red-after-R"])
def test_a_run_created_before_the_real_run_is_never_reached(status, conclusion):
    # A dispatch D of this commit created an hour before R: ci-<event>-<sha>
    # puts the two in different concurrency groups, so D can still be going
    # tonight, or have gone red after R went green. The walk ends at R, which
    # scored these bytes in full; D is a second measurement, and fact 3 reads
    # the same created_at order (see the fact-3 tests below). Pinned, so the
    # docstring's "anything else the walk reaches" cannot quietly widen again.
    d = real(101, before(days=1, hours=1), event="workflow_dispatch",
             status=status, conclusion=conclusion)
    api = idle_night(real(R, before(days=1)), d)
    got = ask(api)
    assert (got.idle, got.source_run) == (True, R)
    assert artifacts_path(101) not in api.calls
    assert jobs_path(101) not in api.calls


# --------------------------------------------------------------------------
# what the real run must be, and what every skip passed over must say
# --------------------------------------------------------------------------

@pytest.mark.parametrize("attempt", [2, 0, True, None, "1"])
def test_only_a_first_attempt_counts(attempt):
    for runs in ([real(R, before(days=1), attempt=attempt)],
                 [skip(101, before(days=1), R, attempt=attempt), real(R, before(days=2))]):
        got = ask(idle_night(*runs))
        assert got.idle is False
        assert "only a first attempt counts" in got.reason


def test_a_rerun_of_tonight_plans_full_without_asking():
    api = idle_night()
    got = ask(api, attempt=2)
    assert got == pt.Idle(False, "this run is attempt 2, and a re-run plans the full set")
    assert api.calls == []


def test_a_push_since_the_real_run_makes_tonight_full():
    # Any push -- proven or not -- moves main's head, and the real run is of
    # the old one. Same for a skip of the old head.
    for older in ([real(R, before(days=1), sha=MOVED)],
                  [skip(101, before(days=1), R, sha=MOVED), real(R, before(days=2))]):
        got = ask(idle_night(*older))
        assert got.idle is False
        assert "ran commit %s, not %s: main has moved since" % (MOVED[:12], SHA[:12]) \
            in got.reason


def test_a_real_run_that_recorded_another_tree_is_not_inherited():
    got = ask(idle_night(real(R, before(days=1), tree=OTHER_TREE)))
    assert got.idle is False
    assert "recorded tree %s, not %s" % (OTHER_TREE[:12], TREE[:12]) in got.reason


def test_an_unmarked_green_run_stops_the_walk():
    # A run that never said what it planned is not passed over to reach an
    # older green one: it may have been the red real run's mirror image.
    got = ask(idle_night(wrun(101, before(days=1)), real(R, before(days=2))))
    assert got.idle is False
    assert "run 101 (schedule) carries no mutated-tree- or inherited-tree- marker" \
        in got.reason


@pytest.mark.parametrize("expired", [True, None, "false"])
def test_a_marker_that_is_not_plainly_live_stops_the_walk(expired):
    run = wrun(R, before(days=1), markers=[{**mutated(R), "expired": expired}])
    got = ask(idle_night(run))
    assert got.idle is False
    assert "marker has expired" in got.reason


@pytest.mark.parametrize("job, word", [
    (None, "has no mutation job"),
    (mutation_job(R, conclusion="failure"), "mutation job is completed/failure"),
    (mutation_job(R, conclusion="skipped"), "mutation job is completed/skipped"),
    (mutation_job(R, status="in_progress", conclusion=None),
     "mutation job is in_progress/unknown"),
    (mutation_job(R, name="mutation-plan"), "has no mutation job"),
])
def test_the_real_runs_own_mutation_job_must_be_green(job, word):
    run = real(R, before(days=1), jobs=[] if job is None else [job])
    got = ask(idle_night(run))
    assert got.idle is False
    assert word in got.reason


def test_two_mutation_jobs_or_one_of_another_run_is_an_error():
    for jobs in ([mutation_job(R), mutation_job(R)], [mutation_job(R + 1)]):
        with pytest.raises(ValueError):
            ask(idle_night(real(R, before(days=1), jobs=jobs)))


def test_a_skip_that_names_another_source_stops_the_walk():
    got = ask(idle_night(skip(101, before(days=1), 77), real(R, before(days=2))))
    assert got.idle is False
    assert "run 101 inherited from run 77, not from run %d (schedule)" % R in got.reason


def test_a_window_of_skips_with_no_real_run_plans_full():
    got = ask(idle_night(skip(101, before(days=1), 77), skip(100, before(days=2), 77)))
    assert got.idle is False
    assert got.reason == ("not idle: no real whole-codebase run of ci.yml on main "
                          "created since %s" % FLOOR)


def test_an_empty_window_plans_full():
    got = ask(GitHub(tonight()))
    assert got == pt.Idle(False, "not idle: no real whole-codebase run of ci.yml on main "
                                 "created since %s" % FLOOR)


def test_api_text_never_reaches_the_reason():
    hostile = "in_progress\n::error::pwned"
    got = ask(idle_night(wrun(101, before(hours=1), status=hostile, conclusion=hostile),
                         real(R, before(days=1))))
    assert got.idle is False
    assert "pwned" not in got.reason and "\n" not in got.reason
    assert "is unknown" in got.reason


# --------------------------------------------------------------------------
# every contradiction raises (the CLI makes it error: <type>)
# --------------------------------------------------------------------------

def _listing(*runs):
    return {"total_count": len(runs), "workflow_runs": [GitHub.public(r) for r in runs]}


@pytest.mark.parametrize("bad", [
    {"event": "push"}, {"event": None}, {"head_branch": "feature/x"}, {"head_branch": None},
    {"id": "41"}, {"id": True}, {"created_at": None}, {"created_at": "yesterday"},
    {"created_at": "2026-11-09T17:14:31"},
], ids=lambda d: "%s=%r" % next(iter(d.items())))
def test_a_window_run_that_contradicts_its_query_is_an_error(bad):
    odd = {**real(R, before(days=1)), **bad}
    api = idle_night()
    api.routes[window_path("schedule")] = _listing(tonight(), odd)
    with pytest.raises(ValueError):
        ask(api)


@pytest.mark.parametrize("listing", [
    {"total_count": 3, "workflow_runs": []},            # a second page
    {"workflow_runs": []},                              # no total_count
    {"total_count": 0},                                 # no list
    [],
])
def test_a_window_listing_of_the_wrong_shape_is_an_error(listing):
    api = idle_night()
    api.routes[window_path("workflow_dispatch")] = listing
    with pytest.raises(ValueError):
        ask(api)


@pytest.mark.parametrize("me", [
    None,                                               # tonight is not listed
    tonight(event="workflow_dispatch"),                 # a dispatch never skips
    tonight(sha=MOVED),                                 # another commit
    tonight(created=NOW + pt.CLOCK_SKEW + timedelta(seconds=1)),
])
def test_tonight_must_be_in_the_window_as_a_schedule_run_of_this_commit(me):
    runs = [real(R, before(days=1))] + ([] if me is None else [me])
    with pytest.raises(ValueError):
        ask(GitHub(*runs))


def test_tonight_listed_twice_is_an_error():
    api = idle_night()
    api.routes[window_path("schedule")] = _listing(tonight(), tonight(),
                                                   real(R, before(days=1)))
    with pytest.raises(ValueError):
        ask(api)


@pytest.mark.parametrize("tree", ["", "E" * 40, "e" * 39, None])
def test_a_commit_tree_that_is_not_an_object_id_is_an_error(tree):
    api = idle_night()
    api.routes["git/commits/%s" % SHA] = {"tree": {"sha": tree}}
    with pytest.raises(ValueError):
        ask(api)


@pytest.mark.parametrize("entry", [
    {"name": pt.MUTATED_TREE_ARTIFACT + "E" * 40},
    {"name": pt.MUTATED_TREE_ARTIFACT + TREE + "x"},
    {"name": pt.INHERITED_TREE_ARTIFACT + TREE},
    {"name": "%s%s-from-0" % (pt.INHERITED_TREE_ARTIFACT, TREE)},
    {"name": "%s%s-from-%d" % (pt.INHERITED_TREE_ARTIFACT, TREE, R),
     "workflow_run": {"id": R + 1}},
    {"name": pt.MUTATED_TREE_ARTIFACT + TREE, "workflow_run": {"id": str(R)}},
], ids=["upper", "trailing", "no-source", "zero-source", "other-run", "string-owner"])
def test_a_malformed_or_foreign_marker_is_an_error(entry):
    marker = {"id": 1, "expired": False, "workflow_run": {"id": R}, **entry}
    with pytest.raises(ValueError):
        ask(idle_night(wrun(R, before(days=1), markers=[marker])))


@pytest.mark.parametrize("markers", [[mutated(R), inherited(R, 5)],
                                     [mutated(R), mutated(R)]], ids=["mixed", "twice"])
def test_a_run_with_two_markers_stops_the_walk(markers):
    got = ask(idle_night(wrun(R, before(days=1), markers=markers)))
    assert got.idle is False
    assert "run %d (schedule) carries 2 markers, so what it was is ambiguous" % R \
        in got.reason


def test_a_marker_that_names_no_run_is_read_the_listing_is_per_run():
    marker = {k: v for k, v in mutated(R).items() if k != "workflow_run"}
    assert ask(idle_night(wrun(R, before(days=1), markers=[marker]))).idle is True


def test_a_sha256_tree_is_a_tree():
    long_tree = "e" * 64
    api = GitHub(tonight(), real(R, before(days=1), tree=long_tree),
                 trees={SHA: long_tree})
    got = ask(api)
    assert (got.idle, got.source_tree) == (True, long_tree)


@pytest.mark.parametrize("listing", [
    {"total_count": 101, "artifacts": []},
    {"artifacts": []},
    {"total_count": 0, "artifacts": "x"},
])
def test_an_artifact_listing_of_the_wrong_shape_is_an_error(listing):
    api = idle_night()
    api.routes[artifacts_path(R)] = listing
    with pytest.raises(ValueError):
        ask(api)


# --------------------------------------------------------------------------
# fact 3: a skip is green only when its inheritance still holds
# --------------------------------------------------------------------------

CHECK = datetime(2026, 11, 10, 23, 0, tzinfo=UTC)       # when a push asks
W_AT = CHECK - timedelta(hours=6)                       # the skip it finds


def w_skip(source=R, **kw):
    return skip(TONIGHT, W_AT, source, **kw)


def fact3(*runs, routes=None):
    api = GitHub(*runs, routes=routes)
    return pt._last_whole(api), api


def _good_candidate():
    return pt.Candidate("h", "T", 7, "success", run_created_at=CHECK - timedelta(hours=1),
                        artifacts=(pt.Artifact(pt.TESTED_TREE_ARTIFACT + "T", False, 7),))


def test_a_real_newest_run_reads_as_before_with_one_more_request():
    nightly, api = fact3(real(R, W_AT))
    assert nightly == pt.Nightly("success", W_AT)
    assert api.calls == [liveness_path("schedule"), liveness_path("workflow_dispatch"),
                         artifacts_path(R)]


def test_an_unmarked_newest_run_reads_as_before():
    # Every whole-codebase run before markers existed planned full.
    nightly, api = fact3(wrun(R, W_AT))
    assert nightly == pt.Nightly("success", W_AT)
    assert api.calls[-1] == artifacts_path(R)


def test_a_red_newest_run_is_returned_without_asking_what_it_was():
    nightly, api = fact3(skip(R, W_AT, 5, conclusion="failure"))
    assert nightly == pt.Nightly("failure", W_AT)
    assert len(api.calls) == 2


def test_a_verified_skip_counts_for_fact_3():
    nightly, api = fact3(w_skip(), real(R, W_AT - timedelta(days=3)))
    assert nightly == pt.Nightly("success", W_AT)
    # Its age is still its own: 6 h, inside 48.
    assert pt.decide("T", [_good_candidate()], nightly, now=CHECK).skip is True
    assert window_path("schedule", "2026-11-02") in api.calls


def test_the_re_check_ages_the_real_run_from_the_skip_not_the_clock():
    # R is 6 days 23 h before the skip -- inheritable then -- and more than 7
    # days before CHECK. The skip still holds; its own 48 h is fact 3's bound.
    nightly, _ = fact3(w_skip(), real(R, W_AT - timedelta(days=6, hours=23)))
    assert nightly == pt.Nightly("success", W_AT)


@pytest.mark.parametrize("older", [
    [real(R, W_AT - timedelta(days=1), conclusion="failure")],
    [real(R, W_AT - timedelta(days=1), tree=OTHER_TREE)],
    [real(R, W_AT - timedelta(days=7))],
    [skip(101, W_AT - timedelta(days=1), 77)],
    [wrun(101, W_AT - timedelta(hours=1), status="in_progress", conclusion=None),
     real(R, W_AT - timedelta(days=1))],
    [wrun(101, W_AT - timedelta(hours=1)), real(R, W_AT - timedelta(days=1))],
    [real(R, W_AT - timedelta(days=1), sha=MOVED)],
    [real(R, W_AT - timedelta(days=1), jobs=[mutation_job(R, conclusion="failure")])],
], ids=["source-red", "other-tree", "seven-days", "only-skips", "older-running",
        "older-unmarked", "other-commit", "mutation-job-red"])
def test_a_skip_whose_inheritance_does_not_hold_is_unproven(older):
    nightly, _ = fact3(w_skip(), *older)
    assert nightly == pt.Nightly(pt.UNPROVEN_SKIP, W_AT)
    decision = pt.decide("T", [_good_candidate()], nightly, now=CHECK)
    assert decision.skip is False
    assert "concluded unproven_skip" in decision.reason


def test_a_skip_whose_source_is_not_the_one_it_names_is_unproven():
    # It names run 77; the walk finds R.
    nightly, _ = fact3(w_skip(source=77), real(R, W_AT - timedelta(days=1)))
    assert nightly.conclusion == pt.UNPROVEN_SKIP


def test_a_red_full_run_that_raced_in_before_the_skip_makes_it_unproven():
    # A dispatch D, full and red, created between R and the skip: whatever
    # the skip believed, the walk now meets D first.
    nightly, _ = fact3(w_skip(), real(102, W_AT - timedelta(hours=2), event="workflow_dispatch",
                                      conclusion="failure"),
                       real(R, W_AT - timedelta(days=1)))
    assert nightly.conclusion == pt.UNPROVEN_SKIP


def test_fact_3_orders_the_same_red_dispatch_behind_the_real_run():
    # The walk's limit, as fact 3 has it: a red dispatch created before the
    # newest real run is not the newest completed whole-codebase run.
    d = real(101, W_AT - timedelta(hours=1), event="workflow_dispatch",
             conclusion="failure")
    nightly, _ = fact3(real(R, W_AT), d)
    assert nightly == pt.Nightly("success", W_AT)


def test_a_run_started_after_the_skip_does_not_move_its_answer():
    later = wrun(103, W_AT + timedelta(hours=1), event="workflow_dispatch",
                 status="in_progress", conclusion=None)
    nightly, _ = fact3(later, w_skip(), real(R, W_AT - timedelta(days=1)))
    assert nightly == pt.Nightly("success", W_AT)


def test_a_verified_skip_more_than_48_hours_old_is_stale():
    w_at = CHECK - pt.MAX_NIGHTLY_AGE - timedelta(seconds=1)
    nightly, _ = fact3(skip(TONIGHT, w_at, R), real(R, w_at - timedelta(days=1)))
    assert nightly == pt.Nightly("success", w_at)
    decision = pt.decide("T", [_good_candidate()], nightly, now=CHECK)
    assert decision.skip is False
    assert "nightly stale" in decision.reason


@pytest.mark.parametrize("field, value", [("created_at", None), ("created_at", "soon"),
                                          ("head_sha", "main"), ("head_sha", None)])
def test_a_skip_that_cannot_be_placed_is_unproven(field, value):
    w = {**w_skip(), field: value}
    nightly, api = fact3(w, real(R, W_AT - timedelta(days=1)))
    assert nightly is not None and nightly.conclusion == pt.UNPROVEN_SKIP
    assert not any("created=" in c for c in api.calls)


def test_a_rerun_of_a_skip_is_unproven_not_an_error():
    # Its second attempt was not idle, planned full and uploaded a real
    # marker beside the first attempt's skip marker: one listing, two stories.
    w = wrun(TONIGHT, W_AT, attempt=2, markers=[inherited(TONIGHT, R), mutated(TONIGHT)])
    nightly, api = fact3(w, real(R, W_AT - timedelta(days=1)))
    assert nightly == pt.Nightly(pt.UNPROVEN_SKIP, W_AT)
    assert not any("created=" in c for c in api.calls)


def test_a_skip_on_a_second_attempt_alone_is_unproven():
    nightly, _ = fact3(w_skip(attempt=2), real(R, W_AT - timedelta(days=1)))
    assert nightly.conclusion == pt.UNPROVEN_SKIP


def test_a_newest_run_with_two_real_markers_reads_as_real():
    w = wrun(R, W_AT, attempt=2, markers=[mutated(R), mutated(R)])
    nightly, _ = fact3(w)
    assert nightly == pt.Nightly("success", W_AT)


def test_a_newest_run_without_an_integer_id_is_an_error():
    w = {**real(R, W_AT), "id": "41"}
    api = GitHub(routes={liveness_path("schedule"): _listing(w),
                         liveness_path("workflow_dispatch"): _listing()})
    with pytest.raises(ValueError, match="integer id"):
        pt._last_whole(api)


def test_unproven_skip_is_a_word_both_outputs_carry_intact():
    assert pt._WORD.fullmatch(pt.UNPROVEN_SKIP)
    assert pt._BASE_WORD.fullmatch("nightly-" + pt.UNPROVEN_SKIP)


BEFORE = "d" * 40
BASE_RUN = 41148140704


def test_a_green_base_under_an_unproven_skip_is_written_not_green(tmp_path):
    out = tmp_path / "out"
    routes = {
        "commits/%s/pulls" % SHA: [],
        ("actions/workflows/ci.yml/runs?branch=main&event=push&head_sha=%s&per_page=100"
         % BEFORE): {"total_count": 1, "workflow_runs": [
             {"id": BASE_RUN, "event": "push", "head_branch": "main", "head_sha": BEFORE,
              "created_at": "2026-11-10T20:00:00Z"}]},
        jobs_path(BASE_RUN): {"total_count": 1, "jobs": [mutation_job(BASE_RUN)]},
    }
    api = GitHub(w_skip(), real(R, W_AT - timedelta(days=1), conclusion="failure"),
                 routes=routes)
    argv = ["--sha", SHA, "--now", CHECK.isoformat(), "--before", BEFORE]
    assert pt.main(argv, api=api, env={"GITHUB_OUTPUT": str(out)}) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert "base_mutation_green=false" in lines
    assert "base_mutation=nightly-unproven_skip" in lines
    assert "skip=false" in lines


# --------------------------------------------------------------------------
# the CLI
# --------------------------------------------------------------------------

ARGV = ["--sha", SHA, "--run-id", str(TONIGHT), "--run-attempt", "1", "--now", NOW.isoformat()]


@pytest.fixture
def env(tmp_path):
    return {"GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main",
            "GITHUB_OUTPUT": str(tmp_path / "out"),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")}


def outputs(env) -> dict:
    lines = Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8").splitlines()
    pairs = dict(line.split("=", 1) for line in lines)
    assert len(pairs) == len(lines) == 4, lines
    return pairs


def test_main_writes_the_inheritance_and_exits_zero(env):
    assert cli.main(ARGV, api=idle_night(), env=env) == 0
    got = outputs(env)
    assert {k: got[k] for k in ("idle", "source_run", "source_tree")} == {
        "idle": "true", "source_run": str(R), "source_tree": TREE}
    assert got["reason"].startswith("idle nightly: main is still %s" % SHA[:12])
    assert "2026-11-09T17:14:31Z" in got["reason"]
    summary = Path(env["GITHUB_STEP_SUMMARY"]).read_text(encoding="utf-8")
    assert summary.startswith("### Idle-nightly check\n\n- idle: `true`\n- reason: idle nightly")


def test_main_writes_false_with_empty_sources_when_not_idle(env):
    api = idle_night(real(R, before(days=1), conclusion="failure"))
    assert cli.main(ARGV, api=api, env=env) == 0
    got = outputs(env)
    assert (got["idle"], got["source_run"], got["source_tree"]) == ("false", "", "")
    assert got["reason"].startswith("not idle: run %d (schedule) concluded failure" % R)


@pytest.mark.parametrize("event, ref", [
    ("workflow_dispatch", "refs/heads/main"), ("push", "refs/heads/main"),
    ("pull_request", "refs/pull/7/merge"), ("", "refs/heads/main"),
    ("schedule", "refs/heads/feature"), ("schedule", ""),
])
def test_only_a_schedule_run_on_main_is_asked_about(env, event, ref):
    api = idle_night()
    assert cli.main(ARGV, api=api, env={**env, "GITHUB_EVENT_NAME": event,
                                        "GITHUB_REF": ref}) == 0
    assert outputs(env)["idle"] == "false"
    assert api.calls == []


@pytest.mark.parametrize("flag, value", [
    ("--sha", "main"), ("--sha", SHA.upper()), ("--sha", SHA[:12]),
    ("--run-id", "0"), ("--run-id", "-1"), ("--run-id", "1e3"), ("--run-id", ""),
    ("--run-id", "1" * 21), ("--run-attempt", "0"), ("--run-attempt", "two"),
    ("--run-attempt", ""), ("--now", "yesterday"), ("--now", "2026-11-10T17:00:00"),
])
def test_a_bad_argument_is_not_idle_and_asks_nothing(env, flag, value):
    argv = list(ARGV)
    argv[argv.index(flag) + 1] = value
    api = idle_night()
    assert cli.main(argv, api=api, env=env) == 0
    assert outputs(env)["idle"] == "false"
    assert api.calls == []


def test_a_missing_argument_is_not_idle(env):
    assert cli.main(["--sha", SHA], api=idle_night(), env=env) == 0
    assert outputs(env)["reason"] == "error: UsageError"


def test_a_second_attempt_is_not_idle_and_asks_nothing(env):
    argv = list(ARGV)
    argv[argv.index("--run-attempt") + 1] = "2"
    api = idle_night()
    cli.main(argv, api=api, env=env)
    assert outputs(env)["idle"] == "false"
    assert api.calls == []


@pytest.mark.parametrize("exc", [
    urllib.error.HTTPError("https://api.github.com/x", 403, "rate limit", None, None),
    urllib.error.HTTPError("https://api.github.com/x", 404, "nope", None, None),
    urllib.error.HTTPError("https://api.github.com/x", 429, "slow down", None, None),
    urllib.error.HTTPError("https://api.github.com/x", 500, "boom", None, None),
    urllib.error.URLError("no route"),
    TimeoutError("timed out"),
    json.JSONDecodeError("bad", "x", 0),
    ValueError("odd shape"),
], ids=["403", "404", "429", "500", "url", "timeout", "json", "shape"])
@pytest.mark.parametrize("position", range(5))
def test_an_error_at_any_request_is_not_idle(env, exc, position):
    model = idle_night()

    def api(path):
        if len(model.calls) == position:
            model.calls.append(path)
            raise exc
        return model(path)

    assert cli.main(ARGV, api=api, env=env) == 0
    got = outputs(env)
    assert (got["idle"], got["source_run"], got["source_tree"]) == ("false", "", "")
    assert got["reason"] == "error: %s" % type(exc).__name__


def test_an_idle_verdict_with_an_unsound_source_is_written_false(env, monkeypatch):
    for bad in (pt.Idle(True, "x", None, TREE, NOW), pt.Idle(True, "x", 0, TREE, NOW),
                pt.Idle(True, "x", True, TREE, NOW), pt.Idle(True, "x", R, "E" * 40, NOW),
                pt.Idle(True, "x", R, TREE, None),
                pt.Idle(True, "x", R, TREE, NOW.replace(tzinfo=None))):
        Path(env["GITHUB_OUTPUT"]).write_text("", encoding="utf-8")
        monkeypatch.setattr(pt, "idle", lambda *a, verdict=bad, **k: verdict)
        cli.main(ARGV, api=idle_night(), env=env)
        got = outputs(env)
        assert (got["idle"], got["source_run"], got["source_tree"]) == ("false", "", ""), bad
        assert "did not check out" in got["reason"]


def test_without_github_output_the_outputs_go_to_stdout(capsys):
    env = {"GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main"}
    assert cli.main(ARGV, api=idle_night(), env=env) == 0
    out = capsys.readouterr().out
    assert "\nidle=true\nsource_run=%d\nsource_tree=%s\nreason=" % (R, TREE) in out


@pytest.mark.parametrize("extra, reason", [
    ({}, "GITHUB_TOKEN is not set"),
    ({"GITHUB_TOKEN": "t"}, "GITHUB_REPOSITORY is unset or malformed"),
    ({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "../x"},
     "GITHUB_REPOSITORY is unset or malformed"),
])
def test_missing_credentials_are_not_idle_before_any_request(env, monkeypatch, extra, reason):
    def refuse(*_a, **_k):
        raise AssertionError("no request may be made")
    monkeypatch.setattr(pt, "make_api", refuse)
    assert cli.main(ARGV, env={**env, **extra}) == 0
    assert outputs(env)["reason"] == reason


def test_the_environment_wires_repo_and_token_into_the_api(env, monkeypatch):
    seen = {}

    def make_api(repo, token):
        seen.update(repo=repo, token=token)
        return idle_night()

    monkeypatch.setattr(pt, "make_api", make_api)
    cli.main(ARGV, env={**env, "GITHUB_TOKEN": " tok ", "GITHUB_REPOSITORY": "o/boost"})
    assert seen == {"repo": "o/boost", "token": "tok"}
    assert outputs(env)["idle"] == "true"


def test_the_token_never_reaches_the_log(env, monkeypatch, capsys):
    def make_api(repo, token):
        def api(path):
            raise ValueError("leaked %s" % token)
        return api

    monkeypatch.setattr(pt, "make_api", make_api)
    cli.main(ARGV, env={**env, "GITHUB_TOKEN": "s3cret", "GITHUB_REPOSITORY": "o/boost"})
    captured = capsys.readouterr()
    assert "s3cret" not in captured.out + captured.err
    assert "***" in captured.err
    assert outputs(env)["reason"] == "error: ValueError"


def test_run_as_a_script_with_no_credentials_it_exits_zero_not_idle(tmp_path):
    # The inherited environment minus every GITHUB_* (as the proven-tree
    # script test does): a Windows child needs SYSTEMROOT and friends.
    out = tmp_path / "out"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
    env.update(GITHUB_OUTPUT=str(out), GITHUB_EVENT_NAME="schedule",
               GITHUB_REF="refs/heads/main")
    proc = subprocess.run([sys.executable, str(SCRIPT), *ARGV], env=env, cwd=tmp_path,
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    assert out.read_text(encoding="utf-8").splitlines() == [
        "idle=false", "source_run=", "source_tree=", "reason=GITHUB_TOKEN is not set"]


# --------------------------------------------------------------------------
# ci.yml: the job, the tree, the markers
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def jobs():
    yaml = pytest.importorskip("yaml")
    if not CI_YML.exists():
        pytest.skip(".github/workflows not reachable (e.g. mutation sandbox)")
    return yaml.safe_load(CI_YML.read_text(encoding="utf-8"))["jobs"]


def _step(job, step_id=None, *, name=None):
    found = [s for s in job["steps"] if (step_id is None or s.get("id") == step_id)
             and (name is None or s.get("name") == name)]
    assert len(found) == 1, (step_id, name)
    return found[0]


def _uploads(job):
    return [s for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact@")]


def test_the_idle_job_holds_read_scopes_only(jobs):
    job = jobs["idle-nightly"]
    assert job["permissions"] == {"contents": "read", "actions": "read"}
    assert job["timeout-minutes"] <= 5
    assert "continue-on-error" not in job
    assert job["steps"][0]["uses"].startswith("step-security/harden-runner@")
    checkout = job["steps"][1]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["persist-credentials"] is False


def test_the_idle_step_passes_only_the_token_and_expands_nothing_in_run(jobs):
    job = jobs["idle-nightly"]
    step = _step(job, "idle")
    assert step["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
    assert step["run"] == ('python3 scripts/ci_idle_nightly.py --sha "$GITHUB_SHA" '
                           '--run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT"')
    assert "continue-on-error" not in step
    assert job["outputs"] == {key: "${{ steps.idle.outputs.%s }}" % key
                              for key in ("idle", "source_run", "source_tree", "reason")}


def test_the_planner_waits_for_it_and_its_token_does_not_grow(jobs):
    plan = jobs["mutation-plan"]
    assert plan["needs"] == ["proven", "idle-nightly"]
    assert plan["permissions"] == {"contents": "read"}
    assert plan["if"] == "${{ !cancelled() }}"


def test_the_scope_and_plan_steps_read_the_verdict_through_env(jobs):
    plan = jobs["mutation-plan"]
    scope = _step(plan, "scope")
    assert {k: scope["env"][k] for k in ("IDLE", "IDLE_RUN", "IDLE_TREE", "TREE")} == {
        "IDLE": "${{ needs.idle-nightly.outputs.idle }}",
        "IDLE_RUN": "${{ needs.idle-nightly.outputs.source_run }}",
        "IDLE_TREE": "${{ needs.idle-nightly.outputs.source_tree }}",
        "TREE": "${{ steps.tree.outputs.tree }}"}
    # The attempt is the runner's default, read by this attempt: an output
    # or an expression here could carry an earlier attempt's.
    assert "GITHUB_RUN_ATTEMPT" not in scope["env"]
    assert '[ "$GITHUB_RUN_ATTEMPT" != 1 ]' in scope["run"]
    write = _step(plan, "plan")
    assert write["env"]["IDLE"] == "${{ steps.scope.outputs.idle }}"
    assert write["env"]["IDLE_REASON"] == "${{ needs.idle-nightly.outputs.reason }}"
    for step in (scope, write, _step(plan, "tree")):
        assert "${{" not in step["run"]


needs_git = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash") or not shutil.which("git"),
    reason="runs a workflow step's bash in a git repository")


@needs_git
def test_the_tree_step_records_the_checkouts_tree(jobs, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path),
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

    def git(*args):
        return subprocess.run(["git", "-c", "user.email=ci@boost.test", "-c", "user.name=CI",
                               "-c", "commit.gpgsign=false", *args], cwd=repo, env=git_env,
                              capture_output=True, text=True, check=True).stdout.strip()

    git("init", "-q")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-qm", "f")
    temp, out = tmp_path / "runner-temp", tmp_path / "out"
    temp.mkdir()
    script = tmp_path / "step.sh"
    script.write_text(_step(jobs["mutation-plan"], "tree")["run"], encoding="utf-8")
    proc = subprocess.run(["bash", "-e", str(script)], cwd=repo, capture_output=True, text=True,
                          env={**git_env, "RUNNER_TEMP": str(temp), "GITHUB_OUTPUT": str(out),
                               "GITHUB_SHA": git("rev-parse", "HEAD")}, check=False)
    assert proc.returncode == 0, proc.stderr
    tree = git("rev-parse", "HEAD^{tree}")
    assert out.read_text(encoding="utf-8") == "tree=%s\n" % tree
    assert (temp / "whole-codebase-tree").read_text(encoding="utf-8") == "%s %s\n" % (
        tree, git("rev-parse", "HEAD"))


def _markers(jobs):
    """The two marker uploads, by prefix -- exactly one of each."""
    plan = jobs["mutation-plan"]
    found = {}
    for step in _uploads(plan):
        name = step["with"]["name"]
        for prefix in (pt.MUTATED_TREE_ARTIFACT, pt.INHERITED_TREE_ARTIFACT):
            if name.startswith(prefix):
                assert prefix not in found, "two uploads of %s" % prefix
                found[prefix] = step
    assert set(found) == {pt.MUTATED_TREE_ARTIFACT, pt.INHERITED_TREE_ARTIFACT}
    return found


def test_each_marker_is_named_for_the_tree_and_parses_as_the_walk_reads_it(jobs):
    found = _markers(jobs)
    real_name = found[pt.MUTATED_TREE_ARTIFACT]["with"]["name"]
    skip_name = found[pt.INHERITED_TREE_ARTIFACT]["with"]["name"]
    assert real_name == pt.MUTATED_TREE_ARTIFACT + "${{ steps.tree.outputs.tree }}"
    assert skip_name == (pt.INHERITED_TREE_ARTIFACT + "${{ steps.tree.outputs.tree }}"
                         "-from-${{ steps.scope.outputs.source_run }}")
    rendered = real_name.replace("${{ steps.tree.outputs.tree }}", TREE)
    assert pt._MUTATED_NAME.fullmatch(rendered)["tree"] == TREE
    rendered = skip_name.replace("${{ steps.tree.outputs.tree }}", TREE).replace(
        "${{ steps.scope.outputs.source_run }}", str(R))
    match = pt._INHERITED_NAME.fullmatch(rendered)
    assert (match["tree"], int(match["source"])) == (TREE, R)


def test_the_markers_outlive_every_read_of_them(jobs):
    # A fact-3 re-check of a skip up to 48 h old reads a real run up to 7
    # days before it: 9 days, and a day's margin.
    floor = (pt.MAX_INHERIT_AGE + pt.MAX_NIGHTLY_AGE).days + 1
    pins = {s["uses"] for s in _uploads(jobs["mutation-plan"])}
    assert len(pins) == 1, "the markers use the upload pin every other upload uses"
    for step in _markers(jobs).values():
        spec = step["with"]
        assert int(spec["retention-days"]) >= floor
        assert spec["if-no-files-found"] == "error"
        assert spec["path"] == "${{ runner.temp }}/whole-codebase-tree"
        assert "continue-on-error" not in step


def test_the_markers_are_uploaded_from_the_written_plan_before_any_shard(jobs):
    steps = jobs["mutation-plan"]["steps"]
    ids = [s.get("id") for s in steps]
    assert ids.index("tree") < ids.index("scope") < ids.index("plan")
    plan_at = ids.index("plan")
    for step in _markers(jobs).values():
        assert steps.index(step) > plan_at
    # The shards wait on the whole planner job, so every marker is up first.
    assert jobs["mutation-shard"]["needs"] == "mutation-plan"


def test_no_download_in_the_gate_picks_up_a_marker(jobs):
    names = [pt.MUTATED_TREE_ARTIFACT + TREE,
             "%s%s-from-%d" % (pt.INHERITED_TREE_ARTIFACT, TREE, R)]
    for step in jobs["mutation"]["steps"]:
        if not step.get("uses", "").startswith("actions/download-artifact@"):
            continue
        pattern = step["with"].get("pattern") or step["with"].get("name")
        assert not any(fnmatch.fnmatchcase(n, pattern) for n in names), pattern
