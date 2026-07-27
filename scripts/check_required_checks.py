#!/usr/bin/env python3
"""Gate: the required-status-check list must match the jobs that actually run.

Branch protection is configured in the GitHub UI, so the list of required checks
existed only as prose in CONTRIBUTING.md — and it drifted. Jobs were added to CI
that were never added to the list, so a PR could merge to `main` with them red,
and `main` cuts a PyPI release on every merge.

`.github/required-checks.txt` is now the source of truth and this script keeps it
honest. It fails when:

  * a required name is not a job that runs on ``pull_request`` (removed, renamed,
    or never existed),
  * a check name is **ambiguous** — the same name produced by more than one
    workflow. GitHub matches required checks by name, so a duplicate cannot be
    required unambiguously. Three names collided here when this was written
    (``lint`` in ci/markdownlint/theme-lint, ``audit`` in lighthouse/pip-audit,
    ``analyze`` in codeql/sonarcloud), which is why the prose list saying
    "require `lint`" was not actually implementable, or
  * a required name comes from a workflow with no ``merge_group:`` trigger. The
    merge queue evaluates required checks against its own temporary
    ``gh-readonly-queue/*`` ref rather than against the pull request, so such a
    check never reports there and every enqueued PR waits forever. Nothing is
    broken until the queue is switched on — which is a repo Setting, invisible
    from the tree — so this is checked ahead of time rather than discovered
    afterwards, or
    narrowed by ``paths:``/``paths-ignore:`` or by a ``types:`` list that omits
    the ordinary open/push events. This is the failure mode that actually bricks
    a repository: when a PR touches no matching path GitHub creates no check run
    at all, so branch protection waits for a status that is never coming and the
    PR can never merge. It is not hypothetical — the first version of this list
    required ``validate``, ``markdown-lint``, ``theme-lint`` and ``vale``, all
    four of which are path-filtered, and this gate passed it.

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
# The `  pull_request:` trigger line itself, capturing any same-line remainder.
_PR_TRIGGER = re.compile(r"^  pull_request:\s*(.*)$")
# The `  merge_group:` trigger. Presence is all that matters — unlike
# pull_request there is nothing to narrow it with that would apply here.
_MG_TRIGGER = re.compile(r"^  merge_group:\s*(.*)$")

# How a workflow's pull_request trigger behaves.
PR_NONE = "none"          # no pull_request trigger at all
PR_ALWAYS = "always"      # fires on every PR — safe to require
PR_FILTERED = "filtered"  # fires only on some PRs — NEVER safe to require


def has_merge_group(header_lines: List[str]) -> bool:
    """Does this workflow declare a ``merge_group:`` trigger?

    Same narrow, stdlib-only parsing as everything else here: a top-level
    trigger key sits at exactly two spaces of indent inside the ``on:`` block.
    """
    return any(_MG_TRIGGER.match(line) for line in header_lines)


def pull_request_state(header_lines: List[str]) -> str:
    """Classify the ``pull_request:`` trigger in a workflow header.

    Returns one of :data:`PR_NONE`, :data:`PR_ALWAYS`, :data:`PR_FILTERED`.

    Stdlib-only and deliberately narrow, like the rest of this gate: find the
    ``  pull_request:`` line, then take the more-indented lines that follow it
    as its block. A ``paths:``/``paths-ignore:`` key means the trigger only
    fires when the PR touches matching files. A ``types:`` list means it only
    fires on the listed activity types — which is fine if it still covers the
    ordinary ``opened``/``synchronize`` pair, and disqualifying otherwise
    (``types: [labeled]`` is used here for the opt-in eval and fuzz jobs).
    """
    for i, line in enumerate(header_lines):
        match = _PR_TRIGGER.match(line)
        if not match:
            continue
        block = [match.group(1)] if match.group(1).strip() else []
        for nxt in header_lines[i + 1:]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            if len(nxt) - len(nxt.lstrip()) <= 2:
                break  # dedented back to a sibling trigger
            block.append(nxt)
        text = "\n".join(block)
        if re.search(r"^\s*paths(-ignore)?\s*:", text, re.M):
            return PR_FILTERED
        # Covers both inline (`types: [opened, synchronize]`) and block
        # (`types:\n  - labeled`) forms — either way the names land in `text`.
        if (re.search(r"^\s*types\s*:", text, re.M)
                and not ("opened" in text and "synchronize" in text)):
            return PR_FILTERED
        return PR_ALWAYS
    return PR_NONE


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    return s


def parse_workflow(path: Path) -> Tuple[str, bool, Dict[str, str]]:
    """``(pull_request_state, has_merge_group, {job_id: display_name})``."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        jobs_at = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return PR_NONE, False, {}

    on_pr = pull_request_state(lines[:jobs_at])
    on_mg = has_merge_group(lines[:jobs_at])

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
    return on_pr, on_mg, jobs


