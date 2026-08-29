# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/release_preflight.py — the pre-PyPI release gate.

The script's whole reason to exist is that a release must not go out when a
sibling gate workflow is red, so the tests drive it against synthetic API
replies for every way a gate can fail to say "success": red, cancelled,
skipped, never started, still running at the deadline, and an API that will not
answer at all. A gate that can only say "yes" is the bug this file guards.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[2] / "scripts"
          / "release_preflight.py")


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("release_preflight", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(m)
    return m


def runs(*entries):
    return {"workflow_runs": list(entries)}


def done(conclusion, url="https://ci.example/1"):
    return {"status": "completed", "conclusion": conclusion, "html_url": url}


class _Clock:
    """Monotonic clock that only advances when the code under test sleeps."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def drive(mod, replies, workflows=("a.yml",), timeout=100.0, interval=10.0):
    """Run wait_for_gates against a scripted sequence of API replies.

    ``replies`` maps workflow name -> list of payloads, consumed one per poll;
    the last one repeats. Returns (exit_code, log_lines, poll_counts).
    """
    calls = dict.fromkeys(workflows, 0)
    clock = _Clock()
    lines = []

    def fetch(path):
        name = next(n for n in workflows if "/" + n + "/" in path)
        seq = replies[name]
        payload = seq[min(calls[name], len(seq) - 1)]
        calls[name] += 1
        return payload

    rc = mod.wait_for_gates(
        "owner/repo", "0123456789abcdef", list(workflows), fetch=fetch,
        sleep=clock.sleep, clock=clock, timeout=timeout, interval=interval,
        log=lines.append)
    return rc, "\n".join(lines), calls


class TestEvaluate:
    def test_completed_success_passes(self, mod):
        verdict, detail = mod.evaluate(runs(done("success", "u")))
        assert verdict == mod.PASS and detail == "u"

    @pytest.mark.parametrize("conclusion",
                             ["failure", "cancelled", "timed_out",
                              "action_required", "startup_failure", None])
    def test_every_other_conclusion_fails(self, mod, conclusion):
        verdict, detail = mod.evaluate(runs(done(conclusion)))
        assert verdict == mod.FAIL
        assert repr(conclusion) in detail

    def test_skipped_fails_and_explains_why(self, mod):
        # A path-filtered gate that skipped has vouched for nothing; reading it
        # as consent is precisely the hole this script closes.
        verdict, detail = mod.evaluate(runs(done("skipped")))
        assert verdict == mod.FAIL
        assert "cannot vouch" in detail

    def test_in_progress_is_pending_not_a_pass(self, mod):
        verdict, _ = mod.evaluate(
            runs({"status": "in_progress", "conclusion": None}))
        assert verdict == mod.PENDING

    @pytest.mark.parametrize("payload", [None, {}, {"workflow_runs": []},
                                         {"workflow_runs": "nope"},
                                         {"workflow_runs": ["str"]}, "junk"])
    def test_unusable_payloads_never_pass(self, mod, payload):
        # None is what api_get returns when the API could not be read at all.
        assert mod.evaluate(payload)[0] == mod.PENDING

    def test_newest_run_wins_over_an_older_one(self, mod):
        # GitHub returns runs newest-first; a re-run that went green must not
        # be overruled by the original red attempt further down the list.
        verdict, _ = mod.evaluate(runs(done("success"), done("failure")))
        assert verdict == mod.PASS


class TestWaitForGates:
    def test_all_green_exits_zero(self, mod):
        rc, log, _ = drive(mod, {"a.yml": [runs(done("success"))]})
        assert rc == 0
        assert "all 1 release gates green" in log

    def test_red_gate_blocks_the_release(self, mod):
        rc, log, _ = drive(mod, {"a.yml": [runs(done("failure"))]})
        assert rc == 1
        assert "refusing to release 0123456789" in log
        assert "1 of 1 release gates did not pass" in log

    def test_pending_then_green(self, mod):
        rc, log, calls = drive(mod, {"a.yml": [
            runs(), runs({"status": "queued"}), runs(done("success"))]})
        assert rc == 0 and calls["a.yml"] == 3
        assert "ok   a.yml" in log

    def test_never_started_fails_at_the_deadline(self, mod):
        # The dangerous case: no run exists for this sha, so there is nothing
        # red to see. Silence must not read as success.
        rc, log, _ = drive(mod, {"a.yml": [runs()]}, timeout=30.0, interval=10.0)
        assert rc == 1
        assert "still not conclusive after 30s" in log

    def test_unreachable_api_fails_at_the_deadline(self, mod):
        rc, log, _ = drive(mod, {"a.yml": [None]}, timeout=20.0, interval=10.0)
        assert rc == 1
        assert "cannot be assumed" in log

    def test_one_red_of_two_still_blocks(self, mod):
        rc, log, _ = drive(
            mod, {"a.yml": [runs(done("success"))],
                  "b.yml": [runs(done("failure"))]},
            workflows=("a.yml", "b.yml"))
        assert rc == 1
        assert "1 of 2 release gates did not pass" in log
        assert "b.yml" in log.split("refusing to release")[1]

    def test_a_red_gate_stops_polling_the_slow_one(self, mod):
        # No point holding the release job open for 30 minutes waiting on a
        # gate whose verdict can no longer matter.
        rc, _, calls = drive(
            mod, {"a.yml": [runs(done("failure"))], "b.yml": [runs()]},
            workflows=("a.yml", "b.yml"), timeout=1000.0)
        assert rc == 1 and calls["b.yml"] == 1

    def test_both_green_reports_both(self, mod):
        rc, log, _ = drive(
            mod, {"a.yml": [runs(done("success"))],
                  "b.yml": [runs({"status": "in_progress"}),
                            runs(done("success"))]},
            workflows=("a.yml", "b.yml"))
        assert rc == 0
        assert "all 2 release gates green" in log

    def test_head_sha_is_url_encoded_into_the_query(self, mod):
        seen = []

        def fetch(path):
            seen.append(path)
            return runs(done("success"))

        mod.wait_for_gates("owner/repo", "abc123", ["pip-audit.yml"],
                           fetch=fetch, sleep=lambda s: None,
                           clock=lambda: 0.0, log=lambda *_: None)
        assert seen == ["/repos/owner/repo/actions/workflows/pip-audit.yml"
                        "/runs?head_sha=abc123&per_page=20"]


class TestMain:
    def test_no_require_list_is_an_error_not_a_pass(self, mod, monkeypatch):
        # Exit 0 here would print nothing and read as a green gate in the
        # release log while checking exactly zero workflows.
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        assert mod.main(["--repo", "o/r", "--sha", "abc"]) == 2

    def test_missing_token_is_an_error(self, mod, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert mod.main(["--repo", "o/r", "--sha", "abc",
                         "--require", "a.yml"]) == 2

    def test_missing_repo_is_an_error(self, mod, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        assert mod.main(["--sha", "abc", "--require", "a.yml"]) == 2

    def test_repo_defaults_to_the_actions_env(self, mod, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        seen = []
        monkeypatch.setattr(mod, "api_get",
                            lambda path, token: seen.append(path)
                            or runs(done("success")))
        assert mod.main(["--sha", "abc", "--require", "a.yml"]) == 0
        assert seen and seen[0].startswith("/repos/owner/repo/")
