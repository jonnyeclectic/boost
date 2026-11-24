#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Mutation-strength gate: fail unless >= MIN_SCORE% of mutants are killed.

Usage:  python3 scripts/mutation_gate.py [--run] [--min 80] [--plan PLAN]

  --run   run `mutmut run` first (otherwise gate the existing results)
  --plan  the run's plan; when its full set carries ledgered survivors, check
          every carried row first and say where they came from

Score = killed / (total - skipped). "no tests" mutants count against the
score — untested code is unkilled mutants by definition.

A ledgered plan (docs/superpowers/specs/2026-11-24-mutation-survivor-ledger.md)
names survivors this run did not re-run; `mutation_shards.py merge --plan`
merged each in as ``CARRIED_EXIT``. Carrying a row never adds a kill: it is
scored as "survived", so it adds nothing to killed and one to the denominator.
The gate re-reads every carried row and exits 2 unless each is exactly
``CARRIED_EXIT`` and the installed mutmut reads that code as "survived". It
does not claim more than that: the rows that were run were measured under this
run's own selectors, so this score is not a bound on what a plain run of the
same commit would measure.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MUTMUT = ROOT / ".venv" / "bin" / "mutmut"
STATS_NAME = "mutmut-cicd-stats.json"
STATS = ROOT / "mutants" / STATS_NAME
SOURCE = Path("boost_cli/core")

#: The ways back to a plain run, printed under a ledgered FAIL. Each one runs
#: the plain full gate exactly as it ran before the ledger existed.
ESCAPES = (
    "on a pull request: add the label `mutation-no-ledger` and push a commit "
    "(attempt 1 of the new head plans plain)",
    "\"Re-run all jobs\": an attempt after the first never uses a ledger",
    "the owner: remove this event from the repository variable `MUTATION_LEDGER`",
)

_SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_WHEN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_WORD = re.compile(r"[a-z_]{1,32}")


