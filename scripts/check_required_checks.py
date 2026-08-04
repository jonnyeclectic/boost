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

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CONFIG = ROOT / ".github" / "required-checks.txt"

# `main` is protected TWICE: by a classic branch protection and by a repository
# ruleset. They are independent objects with independent lists, and applying the
# file to one leaves the other untouched — which is how the ruleset came to be
# missing `bdd`, `evals` and `onnx-inference` while this script reported the
# config clean. It was checking the file against the *workflows*, and emitting a
# payload for the classic endpoint only; nothing here had ever heard of a
# ruleset.
#
# Which mechanism actually binds is the part that made the gap expensive rather
# than untidy. The classic protection sets `enforce_admins: false`, so it does
# not apply to the identity that merges here; the ruleset carries
# `bypass_actors: []`, so it applies to everyone. The three checks missing from
# the ruleset were therefore the three that nothing enforced — among them
# `evals`, the retrieval-quality floor, and `onnx-inference`, whose entry in
# required-checks.txt says in as many words that the failure it catches is
# silent.
GITHUB_API = "https://api.github.com"
REPO = "jonnyeclectic/boost"
BRANCH = "main"
# GitHub Actions' app id. A ruleset records which app must produce each context;
# leaving it out lets any app satisfy a check by name, which is a weaker gate
# than the one the file describes.
ACTIONS_APP_ID = 15368

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


def has_merge_group(header_lines: list[str]) -> bool:
    """Does this workflow declare a ``merge_group:`` trigger?

    Same narrow, stdlib-only parsing as everything else here: a top-level
    trigger key sits at exactly two spaces of indent inside the ``on:`` block.
    """
    return any(_MG_TRIGGER.match(line) for line in header_lines)


def pull_request_state(header_lines: list[str]) -> str:
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


