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
import os
import subprocess
import sys
import urllib.error
import urllib.request
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
TREE = "T" * 40
OTHER = "O" * 40

GOOD = pt.Candidate("h", "T", 7, "success")


# --------------------------------------------------------------------------
# decide: the pure decision
# --------------------------------------------------------------------------

def test_skips_when_tree_matches_a_green_pr_and_nightly_is_green():
    assert pt.decide("T", [GOOD], "success") == pt.Decision(True, ANY, 7)


def test_the_skip_reason_names_the_run_and_the_tree():
    reason = pt.decide("T" * 40, [pt.Candidate("h" * 40, "T" * 40, 7, "success")],
                       "success").reason
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
             pt.Candidate("h3", "T", 3, "success")]     # the proof
    assert pt.decide("T", cands, "success") == pt.Decision(True, ANY, 3)


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


def pr(head):
    return {"number": 1, "head": {"sha": head}}


def run(run_id=7, *, conclusion="success", event="pull_request", head_sha=HEAD,
        attempt=1, created="2026-10-30T10:00:00Z", status="completed"):
    return {"id": run_id, "event": event, "head_sha": head_sha, "status": status,
            "conclusion": conclusion, "run_attempt": attempt, "created_at": created}


def runs(*items):
    return {"total_count": len(items), "workflow_runs": list(items)}


def pr_runs_path(head):
    return "actions/workflows/ci.yml/runs?head_sha=%s&event=pull_request" % head


def whole_path(event):
    return ("actions/workflows/ci.yml/runs?branch=main&status=completed"
            "&event=%s&per_page=1" % event)


SCHEDULE = whole_path("schedule")
DISPATCH = whole_path("workflow_dispatch")


def green_routes(**overrides):
    """A push that is fully proven: one PR, equal trees, green run, green nightly."""
    routes = {
        "git/commits/%s" % SHA: commit(TREE),
        "commits/%s/pulls" % SHA: [pr(HEAD)],
        "git/commits/%s" % HEAD: commit(TREE),
        pr_runs_path(HEAD): runs(run()),
        SCHEDULE: runs(run(100, event="schedule", head_sha=SHA)),
        DISPATCH: runs(),
    }
    routes.update(overrides)
    return routes


# --------------------------------------------------------------------------
# gather: what it asks GitHub, and what it makes of the answers
# --------------------------------------------------------------------------

def test_gather_assembles_the_three_facts_decide_needs():
    api = FakeApi(green_routes())
    merge_tree, cands, last = pt.gather(api, SHA)
    assert merge_tree == TREE
    assert cands == [pt.Candidate(HEAD, TREE, 7, "success", "pull_request", HEAD, 1)]
    assert last == "success"
    assert pt.decide(merge_tree, cands, last) == pt.Decision(True, ANY, 7)


def test_gather_asks_the_documented_endpoints_and_nothing_else():
    api = FakeApi(green_routes())
    pt.gather(api, SHA)
    assert sorted(api.calls) == sorted([
        "git/commits/%s" % SHA,
        "commits/%s/pulls" % SHA,
        "git/commits/%s" % HEAD,
        pr_runs_path(HEAD),
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
    assert pt.gather(api, SHA)[2] == "failure"


def test_gather_picks_the_newest_whole_codebase_run_whichever_query_it_came_from():
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(1, event="schedule", conclusion="failure",
                           created="2026-10-30T09:30:00Z")),
        DISPATCH: runs(run(2, event="workflow_dispatch", conclusion="success",
                           created="2026-10-31T11:00:00Z")),
    }))
    assert pt.gather(api, SHA)[2] == "success"


def test_gather_compares_instants_not_strings():
    # 23:00-05:00 is 04:00Z the next day: later than 01:00Z, though it sorts earlier.
    api = FakeApi(green_routes(**{
        SCHEDULE: runs(run(1, event="schedule", conclusion="success",
                           created="2026-10-31T01:00:00+00:00")),
        DISPATCH: runs(run(2, event="workflow_dispatch", conclusion="failure",
                           created="2026-10-30T23:00:00-05:00")),
    }))
    assert pt.gather(api, SHA)[2] == "failure"