def collect() -> Tuple[Dict[str, List[str]], Set[str], Dict[str, str], Set[str]]:
    """``({check_name: [workflow, ...]}, {on every PR}, {name: workflow}, {on merge_group})``.

    The third value maps a *conditionally*-triggered check name to the workflow
    that narrows it, so the error message can name the culprit. The fourth is
    the set of names that would also report on a merge-queue ref.
    """
    by_name: Dict[str, List[str]] = {}
    on_pr: Set[str] = set()
    filtered: Dict[str, str] = {}
    on_mg: Set[str] = set()
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        raise SystemExit("required-checks: no workflow files found under %s" % WORKFLOWS)
    parsed_any = False
    for path in files:
        runs_on_pr, runs_on_mg, jobs = parse_workflow(path)
        if jobs:
            parsed_any = True
        for display in jobs.values():
            by_name.setdefault(display, []).append(path.name)
            if runs_on_pr == PR_ALWAYS:
                on_pr.add(display)
            elif runs_on_pr == PR_FILTERED:
                filtered[display] = path.name
            if runs_on_mg:
                on_mg.add(display)
    if not parsed_any:
        # Every workflow parsed to zero jobs: the format changed and this gate
        # would otherwise pass by finding no problems. Fail instead.
        raise SystemExit("required-checks: parsed 0 jobs from %d workflow files — "
                         "the parser is broken, not the config" % len(files))
    return by_name, on_pr, filtered, on_mg


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
    """Is ``required`` satisfied by some job name in ``on_pr``?

    Called twice — once against the names that run on every PR, and once
    against the conditionally-triggered ones, so a required entry that matches
    only the latter can be reported as the deadlock it is rather than as a
    generic "no such job".
    """
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


def workflows_for(required: str, by_name: Dict[str, List[str]]) -> List[str]:
    """Which workflow file(s) produce ``required``.

    Accepts the same three spellings :func:`resolve` does — an exact name, a
    matrix leg like ``tests (ubuntu-latest, 3.9)``, and a reusable-workflow
    ``caller / job`` — so an error message can name the file to edit instead of
    leaving the reader to grep for it.
    """
    if required in by_name:
        return by_name[required]
    leg = _MATRIX_LEG.match(required)
    if leg and leg.group("job") in by_name:
        return by_name[leg.group("job")]
    if " / " in required:
        head = required.split(" / ", 1)[0].strip()
        if head in by_name:
            return by_name[head]
    return ["an unknown workflow"]


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print-api", action="store_true",
                    help="print the branch-protection API payload and exit")
    args = ap.parse_args(argv)

    by_name, on_pr, filtered, on_mg = collect()
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
        # A required context must also report on the merge queue's ref. The
        # queue evaluates required checks against gh-readonly-queue/*, not
        # against the pull request, so a workflow without a `merge_group:`
        # trigger never reports there and every enqueued PR waits forever —
        # the same never-reports deadlock as a `paths:` filter, arriving
        # through a different door. Checked independently of the
        # pull_request result below: a check can be perfectly requireable
        # today and still be the thing that breaks the day the queue is
        # switched on, which is a repo Setting and not visible from here.
        queue_ok, _ = resolve(name, on_mg)
        if not queue_ok:
            where = workflows_for(name, by_name)
            problems.append(
                "required check %r comes from %s, which has no `merge_group:` "
                "trigger. Enabling the merge queue would deadlock every PR on "
                "it, because the queue evaluates required checks against the "
                "gh-readonly-queue/* ref where this never reports — add the "
                "trigger, or drop the check from the required list"
                % (name, ", ".join(where)))

        ok, _via = resolve(name, on_pr)
        if ok:
            continue
        conditional, via = resolve(name, set(filtered))
        if conditional:
            problems.append(
                "required check %r only runs on SOME pull requests (%s narrows "
                "its trigger with paths:/types:). GitHub creates no check run at "
                "all on a PR that does not match, so branch protection would "
                "wait forever and the PR could never merge — drop it from the "
                "list or widen the trigger" % (name, filtered[via]))
        else:
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
