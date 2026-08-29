#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Fail a pull request that does not contain the base branch's tip.

Every merge to `main` cuts a PyPI release, and two pull requests that are each
green in isolation can still land a broken *combination*. That is not
hypothetical here: on 2026-08-29 two of them each added a roadmap item and each
regenerated `docs/roadmap.html`. The item files merged cleanly — that is what
the file-per-item design is for — but the generated board is one shared file,
and a squash merge takes one side of it without reporting a conflict. `main`
went red on a counter that was correct on both branches and wrong for their
union, and because `ci` was red the release workflow's guard never armed, so
two merged pull requests sat unreleased.

GitHub can enforce this natively and the repository asks it to twice, which is
the trap. Classic branch protection sets `strict: true` but also
`enforce_admins: false`, so it does not apply to the account that does the
merging; the active ruleset, which has no bypass actors and therefore does
apply, sets `strict_required_status_checks_policy: false`. Two mechanisms, and
the binding one had the safety off. A required *check* is enforced by the
ruleset either way, which is why this lives in the repository instead of in a
settings page nobody can diff.

Usage (CI passes the base explicitly; locally it defaults to origin/main)::

    python3 scripts/check_branch_current.py
    python3 scripts/check_branch_current.py --base origin/main
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def problem(base_sha: str, *, contains_base: bool) -> str | None:
    """The message to print, or None when the branch is current.

    Split from the git plumbing so the verdict is a pure function of the one
    thing that decides it: whether this branch already contains the base tip.
    """
    if contains_base:
        return None
    return (
        "this branch does not contain %s, the current tip of the base branch.\n"
        "  Two branches that are each green can still merge into a broken\n"
        "  combination — a generated file is the usual way, since a squash\n"
        "  merge takes one side of it without reporting a conflict.\n"
        "  Fix: git fetch origin main && git rebase origin/main\n"
        "  then re-run `make generate` and commit any drift."
    ) % base_sha


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def contains(base: str) -> tuple[str, bool]:
    """(base sha, whether HEAD already contains it)."""
    base_sha = _git("rev-parse", base)
    result = subprocess.run(["git", "merge-base", "--is-ancestor", base_sha, "HEAD"],
                            capture_output=True, text=True)
    return base_sha, result.returncode == 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main",
                        help="base ref the branch must contain (default: origin/main)")
    args = parser.parse_args(argv)

    try:
        base_sha, ok = contains(args.base)
    except subprocess.CalledProcessError:
        # No such ref — a shallow clone or a fork without the base fetched.
        # Report it rather than passing silently: a check that cannot look is
        # not a check that passed.
        print("check-branch-current: cannot resolve %s — fetch it first" % args.base,
              file=sys.stderr)
        return 2

    found = problem(base_sha, contains_base=ok)
    if found is None:
        print("check-branch-current: OK — branch contains %s (%s)"
              % (args.base, base_sha[:8]))
        return 0
    print("check-branch-current: %s" % found, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