def _carried_exit() -> int:
    """``CARRIED_EXIT``, from the module that merges with it, so there is one spelling."""
    spec = importlib.util.spec_from_file_location(
        "mutation_shards", Path(__file__).resolve().parent / "mutation_shards.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load mutation_shards.py beside %s" % __file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CARRIED_EXIT


def sh(*args: str) -> int:
    return subprocess.call(args, cwd=ROOT)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _status_of(code: int) -> str:
    """mutmut's own name for ``code``, without growing its defaultdict."""
    from mutmut.stats import status_by_exit_code

    if code in status_by_exit_code:
        return status_by_exit_code[code]
    factory = status_by_exit_code.default_factory
    return factory() if factory is not None else "suspicious"


def ledger_of(plan: Any) -> tuple[list[str], dict[str, Any]] | None:
    """The full set's carried names and its ``ledger`` provenance, or None when plain.

    Raises ValueError for a full set whose ``carried`` is not a non-empty list
    of strings: the merge refuses that plan too, so reaching here with one is
    a contradiction worth exit 2.
    """
    full = ((plan.get("sets") or {}).get("full") if isinstance(plan, dict) else None)
    if not isinstance(full, dict) or "carried" not in full:
        return None
    carried = full["carried"]
    if not isinstance(carried, list) or not carried or not all(
            isinstance(n, str) and n for n in carried):
        raise ValueError("`sets.full.carried` is not a non-empty list of names")
    ledger = full.get("ledger")
    return carried, ledger if isinstance(ledger, dict) else {}


def merged_codes(mutants: Path) -> dict[str, Any]:
    """Every key of every merged ``.meta`` under ``mutants``, with its code."""
    codes: dict[str, Any] = {}
    for meta in sorted((mutants / SOURCE).rglob("*.py.meta")):
        data = json.loads(meta.read_text(encoding="utf-8"))
        codes.update(data.get("exit_code_by_key") or {})
    return codes


def check_carried(carried: list[str], codes: dict[str, Any], carried_exit: int,
                  status_of=None) -> list[str]:
    """Why the carried rows cannot be trusted as merged, or [] when they can (I1, I4)."""
    problems: list[str] = []
    try:
        meaning = (status_of or _status_of)(carried_exit)
    except ImportError:
        return ["mutmut is not importable, so what exit code %d means cannot be checked"
                % carried_exit]
    if meaning != "survived":
        problems.append("the installed mutmut reads exit code %d as %r, not 'survived'"
                        % (carried_exit, meaning))
    absent = [n for n in carried if n not in codes]
    wrong = [n for n in carried if n in codes and codes[n] != carried_exit]
    if absent:
        problems.append("%d carried rows are missing from the merged results, first: %s"
                        % (len(absent), absent[0]))
    if wrong:
        problems.append("%d carried rows are not exactly %d, first: %s = %r"
                        % (len(wrong), carried_exit, wrong[0], codes[wrong[0]]))
    return problems


def provenance(carried: list[str], ledger: dict[str, Any], total: int) -> str:
    """One line: how many rows were carried, and from which whole-codebase run.

    Built only from integers and from strings that match a commit, a UTC time
    or an event word, so nothing the plan holds can start a workflow command.
    """
    run = _int(ledger.get("run_id"))
    event = ledger.get("event")
    when = ledger.get("created_at")
    head = ledger.get("head_sha")
    age = ledger.get("age_hours")
    survived = _int(ledger.get("carried_survived"))
    timeouts = _int(ledger.get("carried_timeouts"))
    split = (" (%d survived and %d timeout on record)" % (survived, timeouts)
             if survived is not None and timeouts is not None else "")
    source = "whole-codebase run %s (%s, %s, %s old, commit %s)" % (
        run if run is not None else "?",
        event if isinstance(event, str) and _WORD.fullmatch(event) else "?",
        when if isinstance(when, str) and _WHEN.fullmatch(when) else "?",
        "%.0f h" % age if isinstance(age, (int, float)) and not isinstance(age, bool)
        and 0 <= age < 10_000 else "? h",
        head[:12] if isinstance(head, str) and _SHA.fullmatch(head) else "?")
    return ("mutation gate: ledgered — %d of %d mutants carried as survived%s from %s; "
            "not re-run on this commit" % (len(carried), total, split, source))


def _summary(lines: list[str]) -> None:
    """A ledgered run's gate lines, in the job summary; a plain run writes none, as before."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as out:
        for line in lines:
            out.write("- %s\n" % line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="run mutmut first")
    ap.add_argument("--min", type=float, default=80.0, help="minimum kill %%")
    ap.add_argument("--plan", help="the run's plan (checks and reports carried survivors)")
    ap.add_argument("--mutants", default=str(STATS.parent),
                    help="the merged mutants/ tree (default: this checkout's)")
    args = ap.parse_args(argv)
    mutants = Path(args.mutants)
    stats = mutants / STATS_NAME

    ledgered: tuple[list[str], dict[str, Any]] | None = None
    if args.plan:
        try:
            ledgered = ledger_of(json.loads(Path(args.plan).read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            print("mutation gate: cannot read the plan %s (%s)" % (args.plan, exc))
            return 2

    mutmut = str(MUTMUT if MUTMUT.exists() else shutil.which("mutmut") or "mutmut")
    if args.run:
        rc = sh(mutmut, "run")
        if rc not in (0, 2):  # mutmut exits nonzero when mutants survive
            print("mutation gate: `mutmut run` failed to execute (rc %d)" % rc)
            return 2

    lines: list[str] = []
    if ledgered is not None:
        carried, ledger = ledgered
        try:
            codes = merged_codes(mutants)
        except (OSError, ValueError) as exc:
            print("mutation gate: cannot read the merged results (%s)" % exc)
            return 2
        problems = check_carried(carried, codes, _carried_exit())
        if problems:
            print("mutation gate: the carried survivors were not merged as planned:")
            for p in problems:
                print("  - %s" % p)
            return 2
        lines.append(provenance(carried, ledger, len(codes)))
        print(lines[-1])

    if sh(mutmut, "export-cicd-stats") != 0 or not stats.exists():
        print("mutation gate: no mutation results — run `make mutation`")
        return 2

    s = json.loads(stats.read_text(encoding="utf-8"))
    denominator = s["total"] - s.get("skipped", 0)
    score = 100.0 * s["killed"] / denominator if denominator else 0.0
    lines.append("mutation gate: %d/%d killed (%.1f%%) — survived %d, no-tests %d, "
                 "timeout %d, suspicious %d"
                 % (s["killed"], denominator, score, s.get("survived", 0),
                    s.get("no_tests", 0), s.get("timeout", 0), s.get("suspicious", 0)))
    print(lines[-1])
    if score < args.min:
        lines.append("mutation gate: FAIL — %.1f%% < %.1f%% minimum" % (score, args.min))
        print(lines[-1])
        if ledgered is not None:
            carried = ledgered[0]
            top = 100.0 * (s["killed"] + len(carried)) / denominator if denominator else 0.0
            more = [
                "mutation gate: this FAIL is ledgered: %d carried survivors were not "
                "re-run, so a test that now kills one gets no credit here. Even if "
                "every one were killed, this run's other verdicts would score %.1f%% "
                "— arithmetic over this run, not a forecast of a plain run, whose "
                "other verdicts are measured under its own selectors."
                % (len(carried), top),
                "mutation gate: for a plain run of the same gate:",
                *("  - %s" % e for e in ESCAPES),
            ]
            for line in more:
                print(line)
            lines.extend(more)
            _summary(lines)
        return 1
    lines.append("mutation gate: PASS (>= %.1f%%)" % args.min)
    print(lines[-1])
    if ledgered is not None:
        _summary(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
