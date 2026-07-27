#!/usr/bin/env python3
"""Gate: the required-status-check list must match the jobs that actually run.

Branch protection is configured in the GitHub UI, so the list of required checks
existed only as prose in CONTRIBUTING.md — and it drifted. Jobs were added to CI
that were never added to the list, so a PR could merge to `main` with them red,
and `main` cuts a PyPI release on every merge.

`.github/required-checks.txt` is now the source of truth and this script keeps it
honest. It fails when:

  * a required name is not a job that runs on ``pull_request`` (removed, renamed,
    or never existed), or
  * a check name is **ambiguous** — the same name produced by more than one
    workflow. GitHub matches required checks by name, so a duplicate cannot be
    required unambiguously. Three names collided here when this was written
    (``lint`` in ci/markdownlint/theme-lint, ``audit`` in lighthouse/pip-audit,
    ``analyze`` in codeql/sonarcloud), which is why the prose list saying
    "require `lint`" was not actually implementable.

Stdlib only, like the repo's other gates — there is no YAML parser in the lint
toolchain. The parsing is deliberately narrow (top-level keys under ``jobs:``)
and refuses to report success if it parsed nothing, so a parser that silently
stops matching fails the gate instead of passing it vacuously.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CONFIG = ROOT / ".github" / "required-checks.txt"

# A job id line: exactly two spaces of indent, directly under `jobs:`.
_JOB = re.compile(r"^  ([A-Za-z0-9][\w-]*):\s*$")
# `    name: something` within a job block overrides the displayed check name.
_NAME = re.compile(r"^    name:\s*(.+?)\s*$")
# A required entry like `tests (ubuntu-latest, 3.9)` -> the `tests` job.
_MATRIX_LEG = re.compile(r"^(?P<job>[A-Za-z0-9][\w-]*)\s*\(.*\)$")


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    return s


def parse_workflow(path: Path) -> Tuple[bool, Dict[str, str]]:
    """Return ``(runs_on_pull_request, {job_id: display_name})`` for one file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        jobs_at = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return False, {}

    header = "\n".join(lines[:jobs_at])
    on_pr = bool(re.search(r"^\s{2}pull_request:", header, re.M))

    jobs: Dict[str, str] = {}
    current = None
    for line in lines[jobs_at + 1:]:
        job = _JOB.match(line)
        if job:
            current = job.group(1)
            jobs[current] = current
            continue
        if current is not None:
            name = _NAME.match(line)
            if name:
                jobs[current] = _strip_quotes(name.group(1))
    return on_pr, jobs


def collect() -> Tuple[Dict[str, List[str]], Set[str]]:
    """``({check_name: [workflow, ...]}, {names that run on pull_request})``."""
    by_name: Dict[str, List[str]] = {}
    on_pr: Set[str] = set()
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        raise SystemExit("required-checks: no workflow files found under %s" % WORKFLOWS)
    parsed_any = False
    for path in files:
        runs_on_pr, jobs = parse_workflow(path)
        if jobs:
            parsed_any = True
        for display in jobs.values():
            by_name.setdefault(display, []).append(path.name)
            if runs_on_pr:
                on_pr.add(display)
    if not parsed_any:
        # Every workflow parsed to zero jobs: the format changed and this gate
        # would otherwise pass by finding no problems. Fail instead.
        raise SystemExit("required-checks: parsed 0 jobs from %d workflow files — "
                         "the parser is broken, not the config" % len(files))
    return by_name, on_pr


def read_config() -> List[str]:
    if not CONFIG.exists():
        raise SystemExit("required-checks: missing %s" % CONFIG)
    out = []
    for raw in CONFIG.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    if not out:
        raise SystemExit("required-checks: %s lists no checks" % CONFIG)
    return out


def resolve(required: str, on_pr: Set[str]) -> Tuple[bool, str]:
    """Is ``required`` satisfied by some job that runs on pull_request?"""
    if required in on_pr:
        return True, required
    # `tests (ubuntu-latest, 3.9)` is one leg of the `tests` matrix. Expanding a
    # matrix correctly needs a YAML parser; checking that the underlying job
    # still exists catches the failure that matters (renamed/deleted job)
    # without reimplementing matrix expansion.
    leg = _MATRIX_LEG.match(required)
    if leg and leg.group("job") in on_pr:
        return True, leg.group("job")
    # A called reusable workflow reports as "caller / job".
    if " / " in required:
        head = required.split(" / ", 1)[0].strip()
        if head in on_pr:
            return True, head
    return False, ""


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print-api", action="store_true",
                    help="print the branch-protection API payload and exit")
    args = ap.parse_args(argv)

    by_name, on_pr = collect()
    required = read_config()

    if args.print_api:
        payload = {
            "required_status_checks": {"strict": True, "contexts": required},
            # Deliberately null: the repo's working model is parallel loop/*
            # branches self-merging, so requiring reviews would deadlock it.
            "required_pull_request_reviews": None,
            "enforce_admins": False,
            "restrictions": None,
        }
        print("# apply with:")
        print("#   curl -X PUT -H \"Authorization: Bearer $GITHUB_TOKEN\" \\")
        print("#     https://api.github.com/repos/jonnyeclectic/boost/branches/main/protection \\")
        print("#     -d @payload.json")
        print(json.dumps(payload, indent=2))
        return 0

    problems: List[str] = []

    ambiguous = {n: w for n, w in sorted(by_name.items()) if len(w) > 1}
    for name, where in ambiguous.items():
        problems.append("check name %r is produced by %d workflows (%s) — GitHub "
                        "matches required checks by name, so this one cannot be "
                        "required unambiguously" % (name, len(where), ", ".join(where)))

    for name in required:
        ok, _via = resolve(name, on_pr)
        if not ok:
            problems.append("required check %r is not a job that runs on "
                            "pull_request" % name)

    if problems:
        print("required-checks: %d problem(s)" % len(problems), file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        return 1

    print("required-checks: %d required, %d PR check names, no ambiguity."
          % (len(required), len(on_pr)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
