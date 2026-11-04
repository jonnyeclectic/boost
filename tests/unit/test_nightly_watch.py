# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: scripts/nightly_watch.py and the workflow that runs it.

ci.yml's nightly whole-codebase mutation run is the only run that scores all of
``boost_cli/core``. A red one opens a tracker (ci-failure-issue.yml watches
``ci``); a missing one alarmed nobody, and ci_proven_tree.py turned the
proven-tree skip off after 48 h without saying so. nightly-watch.yml fails
when the newest such run is older than 36 h, and ci-failure-issue.yml watches
nightly-watch, so the absence now opens a tracker too.

The fake GitHub below applies the query's filters (event, branch, status) the
way the real one does, so "a newer push run does not count" is a claim about
what the script asks for, not about what a canned response happens to hold.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "nightly_watch.py"
WORKFLOWS = ROOT / ".github" / "workflows"
WATCH_YML = WORKFLOWS / "nightly-watch.yml"
ALERT_YML = WORKFLOWS / "ci-failure-issue.yml"
CI_YML = WORKFLOWS / "ci.yml"


def _load():
    spec = importlib.util.spec_from_file_location("nightly_watch_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


nw = _load()
pt = nw.pt

NOW = datetime(2026, 11, 3, 20, 0, tzinfo=UTC)
RUNS_PATH = "actions/workflows/ci.yml/runs"


def iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(ident: int, event: str, age: timedelta | None, *, conclusion: str | None = "success",
        branch: str = "main", status: str = "completed", workflow: str = "ci.yml",
        created_at: str | None = None) -> dict:
    out = {"id": ident, "event": event, "head_branch": branch, "status": status,
           "conclusion": conclusion, "path": ".github/workflows/" + workflow}
    if created_at is not None:
        out["created_at"] = created_at
    elif age is not None:
        out["created_at"] = iso(NOW - age)
    return out


class FakeGitHub:
    """Answers list-runs queries for ci.yml by filtering ``runs`` like GitHub does."""

    def __init__(self, *runs: dict):
        self.runs = list(runs)
        self.paths: list[str] = []

    def __call__(self, path: str):
        self.paths.append(path)
        url = urlsplit(path)
        assert url.path == RUNS_PATH, "unexpected request %r" % path
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        found = [r for r in self.runs
                 if r["path"].endswith("/ci.yml")
                 and ("event" not in query or r["event"] == query["event"])
                 and ("branch" not in query or r["head_branch"] == query["branch"])
                 and ("status" not in query or r["status"] == query["status"])]
        found.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return {"total_count": len(found),
                "workflow_runs": found[:int(query.get("per_page", 30))]}


def watch(api, capsys, *, env=None, now=NOW):
    code = nw.main(api=api, env={} if env is None else env, now=now)
    return code, capsys.readouterr().out


class TestTheVerdict:
    def test_a_recent_nightly_passes_and_names_the_run(self, capsys):
        code, out = watch(FakeGitHub(run(41168736566, "schedule", timedelta(hours=10))), capsys)
        assert code == 0
        assert out == ("nightly_watch: ok -- run 41168736566 (schedule, concluded "
                       "success) was created 10h ago (limit 36h)\n")

    def test_an_overdue_nightly_fails_with_an_error_annotation(self, capsys):
        code, out = watch(FakeGitHub(run(7, "schedule", timedelta(hours=50))), capsys)
        assert code == 1
        assert out == ("::error::nightly_watch: run 7 (schedule, concluded success) "
                       "was created 50h ago, more than 36h: ci's nightly "
                       "whole-codebase mutation run is overdue\n")

    def test_exactly_36_hours_is_still_fresh(self, capsys):
        code, out = watch(FakeGitHub(run(7, "schedule", timedelta(hours=36))), capsys)
        assert code == 0, out

    def test_one_second_past_36_hours_fails_and_reads_past_the_limit(self, capsys):
        # Rounded UP (ci_proven_tree._hours): 36 h 1 s must not print a
        # fresh-looking "36h" next to a failure.
        code, out = watch(FakeGitHub(run(7, "schedule", timedelta(hours=36, seconds=1))), capsys)
        assert code == 1
        assert "created 36.1h ago, more than 36h" in out

    def test_no_whole_codebase_run_at_all_fails(self, capsys):
        code, out = watch(FakeGitHub(), capsys)
        assert code == 1
        assert out == ("::error::nightly_watch: no completed schedule or "
                       "workflow_dispatch run of ci.yml exists on main\n")

    def test_a_red_nightly_is_not_this_alarms_business(self, capsys):
        # A failed nightly already opens ci's own tracker; this one is about
        # whether the run happens, so a recent red run passes here.
        code, out = watch(FakeGitHub(run(9, "schedule", timedelta(hours=2),
                                         conclusion="failure")), capsys)
        assert code == 0
        assert "(schedule, concluded failure)" in out

    def test_a_cancelled_nightly_also_counts_as_having_run(self, capsys):
        code, out = watch(FakeGitHub(run(9, "schedule", timedelta(hours=2),
                                         conclusion="cancelled")), capsys)
        assert code == 0
        assert "concluded cancelled" in out


class TestWhichRunsCount:
    def test_a_dispatch_counts_as_a_whole_codebase_run(self, capsys):
        code, out = watch(FakeGitHub(run(1, "schedule", timedelta(hours=60)),
                                     run(2, "workflow_dispatch", timedelta(hours=3))), capsys)
        assert code == 0
        assert "run 2 (workflow_dispatch, concluded success) was created 3h ago" in out

    def test_the_newer_of_the_two_events_is_judged_either_way(self, capsys):
        code, out = watch(FakeGitHub(run(1, "schedule", timedelta(hours=3)),
                                     run(2, "workflow_dispatch", timedelta(hours=60))), capsys)
        assert code == 0
        assert "run 1 (schedule," in out

    def test_newer_push_and_pull_request_runs_do_not_count(self, capsys):
        api = FakeGitHub(run(1, "schedule", timedelta(hours=40)),
                         run(2, "push", timedelta(minutes=5)),
                         run(3, "pull_request", timedelta(minutes=1)),
                         run(4, "merge_group", timedelta(minutes=2)))
        code, out = watch(api, capsys)
        assert code == 1
        assert "run 1 (schedule" in out and "40h ago" in out
        # ...because it never asks for them.
        events = sorted(parse_qs(urlsplit(p).query)["event"][0] for p in api.paths)
        assert events == ["schedule", "workflow_dispatch"]

    def test_a_dispatch_on_another_branch_does_not_count(self, capsys):
        code, out = watch(FakeGitHub(run(1, "schedule", timedelta(hours=40)),
                                     run(2, "workflow_dispatch", timedelta(hours=1),
                                         branch="feature")), capsys)
        assert code == 1
        assert "run 1 (schedule" in out

    def test_a_run_still_in_progress_does_not_count(self, capsys):
        # ci_proven_tree reads completed runs only, and this alarm is the early
        # warning for that script's skip, so it reads the same set.
        code, out = watch(FakeGitHub(run(1, "schedule", timedelta(hours=40)),
                                     run(2, "schedule", timedelta(hours=1),
                                         status="in_progress", conclusion=None)), capsys)
        assert code == 1
        assert "run 1 (schedule" in out

    @pytest.mark.parametrize("fake", [
        lambda: FakeGitHub(),
        lambda: FakeGitHub(run(1, "schedule", timedelta(hours=3), conclusion="failure"),
                           run(2, "workflow_dispatch", timedelta(hours=50))),
    ], ids=["no-runs", "runs"])
    def test_it_asks_exactly_what_ci_proven_tree_asks(self, fake):
        # Same definition of "whole-codebase run", by construction: the watch
        # goes through ci_proven_tree._newest_completed_whole -- the one helper
        # for "the newest completed whole-codebase run", which _last_whole
        # starts from -- so the requests are equal.
        ours, theirs, last = fake(), fake(), fake()
        nw.main(api=ours, env={}, now=NOW)
        pt._newest_completed_whole(theirs)
        assert ours.paths == theirs.paths
        assert len(ours.paths) == 2

        # _last_whole begins with the same two. With no run it stops there;
        # with one it goes on to that run's jobs (its `mutation` verdict),
        # which the watch never asks and FakeGitHub refuses.
        if pt._newest_completed_whole(fake()) is not None:
            with pytest.raises(AssertionError, match="unexpected request"):
                pt._last_whole(last)
            assert last.paths[:2] == ours.paths
            assert urlsplit(last.paths[2]).path.endswith("/jobs")
        else:
            assert pt._last_whole(last) is None
            assert last.paths == ours.paths

    def test_an_idle_nightly_counts_as_the_cron_having_fired(self, capsys):
        # A skip is a completed schedule run; the watch never asks what it
        # was. FakeGitHub refuses every path but the runs listing, so an
        # artifact or window request would fail this test loudly.
        api = FakeGitHub(run(41682296301, "schedule", timedelta(hours=12)),
                         run(41512174636, "schedule", timedelta(hours=34)))
        code, out = watch(api, capsys)
        assert code == 0, out
        assert "run 41682296301 (schedule, concluded success)" in out
        assert len(api.paths) == 2

    def test_a_missing_nightly_still_alarms_whatever_skipped_before_it(self, capsys):
        # The newest run being a skip 37 h ago is no excuse: no run since
        # means the cron did not fire, and an idle night still makes a run.
        api = FakeGitHub(run(9, "schedule", timedelta(hours=37)))
        code, out = watch(api, capsys)
        assert code == 1
        assert "overdue" in out

    def test_it_never_asks_for_the_runs_jobs(self, capsys):
        # ci_proven_tree reads the newest run's `mutation` job; the age alarm
        # judges only that a run happened, so a run whose `mutation` is red
        # (or whose jobs cannot be listed) is still a run that happened.
        api = FakeGitHub(run(9, "schedule", timedelta(hours=2), conclusion="failure"))
        code, out = watch(api, capsys)
        assert code == 0, out
        assert "(schedule, concluded failure)" in out
        assert all(urlsplit(p).path == RUNS_PATH for p in api.paths)


class TestAnAlarmThatCannotLookIsLoud:
    @pytest.mark.parametrize("exc", [
        urllib.error.HTTPError(
            "https://api.github.com/x", 403, "rate limit exceeded", None, None),
        urllib.error.URLError("no route"),
        TimeoutError("timed out"),
    ], ids=["http-403", "url-error", "timeout"])
    def test_a_transport_error_fails(self, capsys, exc):
        def api(path):
            raise exc
        code, out = watch(api, capsys)
        assert code == 1
        assert out.startswith("::error::nightly_watch could not check ci's "
                              "whole-codebase run, so it cannot say the nightly "
                              "is running -- %s: " % type(exc).__name__)

    def test_any_other_error_still_says_it_could_not_check(self, capsys):
        # Not only OSError/ValueError: an IncompleteRead or a bug must still
        # leave the ::error:: line, not a bare traceback.
        def api(path):
            raise RuntimeError("boom")
        code, out = watch(api, capsys)
        assert code == 1
        assert out.startswith("::error::nightly_watch could not check") and "RuntimeError" in out

    def test_a_body_of_the_wrong_shape_fails_rather_than_reading_as_none(self, capsys):
        # "No runs" passes through to a failure too, but for the wrong reason;
        # the message must say the check could not be made.
        code, out = watch(lambda path: {"message": "Bad credentials"}, capsys)
        assert code == 1
        assert "could not check" in out and "no workflow_runs list" in out

    def test_a_server_that_ignores_the_event_filter_is_refused(self, capsys):
        # A fresh push run answering the schedule query must not read as a
        # nightly: ci_proven_tree raises on the contradiction, and so this fails.
        code, out = watch(lambda path: {"workflow_runs": [run(5, "push", timedelta(0))]}, capsys)
        assert code == 1
        assert "could not check" in out and "ValueError" in out

    def test_an_unparseable_created_at_fails(self, capsys):
        code, out = watch(FakeGitHub(run(7, "schedule", None, created_at="yesterday")), capsys)
        assert code == 1
        assert "run 7 (schedule, concluded success): created_at is missing or " \
               "unparseable, so its age is unknown" in out

    def test_a_created_at_without_a_timezone_fails(self, capsys):
        code, out = watch(FakeGitHub(run(7, "schedule", None,
                                         created_at="2026-11-03T10:00:00")), capsys)
        assert code == 1
        assert "age is unknown" in out

    def test_a_created_at_well_in_the_future_fails(self, capsys):
        code, out = watch(FakeGitHub(run(7, "schedule", -timedelta(hours=2))), capsys)
        assert code == 1
        assert "created_at is 2h ahead of this clock" in out

    def test_clock_skew_inside_the_tolerance_passes(self, capsys):
        code, out = watch(FakeGitHub(run(7, "schedule", -timedelta(minutes=4))), capsys)
        assert code == 0
        assert "created 0h ago" in out

    def test_skew_of_exactly_the_tolerance_passes(self, capsys):
        # "More than" CLOCK_SKEW ahead fails, as in ci_proven_tree._age_problem.
        code, out = watch(FakeGitHub(run(7, "schedule", -pt.CLOCK_SKEW)), capsys)
        assert code == 0, out
        assert "was created 0h ago (limit 36h)" in out

    def test_skew_just_past_the_tolerance_fails(self, capsys):
        late = -(pt.CLOCK_SKEW + timedelta(seconds=1))
        code, out = watch(FakeGitHub(run(7, "schedule", late)), capsys)
        assert code == 1
        assert "ahead of this clock" in out


class TestTheCli:
    def test_a_missing_token_fails_before_any_request(self, capsys):
        code, out = watch(None, capsys, env={"GITHUB_REPOSITORY": "o/r"})
        assert code == 1
        assert out.endswith("-- ValueError: GITHUB_TOKEN is not set\n")

    @pytest.mark.parametrize("repo", ["", "../x", "o/..", "no-slash"])
    def test_a_malformed_repository_fails(self, capsys, repo):
        code, out = watch(None, capsys, env={"GITHUB_TOKEN": "ghs_x1",
                                             "GITHUB_REPOSITORY": repo})
        assert code == 1
        assert out.endswith("GITHUB_REPOSITORY is unset or malformed\n")

    def test_the_real_api_is_built_from_the_environment(self, capsys, monkeypatch):
        made = []
        fake = FakeGitHub(run(7, "schedule", timedelta(hours=1)))

        def make_api(repo, token):
            made.append((repo, token))
            return fake
        monkeypatch.setattr(pt, "make_api", make_api)
        code, _ = watch(None, capsys, env={"GITHUB_TOKEN": " tok ",
                                           "GITHUB_REPOSITORY": " owner/repo "})
        assert code == 0
        assert made == [("owner/repo", "tok")]
        assert len(fake.paths) == 2

    def test_the_token_never_reaches_the_log(self, capsys):
        def api(path):
            raise ValueError("refused for s3cr3t-token")
        code, out = watch(api, capsys, env={"GITHUB_TOKEN": "s3cr3t-token"})
        assert code == 1
        assert "s3cr3t-token" not in out
        assert "refused for ***" in out

    def test_api_text_cannot_start_a_second_workflow_command(self, capsys):
        def api(path):
            raise ValueError("bad\n::warning::injected\r\nmore")
        code, out = watch(api, capsys)
        assert code == 1
        # A workflow command is only parsed at the start of a line, so the
        # API's text must not be able to begin one: it is flattened into this
        # line instead.
        assert out.count("\n") == 1 and out.startswith("::error::")
        assert out.endswith("-- ValueError: bad ::warning::injected more\n")

    @pytest.mark.parametrize("hours, code, start", [
        (2, 0, "nightly_watch: ok -- "),
        (50, 1, "::error::nightly_watch: "),
    ], ids=["fresh", "overdue"])
    def test_a_conclusion_cannot_start_a_second_workflow_command(
            self, capsys, hours, code, start):
        # The verdict line carries the run's `conclusion`, which ci_proven_tree
        # passes through as any non-empty string, so it is flattened as well.
        api = FakeGitHub(run(7, "schedule", timedelta(hours=hours),
                             conclusion="failure\n::warning::injected\r\nx"))
        got, out = watch(api, capsys)
        assert got == code
        assert out.count("\n") == 1 and out.startswith(start), out
        assert "(schedule, concluded failure ::warning::injected x)" in out

    def test_the_default_clock_is_the_real_one(self, capsys):
        recent = datetime.now(UTC) - timedelta(hours=1)
        api = FakeGitHub(run(7, "schedule", None, created_at=iso(recent)))
        assert nw.main(api=api, env={}) == 0
        # The timestamp is truncated to the second, so the age is 1 h plus a
        # fraction, which rounds up to the next tenth.
        assert re.search(r"was created 1(\.1)?h ago", capsys.readouterr().out)

    def test_the_default_clock_fails_a_stale_run(self, capsys):
        stale = datetime.now(UTC) - timedelta(hours=40)
        api = FakeGitHub(run(7, "schedule", None, created_at=iso(stale)))
        assert nw.main(api=api, env={}) == 1

    def test_run_as_a_script_it_finds_ci_proven_tree_beside_it(self, tmp_path):
        # CI runs `python3 scripts/nightly_watch.py` from the repo root; the
        # sibling import must work there, and with no token it must fail loud
        # without touching the network.
        env = {k: v for k, v in os.environ.items()
               if k not in ("GITHUB_TOKEN", "GITHUB_REPOSITORY")}
        done = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=60, check=False)
        assert done.returncode == 1, done.stderr
        assert done.stdout.startswith("::error::nightly_watch could not check")
        assert "GITHUB_TOKEN is not set" in done.stdout