def parse_workflow(path: Path) -> tuple[str, bool, dict[str, str]]:
    """``(pull_request_state, has_merge_group, {job_id: display_name})``."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        jobs_at = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return PR_NONE, False, {}

    on_pr = pull_request_state(lines[:jobs_at])
    on_mg = has_merge_group(lines[:jobs_at])

    jobs: dict[str, str] = {}
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


def collect() -> tuple[dict[str, list[str]], set[str], dict[str, str], set[str]]:
    """``({check_name: [workflow, ...]}, {on every PR}, {name: workflow}, {on merge_group})``.

    The third value maps a *conditionally*-triggered check name to the workflow
    that narrows it, so the error message can name the culprit. The fourth is
    the set of names that would also report on a merge-queue ref.
    """
    by_name: dict[str, list[str]] = {}
    on_pr: set[str] = set()
    filtered: dict[str, str] = {}
    on_mg: set[str] = set()
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


def read_config() -> list[str]:
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


def resolve(required: str, on_pr: set[str]) -> tuple[bool, str]:
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


def workflows_for(required: str, by_name: dict[str, list[str]]) -> list[str]:
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


def classic_payload(required: list[str]) -> dict:
    """The `PUT /branches/{branch}/protection` body for this required list."""
    return {
        "required_status_checks": {"strict": True, "contexts": list(required)},
        # Deliberately null: the repo's working model is parallel loop/*
        # branches self-merging, so requiring reviews would deadlock it.
        "required_pull_request_reviews": None,
        "enforce_admins": False,
        "restrictions": None,
    }


def ruleset_rule(required: list[str]) -> dict:
    """The `required_status_checks` RULE for a repository ruleset.

    Shaped differently from the classic payload on purpose — this is not a
    stylistic variant of the same thing. A ruleset names each context as an
    object carrying the app that must produce it, and spells `strict` as
    `strict_required_status_checks_policy`. Hand-translating between the two
    forms is exactly the step that got skipped.
    """
    return {
        "type": "required_status_checks",
        "parameters": {
            "strict_required_status_checks_policy": True,
            "required_status_checks": [
                {"context": c, "integration_id": ACTIONS_APP_ID} for c in required
            ],
        },
    }


def drift(required: list[str], remote: list[str]) -> tuple[list[str], list[str]]:
    """``(missing, extra)`` — how a live mechanism disagrees with the file.

    Order-insensitive and duplicate-tolerant: GitHub returns contexts in its own
    order, and a list that merely sorts differently is not drift.
    """
    want, have = set(required), set(remote)
    return sorted(want - have), sorted(have - want)


def _api(path: str, token: str) -> object:
    import urllib.request
    req = urllib.request.Request(  # noqa: S310  GITHUB_API is a hardcoded https constant
        GITHUB_API + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "boost-check-required-checks"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310  same
        return json.load(resp)


def ruleset_contexts(detail: dict) -> tuple[bool, list[str]]:
    """``(has_rule, contexts)`` for one ruleset's required-status-checks rule.

    ``has_rule`` is returned separately from an empty list because the two mean
    opposite things: a ruleset with no such rule requires nothing at all, which
    is a much louder problem than one whose list has drifted.
    """
    for rule in detail.get("rules", []):
        if rule.get("type") == "required_status_checks":
            params = rule.get("parameters") or {}
            return True, [c.get("context") for c in params.get("required_status_checks", [])]
    return False, []


def verify_remote(required: list[str], token: str) -> list[str]:
    """Compare BOTH live mechanisms against the file. Returns problems."""
    problems: list[str] = []

    prot = _api("/repos/%s/branches/%s/protection" % (REPO, BRANCH), token)
    contexts = ((prot or {}).get("required_status_checks") or {}).get("contexts", [])
    missing, extra = drift(required, contexts)
    if missing or extra:
        problems.append(
            "classic branch protection on %r disagrees with %s — missing %s, extra %s "
            "(apply with `--print-api`)"
            % (BRANCH, CONFIG.name, missing or "nothing", extra or "nothing"))

    rulesets = _api("/repos/%s/rulesets" % REPO, token) or []
    checked = 0
    for summary in rulesets:
        detail = _api("/repos/%s/rulesets/%s" % (REPO, summary["id"]), token)
        includes = ((detail.get("conditions") or {}).get("ref_name") or {}).get("include", [])
        # `~DEFAULT_BRANCH` is GitHub's alias for whatever the default branch is.
        if not ({"refs/heads/" + BRANCH, "~DEFAULT_BRANCH"} & set(includes)):
            continue
        if detail.get("enforcement") != "active":
            continue
        checked += 1
        has_rule, contexts = ruleset_contexts(detail)
        if not has_rule:
            problems.append(
                "active ruleset %r targets %r but has no required_status_checks "
                "rule at all — it gates nothing" % (detail.get("name"), BRANCH))
            continue
        missing, extra = drift(required, contexts)
        if missing or extra:
            problems.append(
                "ruleset %r (id %s) disagrees with %s — missing %s, extra %s "
                "(apply with `--print-ruleset`; send the WHOLE body, a partial "
                "PUT drops the other rules)"
                % (detail.get("name"), detail.get("id"), CONFIG.name,
                   missing or "nothing", extra or "nothing"))

    if not checked:
        # Silence here would read as "the rulesets agree", which is the failure
        # this whole function exists to stop being invisible.
        problems.append(
            "no active ruleset targets %r — if protection moved to rulesets, "
            "this check is now blind; if it did not, one was deleted" % BRANCH)
    return problems


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print-api", action="store_true",
                    help="print the CLASSIC branch-protection payload and exit")
    ap.add_argument("--print-ruleset", action="store_true",
                    help="print the ruleset required_status_checks rule and exit")
    ap.add_argument("--verify-remote", action="store_true",
                    help="compare BOTH live mechanisms against the file "
                         "(needs GITHUB_TOKEN; network — not part of `make lint`)")
    args = ap.parse_args(argv)

    by_name, on_pr, filtered, on_mg = collect()
    required = read_config()

    if args.print_api:
        print("# apply with:")
        print("#   curl -X PUT -H \"Authorization: Bearer $GITHUB_TOKEN\" \\")
        print("#     %s/repos/%s/branches/%s/protection \\" % (GITHUB_API, REPO, BRANCH))
        print("#     -d @payload.json")
        print("# NOTE: this is only HALF of `main`'s protection — see --print-ruleset.")
        print(json.dumps(classic_payload(required), indent=2))
        return 0

    if args.print_ruleset:
        print("# One rule out of a ruleset body. The ruleset PUT replaces the whole")
        print("# object, so fetch it, swap ONLY this rule, and send it back — a")
        print("# partial body silently drops deletion/non_fast_forward/code_scanning.")
        print("#   curl %s/repos/%s/rulesets" % (GITHUB_API, REPO))
        print(json.dumps(ruleset_rule(required), indent=2))
        return 0

    if args.verify_remote:
        import os
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            # A skip, not a pass: `make lint` never passes this flag, so the
            # offline gate is unaffected, and a caller who asked for the remote
            # check deserves to know it did not happen.
            print("required-checks: --verify-remote skipped (no GITHUB_TOKEN)")
            return 0
        try:
            remote_problems = verify_remote(required, token)
        # A network fault is not drift: exit 2 (could not check) rather than 1
        # (found a problem), so a caller can tell "GitHub was down" from "your
        # protection is wrong" without reading the message.
        except Exception as exc:
            print("required-checks: --verify-remote could not reach GitHub (%s: %s)"
                  % (type(exc).__name__, exc), file=sys.stderr)
            return 2
        if remote_problems:
            print("required-checks: %d live-protection problem(s)"
                  % len(remote_problems), file=sys.stderr)
            for p in remote_problems:
                print("  - %s" % p, file=sys.stderr)
            return 1
        print("required-checks: live protection matches %s on both mechanisms "
              "(%d checks)." % (CONFIG.name, len(required)))
        return 0

    problems: list[str] = []

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
