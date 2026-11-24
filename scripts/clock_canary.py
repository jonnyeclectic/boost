#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Run the suite on a clock moved forward, so a date time-bomb fails before it goes off.

From 2026-11-13 to 11-23 ci's nightly failed at ``collect mutmut stats once``
every night. The cause was one unit test,
``test_ci_proven_tree.py::test_the_clock_defaults_to_the_real_one_on_the_command_line``,
which aged a PR run stamped with a fixed 2026-10-30 against ``datetime.now()``
and a 13-day proof window. Nothing in the code changed; the calendar did. A red
nightly also switches off main's proven-tree skip, so for eleven days every
push ran the whole ~2.5 h mutation gate. Making mutmut's stats pass tolerate a
failing test would only score a red tree, so the fix belongs earlier: run the
suite as it will run on a later date, and say so today.

How: ``tests/clock_canary/sitecustomize.py`` shifts
``datetime.datetime.now/today/utcnow`` and ``datetime.date.today`` forward by
``BOOST_CLOCK_CANARY_DAYS`` (that file says what it leaves alone, and why).
This script puts that directory first on ``PYTHONPATH`` for one pytest run and
for nothing else, so a plain run never loads it. Every Python subprocess the
suite starts, xdist workers included, inherits the variable and the shift.

Verdicts, for each test that fails on the moved clock. The failures are re-run
together, apart from the rest of the suite, once moved and once on today's
clock:

* **bomb** -- fails again moved and passes on today's clock. Its annotation
  names the offset and the date by which it goes red for real. Exit 1. A test
  that compares ``datetime.now()`` with a clock the shim leaves alone gets this
  verdict too, and the annotation names that case as the other cause:
  ``test_logs.py``'s JSON-stamp test did, until it compared ``time.time()``.
* **red regardless** -- fails on today's clock too, so this run cannot say
  whether the clock is involved. A warning.
* **flaky** -- passes when re-run moved. A warning. A failure that needs the
  rest of the suite's company to happen lands here too, bomb or not, and the
  warning says so rather than calling it harmless.

Exit 2 when the canary cannot answer: the shim did not take (a green run on an
unmoved clock would prove nothing, so this is checked before the suite runs
and again inside it), or pytest stopped without naming a failed test.

``DEFAULT_DAYS`` is 14 because the longest proof window in
``scripts/ci_proven_tree.py`` is ``MAX_PR_RUN_AGE``, 13 days. A test that ages
a fixture dated "now" against any of those windows therefore fails here the
first night it is on main rather than some nights later, and a cron that runs
daily probes every future date 14 days before it arrives.

CLI::

    python3 scripts/clock_canary.py [--days N] [-- PYTEST_ARGS...]

``PYTEST_ARGS`` default to ``tests/unit tests/functional``. Run it with the
interpreter whose environment has pytest (``.venv/bin/python``): the suite is
started as ``sys.executable -m pytest``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHIM_DIR = ROOT / "tests" / "clock_canary"
DAYS_ENV = "BOOST_CLOCK_CANARY_DAYS"
REPORT_ENV = "BOOST_CLOCK_CANARY_REPORT"
SENTINEL_ENV = "BOOST_CLOCK_CANARY_SENTINEL"
PLUGIN = "clock_canary_report"
DEFAULT_DAYS = 14
DEFAULT_PYTEST_ARGS = ("tests/unit", "tests/functional")
PREFIX = "clock canary"

#: The suite's own check that the shift reached the process running the tests
#: (an xdist worker under ``-n auto``). Skipped on an unmoved clock, so a
#: failure here means "this run proves nothing", never a bomb.
SELF_TEST = "tests/unit/test_clock_canary.py::test_the_suite_runs_on_the_moved_clock"

#: Tests that cannot run on a moved clock at all, each with the reason. They are
#: deselected from the moved run only. An entry is a claim that the failure is
#: this harness's, not the test's: the shim moves Python's calendar, and some
#: clocks a test compares against are not Python's.
#: tests/unit/test_clock_canary.py fails when an entry's test no longer exists.
ARTIFACTS: dict[str, str] = {
    "tests/functional/test_cli_intelligence.py::TestImpact::test_named_in_repo_json": (
        "the install is stamped from datetime.now(), which the shim moves, and "
        "`git rev-list --since` counts commits by the dates git gave them, from "
        "a clock no Python shim reaches: on a moved clock every commit the test "
        "makes predates the install, so it counts 0 of 1"),
}

#: How far the moved clock may sit from ``days`` exactly: the probe reads both
#: clocks microseconds apart, so this only absorbs float rounding.
PROBE_TOLERANCE_S = 60.0

PROBE = (
    "import _datetime, datetime, json, sitecustomize\n"
    "print(json.dumps({'shim': sitecustomize.__file__,\n"
    "    'moved': datetime.datetime.now(datetime.timezone.utc).timestamp(),\n"
    "    'real': _datetime.datetime.now(_datetime.timezone.utc).timestamp()}))\n")

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class Outcome:
    """What one pytest run reported through the plugin."""

    rc: int
    failed: frozenset[str]
    #: The sentinel's outcomes (``passed``/``skipped``/``failed``); empty when
    #: the run did not collect it.
    sentinel: frozenset[str]