class TestTheThreshold:
    def test_it_is_36_hours(self):
        assert nw.MAX_AGE / timedelta(hours=1) == 36

    def test_it_fires_before_the_proven_tree_skip_turns_off(self):
        assert nw.MAX_AGE < pt.MAX_NIGHTLY_AGE


# --------------------------------------------------------------------------
# the workflows
# --------------------------------------------------------------------------

def _yaml(path: Path) -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _on(workflow: dict) -> dict:
    # PyYAML (YAML 1.1) reads a bare `on:` key as the boolean True.
    return workflow.get("on", workflow.get(True)) or {}


def _cron_hours(cron: str) -> list[int]:
    minute, hour, dom, month, dow = cron.split()
    assert re.fullmatch(r"\d+", minute) and (dom, month, dow) == ("*", "*", "*"), cron
    return sorted(int(h) for h in hour.split(","))


def _widest_gap(hours: list[int]) -> int:
    """The longest interval, in hours, between consecutive daily firings."""
    return max((hours[(i + 1) % len(hours)] - h) % 24 or 24 for i, h in enumerate(hours))


# Keyed on ci.yml, never on nightly-watch.yml: a skip conditioned on the file
# under test turns deleting the alarm into a skip, not a failure. With ci.yml
# present, a missing nightly-watch.yml makes every test below raise.
@pytest.mark.skipif(not CI_YML.exists(),
                    reason=".github/workflows not reachable (e.g. mutation sandbox)")