def test_gather_uses_the_one_whole_codebase_query_that_has_a_run():
    only_dispatch = FakeApi(green_routes(**{
        SCHEDULE: runs(),
        DISPATCH: runs(run(1, event="workflow_dispatch", conclusion="success")),
    }))
    assert pt.gather(only_dispatch, SHA)[2] == "success"


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


def test_a_lone_whole_codebase_run_needs_no_timestamp():
    lone = run(1, event="schedule", conclusion="success")
    del lone["created_at"]
    api = FakeApi(green_routes(**{SCHEDULE: runs(lone)}))
    assert pt.gather(api, SHA)[2] == "success"


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
    assert pt.decide(merge_tree, cands, last).skip is False


@pytest.mark.parametrize("missing", ["event", "head_sha", "run_attempt"])
def test_a_run_missing_a_fact_decide_checks_is_not_proof(missing):
    # Absent is unknown, and unknown is never defaulted into "fine".
    bare = run()
    del bare[missing]
    api = FakeApi(green_routes(**{pr_runs_path(HEAD): runs(bare)}))
    merge_tree, cands, last = pt.gather(api, SHA)
    assert pt.decide(merge_tree, cands, last).skip is False


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
    rc = pt.main(["--sha", SHA], api=FakeApi(green_routes()), env=gh_env)
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
    assert pt.main(["--sha", SHA], api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "error: %s" % type(exc).__name__ in _summary(gh_env)


def test_an_error_late_in_gathering_still_means_a_full_run(gh_env):
    # The PR was proven; the nightly lookup then fails. Nothing partial counts.
    api = FakeApi(green_routes(**{DISPATCH: urllib.error.URLError("boom")}))
    assert pt.main(["--sha", SHA], api=api, env=gh_env) == 0
    assert _outputs(gh_env)["skip"] == "false"


def test_the_error_reason_is_exactly_error_and_the_type(gh_env):
    api = FakeApi(green_routes(**{"git/commits/%s" % SHA:
                                  urllib.error.HTTPError("u", 403, "x", None, None)}))
    pt.main(["--sha", SHA], api=api, env=gh_env)
    assert "reason: error: HTTPError\n" in _summary(gh_env)


def test_an_unproven_push_writes_skip_false_with_its_reason(gh_env):
    api = FakeApi(green_routes(**{"commits/%s/pulls" % SHA: []}))
    assert pt.main(["--sha", SHA], api=api, env=gh_env) == 0
    assert _outputs(gh_env) == {"skip": "false", "pr_run_id": ""}
    assert "no pull request" in _summary(gh_env)


def test_main_appends_to_the_output_file_instead_of_replacing_it(gh_env):
    Path(gh_env["GITHUB_OUTPUT"]).write_text("earlier=step\n", encoding="utf-8")
    pt.main(["--sha", SHA], api=FakeApi(green_routes()), env=gh_env)
    text = Path(gh_env["GITHUB_OUTPUT"]).read_text(encoding="utf-8")
    assert text.startswith("earlier=step\n")
    assert text.endswith("skip=true\npr_run_id=7\n")


def test_api_sourced_text_cannot_add_lines_to_the_outputs_the_log_or_the_summary(
        gh_env, capsys):
    hostile = "failure\nskip=true\n::error::injected\n## pwned\r\n more"
    api = FakeApi(green_routes(**{SCHEDULE: runs(run(1, event="schedule",
                                                     conclusion=hostile))}))
    assert pt.main(["--sha", SHA], api=api, env=gh_env) == 0
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
    assert pt.main(["--sha", SHA], api=FakeApi(green_routes()), env=env) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "skip=true" in lines and "pr_run_id=7" in lines


def test_an_unwritable_output_path_still_exits_zero(tmp_path, capsys):
    env = {"GITHUB_OUTPUT": str(tmp_path), "GITHUB_STEP_SUMMARY": str(tmp_path)}  # dirs
    assert pt.main(["--sha", SHA], api=FakeApi(green_routes()), env=env) == 0
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
    assert pt.main(["--sha", SHA], env=env) == 0
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
    assert pt.main(["--sha", SHA], env=env) == 0
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
    pt.main(["--sha", SHA], env=env)
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
