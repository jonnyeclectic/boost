#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Fail when a commit in the range lacks a Signed-off-by matching its author.

The Developer Certificate of Origin (see the ``DCO`` file at the repository
root) is an assertion *by the contributor* that they have the right to submit
the work. That is the whole point, and it is why this checker compares the
sign-off against the commit's own author rather than accepting any sign-off at
all: a trailer naming somebody else certifies nothing.

Scope is deliberately the commits a pull request adds, not all of history.
Backfilling sign-offs onto 569 existing commits would mean rewriting `main`,
which would break 478 tags and invalidate the SLSA build-provenance
attestations on every published release — and, worse, the backfilled trailer
would be an assertion nobody actually made. DCO is adopted going forward, which
is how every project that adopts one does it.

Usage::

    python3 scripts/check_dco.py                  # HEAD against origin/main
    python3 scripts/check_dco.py BASE..HEAD       # an explicit range

Exit status is 0 when every commit is signed off (or exempt) and 1 otherwise,
with the offending commits and the exact line to add printed to stdout.
"""
from __future__ import annotations

import re
import subprocess
import sys

# Bots cannot agree to a certificate. Dependabot already emits its own
# Signed-off-by and GitHub's own automation commits are generated from content
# that a human already reviewed in the pull request that produced them, so
# requiring a certificate from an account that cannot give one would only fail
# builds without adding assurance.
EXEMPT_NAMES = frozenset({
    "dependabot[bot]",
    "github-actions[bot]",
    "pre-commit-ci[bot]",
})

_SIGNOFF = re.compile(r"^Signed-off-by:\s*(.+?)\s*<([^>]+)>\s*$", re.MULTILINE)
_MERGE_SUBJECT = re.compile(r"^Merge (branch|pull request|remote-tracking) ")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True).stdout


def _default_range() -> str:
    for base in ("origin/main", "main"):
        try:
            _git("rev-parse", "--verify", base)
        except subprocess.CalledProcessError:
            continue
        return "%s..HEAD" % base
    return "HEAD~1..HEAD"


def _exempt(name: str, email: str) -> bool:
    return name in EXEMPT_NAMES or name.endswith("[bot]") or email.endswith(
        "[bot]@users.noreply.github.com")


def check(rev_range: str) -> list[tuple[str, str, str, str]]:
    """Return ``(sha, subject, author_name, author_email)`` for each failure."""
    shas = [s for s in _git("rev-list", "--no-merges", rev_range).split() if s]
    failures: list[tuple[str, str, str, str]] = []
    for sha in shas:
        record = _git("show", "-s", "--format=%an%n%ae%n%s%n%B", sha)
        name, email, subject, body = record.split("\n", 3)
        if _exempt(name, email) or _MERGE_SUBJECT.match(subject):
            continue
        signers = {(m.group(1).strip(), m.group(2).strip().lower())
                   for m in _SIGNOFF.finditer(body)}
        if (name, email.lower()) not in signers:
            failures.append((sha, subject, name, email))
    return failures


def main(argv: list[str]) -> int:
    rev_range = argv[0] if argv else _default_range()
    try:
        failures = check(rev_range)
    except subprocess.CalledProcessError as exc:
        print("check-dco: git failed on %s: %s" % (rev_range, exc.stderr.strip()))
        return 1

    if not failures:
        print("check-dco: OK — every commit in %s is signed off." % rev_range)
        return 0

    print("check-dco: %d commit(s) in %s lack a Signed-off-by matching the "
          "author.\n" % (len(failures), rev_range))
    for sha, subject, name, email in failures:
        print("  %s  %s" % (sha[:9], subject[:68]))
        print("      add:  Signed-off-by: %s <%s>" % (name, email))
    print("\nThe sign-off must name the commit's own author — it is that "
          "person\ncertifying the DCO (see the DCO file at the repository "
          "root), so a\ntrailer naming anyone else does not satisfy it.\n")
    print("Fix the most recent commit with:\n"
          "    git commit --amend --signoff --no-edit\n"
          "Fix a range with:\n"
          "    git rebase --signoff %s\n"
          "Sign off automatically in future with:\n"
          "    git commit -s" % rev_range.split("..")[0])
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