@dataclass(frozen=True)
class Verdict:
    """Every failure of the moved run, sorted into exactly one bucket."""

    bombs: tuple[str, ...]
    red: tuple[str, ...]
    flaky: tuple[str, ...]


def _with_shim_path(base: Mapping[str, str]) -> dict[str, str]:
    """``base`` with the shim's directory first on ``PYTHONPATH``, canary vars dropped."""
    env = {k: v for k, v in base.items() if k not in (DAYS_ENV, REPORT_ENV, SENTINEL_ENV)}
    rest = [p for p in base.get("PYTHONPATH", "").split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join([str(SHIM_DIR), *rest])
    return env


def moved_env(base: Mapping[str, str], days: int) -> dict[str, str]:
    """The environment of a run whose calendar is ``days`` ahead."""
    env = _with_shim_path(base)
    env[DAYS_ENV] = str(days)
    return env


def today_env(base: Mapping[str, str]) -> dict[str, str]:
    """The same environment on today's clock.

    The shim directory stays on the path, because the report plugin lives
    there; without ``BOOST_CLOCK_CANARY_DAYS`` the shim changes nothing.
    """
    return _with_shim_path(base)


def preflight(env: Mapping[str, str], days: int, *,
              run: Runner = subprocess.run) -> str | None:
    """Why a process started with ``env`` is not on the moved clock, or None.

    Both clocks are read in the child, against the C class the shim cannot
    touch (``_datetime.datetime``), so the answer does not depend on which
    clock this process is on.
    """
    proc = run([sys.executable, "-c", PROBE], env=dict(env), capture_output=True,
               text=True, timeout=60, check=False)
    if proc.returncode != 0:
        return "the probe interpreter failed (rc %d): %s" % (
            proc.returncode, (proc.stderr or proc.stdout).strip()[-400:])
    try:
        seen = json.loads(proc.stdout.strip().splitlines()[-1])
        shim = Path(seen["shim"]).resolve()
        moved_by = float(seen["moved"]) - float(seen["real"])
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        return "the probe printed something unreadable (%s): %r" % (exc, proc.stdout[-400:])
    want = (SHIM_DIR / "sitecustomize.py").resolve()
    if shim != want:
        return "sitecustomize resolved to %s, not %s, so the shim never loaded" % (shim, want)
    if abs(moved_by - days * 86400) > PROBE_TOLERANCE_S:
        return ("datetime.now() reads %.0f s ahead of the real clock, not %d days: "
                "the shim loaded but did not move the clock" % (moved_by, days))
    return None


def read_report(rc: int, text: str) -> Outcome:
    """Parse the plugin's ``<outcome>\\t<node id>`` lines."""
    failed, sentinel = set(), set()
    for line in text.splitlines():
        outcome, sep, nodeid = line.partition("\t")
        if not sep:
            continue
        if outcome == "failed":
            failed.add(nodeid)
        if nodeid == SELF_TEST:
            sentinel.add(outcome)
    return Outcome(rc, frozenset(failed), frozenset(sentinel))


def run_pytest(args: Sequence[str], env: Mapping[str, str], *,
               run: Runner = subprocess.run) -> Outcome:
    """Run pytest with the report plugin loaded, and read back what it wrote."""
    fd, name = tempfile.mkstemp(prefix="clock-canary-", suffix=".txt")
    os.close(fd)
    report = Path(name)
    try:
        proc = run([sys.executable, "-m", "pytest", "-p", PLUGIN, *args],
                   env={**env, REPORT_ENV: str(report), SENTINEL_ENV: SELF_TEST},
                   check=False)
        return read_report(proc.returncode, report.read_text(encoding="utf-8"))
    finally:
        report.unlink(missing_ok=True)


def classify(failed: Iterable[str], again: Iterable[str],
             today_failed: Iterable[str]) -> Verdict:
    """Sort the moved run's failures by what their two lone re-runs did."""
    again, today_failed = set(again), set(today_failed)
    bombs, red, flaky = [], [], []
    for nodeid in sorted(set(failed)):
        if nodeid not in again:
            flaky.append(nodeid)
        elif nodeid in today_failed:
            red.append(nodeid)
        else:
            bombs.append(nodeid)
    return Verdict(tuple(bombs), tuple(red), tuple(flaky))


def bomb_line(nodeid: str, days: int, moved_to: date) -> str:
    """The annotation for one bomb: the offset, the date, and what to do."""
    return ("::error title=%s +%dd::%s fails on a clock moved %d days ahead (to %s) "
            "and passes on today's when re-run. Either something it compares "
            "against now is fixed, and it fails on the real clock by %s at the "
            "latest: take now from the clock under test, as "
            "test_ci_proven_tree.py::test_the_clock_defaults_to_the_real_one_on_the_command_line does. "
            "Or it compares datetime's now with a clock this canary leaves alone "
            "(time.time(), file times, git's dates; tests/clock_canary/sitecustomize.py "
            "lists them): compare like with like, or add it to ARTIFACTS with the reason."
            % (PREFIX, days, nodeid, days, moved_to.isoformat(), moved_to.isoformat()))


def summary(verdict: Verdict, days: int, moved_to: date) -> str:
    """Markdown for the job summary."""
    if verdict.bombs:
        head = ("### %s: %d test(s) go red by %s (+%d days)"
                % (PREFIX, len(verdict.bombs), moved_to.isoformat(), days))
    else:
        head = ("### %s: no date bomb within %d days (clock moved to %s)"
                % (PREFIX, days, moved_to.isoformat()))
    rows = [head, ""]
    for title, ids in (("Date bombs: fail on the moved clock, pass on today's", verdict.bombs),
                       ("Red on today's clock too (the clock may not be involved)", verdict.red),
                       ("Flaky: passed when re-run on the moved clock", verdict.flaky)):
        if ids:
            rows += ["**%s**" % title, "", *("- `%s`" % i for i in ids), ""]
    return "\n".join(rows) + "\n"


def _write_summary(env: Mapping[str, str], text: str) -> None:
    path = env.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8", newline="\n") as out:
            out.write(text)


def _error(message: str) -> int:
    print("::error title=%s::%s" % (PREFIX, message))
    return 2


def parse_args(argv: Sequence[str]) -> tuple[int, list[str]]:
    """``--days N`` before ``--``; everything after it goes to pytest."""
    argv = list(argv)
    split = argv.index("--") if "--" in argv else len(argv)
    parser = argparse.ArgumentParser(prog="clock_canary.py", description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help="how far ahead to move the clock (default %d)" % DEFAULT_DAYS)
    ns = parser.parse_args(argv[:split])
    if ns.days < 1:
        parser.error("--days must be at least 1")
    return ns.days, argv[split + 1:] or list(DEFAULT_PYTEST_ARGS)


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None,
         run: Runner = subprocess.run, now: datetime | None = None) -> int:
    """0: no bomb found. 1: at least one. 2: the canary could not tell."""
    days, pytest_args = parse_args(sys.argv[1:] if argv is None else argv)
    base = os.environ if env is None else env
    moved, today = moved_env(base, days), today_env(base)
    moved_to = ((now or datetime.now(UTC)) + timedelta(days=days)).date()

    problem = preflight(moved, days, run=run)
    if problem:
        return _error("the clock was not moved, so a green suite would prove nothing: %s"
                      % problem)
    print("%s: running the suite with the clock moved +%d days, to %s"
          % (PREFIX, days, moved_to.isoformat()), flush=True)
    deselect = [arg for nodeid in sorted(ARTIFACTS) for arg in ("--deselect", nodeid)]
    first = run_pytest([*pytest_args, *deselect], moved, run=run)
    if first.sentinel - {"passed"}:
        return _error("%s did not pass (%s): the moved clock did not reach the processes "
                      "running the tests, so this run proves nothing"
                      % (SELF_TEST, ", ".join(sorted(first.sentinel))))
    if not first.sentinel:
        print("::warning title=%s::%s was not collected, so nothing checked that the test "
              "processes saw the moved clock" % (PREFIX, SELF_TEST))
    if first.rc == 0:
        _write_summary(base, summary(Verdict((), (), ()), days, moved_to))
        print("%s: green with the clock at %s (+%d days)" % (PREFIX, moved_to.isoformat(), days))
        return 0
    if first.rc not in (1, 2) or not first.failed:
        return _error("pytest exited %d on the moved clock without naming a failed test "
                      "(usage, internal or collection trouble): read the log above" % first.rc)

    ids = sorted(first.failed)
    print("%s: %d failure(s) on the moved clock; re-running them apart from the rest "
          "of the suite, moved and on today's clock" % (PREFIX, len(ids)), flush=True)
    again = run_pytest(ids, moved, run=run)
    on_today = run_pytest(ids, today, run=run)
    for label, rerun in (("the moved", again), ("today's", on_today)):
        if rerun.rc not in (0, 1):
            return _error("the re-run on %s clock exited %d, so the failures cannot be "
                          "told apart: read the log above" % (label, rerun.rc))
    verdict = classify(ids, again.failed, on_today.failed)

    for nodeid in verdict.bombs:
        print(bomb_line(nodeid, days, moved_to))
    for nodeid in verdict.red:
        print("::warning title=%s +%dd::%s fails on today's clock as well when re-run "
              "apart from the suite, so this run cannot tell whether the clock is involved" % (PREFIX, days, nodeid))
    for nodeid in verdict.flaky:
        print("::warning title=%s +%dd::%s failed on the moved clock in the full run and "
              "passed when re-run on it apart from the suite: flaky, or a failure that "
              "needs the rest of the suite -- not shown to be a date bomb, nor cleared"
              % (PREFIX, days, nodeid))
    _write_summary(base, summary(verdict, days, moved_to))
    return 1 if verdict.bombs else 0


if __name__ == "__main__":
    sys.exit(main())