class TestTheWorkflow:
    def test_the_name_is_the_one_ci_failure_issue_matches(self):
        assert _yaml(WATCH_YML)["name"] == "nightly-watch"

    def test_it_runs_on_a_schedule_and_by_hand(self):
        on = _on(_yaml(WATCH_YML))
        assert set(on) == {"schedule", "workflow_dispatch"}
        assert len(on["schedule"]) == 1

    def test_the_schedule_is_off_the_hour(self):
        cron = _on(_yaml(WATCH_YML))["schedule"][0]["cron"]
        assert cron.split()[0] not in ("0", "00"), cron

    def test_threshold_plus_the_watch_interval_is_within_the_skip_window(self):
        # An overdue nightly crosses 36 h at most one watch interval before
        # the next watch looks; that must still be inside ci_proven_tree's 48 h.
        gap = _widest_gap(_cron_hours(_on(_yaml(WATCH_YML))["schedule"][0]["cron"]))
        assert gap == 12
        assert nw.MAX_AGE + timedelta(hours=gap) <= pt.MAX_NIGHTLY_AGE

    def test_the_gap_helper(self):
        assert _widest_gap([2, 14]) == 12
        assert _widest_gap([9]) == 24
        assert _widest_gap([1, 2]) == 23

    def test_one_job_runs_the_script_with_the_token_from_env(self):
        jobs = _yaml(WATCH_YML)["jobs"]
        assert list(jobs) == ["nightly-age"]
        steps = jobs["nightly-age"]["steps"]
        runs = [s for s in steps if "run" in s]
        assert [s["run"].strip() for s in runs] == ["python3 scripts/nightly_watch.py"]
        assert runs[0]["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
        for step in steps:
            assert "${{" not in step.get("run", ""), step

    def test_nothing_can_turn_the_scripts_exit_1_into_a_green_run(self):
        # ci-failure-issue reads only the run's conclusion. `continue-on-error`
        # on the job or a step concludes a failed check `success`; an `if:`
        # that excludes `schedule` concludes it `skipped`. Both are in its
        # green set, so either one line would silence the alarm.
        wf = _yaml(WATCH_YML)
        job = wf["jobs"]["nightly-age"]
        for where, block in [("job", job), *(("step %d" % i, s)
                                             for i, s in enumerate(job["steps"]))]:
            assert "continue-on-error" not in block, where
            assert "if" not in block, where
        # ...and the keys allowed at all, which also rules out the variants
        # nobody listed: a step `shell:`, a job `strategy:` or `needs:`, a
        # workflow-level `defaults:`.
        top = {("on" if key is True else key) for key in wf}
        assert top == {"name", "on", "permissions", "concurrency", "jobs"}
        assert set(job) <= {"name", "runs-on", "timeout-minutes", "permissions", "steps"}
        for step in job["steps"]:
            assert set(step) <= {"name", "id", "uses", "with", "env", "run"}, step

    def test_permissions_are_read_only_and_cover_the_runs_api(self):
        wf = _yaml(WATCH_YML)
        assert wf["permissions"] == {"contents": "read"}
        assert wf["jobs"]["nightly-age"]["permissions"] == {"contents": "read",
                                                           "actions": "read"}

    def test_a_watch_run_is_never_cancelled(self):
        # A cancelled run is not green to ci-failure-issue, so it would open
        # a tracker about nothing.
        concurrency = _yaml(WATCH_YML)["concurrency"]
        assert concurrency["cancel-in-progress"] is False
        # A constant group still cancels an older PENDING run when a third
        # arrives; one group per run never does.
        assert "${{ github.run_id }}" in concurrency["group"]

    def test_actions_are_pinned_as_ci_pins_them(self):
        ci_text = CI_YML.read_text(encoding="utf-8")
        steps = _yaml(WATCH_YML)["jobs"]["nightly-age"]["steps"]
        uses = [s["uses"] for s in steps if "uses" in s]
        assert [u.split("@")[0] for u in uses] == ["step-security/harden-runner",
                                                    "actions/checkout"]
        for ref in uses:
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", ref), ref
            assert ref in ci_text, "%s is not the pin ci.yml uses" % ref
        checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["persist-credentials"] is False

    def test_the_job_id_is_unique_across_every_workflow(self):
        # check_required_checks.py matches check names across workflows.
        seen = []
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            for key, job in (_yaml(path).get("jobs") or {}).items():
                seen.append(job.get("name", key) if isinstance(job, dict) else key)
        assert seen.count("nightly-age") == 1

    def test_ci_failure_issue_watches_it(self):
        listed = _on(_yaml(ALERT_YML))["workflow_run"]["workflows"]
        assert "nightly-watch" in listed
        assert listed == sorted(listed)

    def test_ci_failure_issue_guards_admit_a_scheduled_watch_run(self):
        # Its jobs fire on head_branch == main, event != pull_request and a
        # same-repository head: a schedule run on main satisfies all three.
        jobs = _yaml(ALERT_YML)["jobs"]
        for name in ("open-issue", "close-issue"):
            cond = " ".join(jobs[name]["if"].split())
            assert "github.event.workflow_run.head_branch == 'main'" in cond
            assert "github.event.workflow_run.event != 'pull_request'" in cond
            assert "event == 'push'" not in cond
