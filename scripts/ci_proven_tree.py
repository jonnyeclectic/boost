#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Decide whether a push to ``main`` may skip the full mutation run.

A PR's mutation gate scores only the functions it changed (plus their direct
callers), so the whole-codebase run on ``main`` is what guards the rest. It is
also the slowest job, and most pushes to ``main`` are a PR that was already
tested: a squash-merge of an up-to-date PR produces a new commit SHA over the
*same tree*, and the check below is exactly that equality. Skipping is allowed
only when all three facts hold:

1. an associated PR *into main* has a head commit whose tree is byte-identical
   to this commit's tree (so the code on ``main`` is the code that PR's CI ran).
   A PR aimed at another branch is not counted: its ``pull_request`` run built
   the PR merged into *that* base, a different tree from the one that landed;
2. that head's newest ``ci`` run, on the ``pull_request`` event, is a
   first-attempt run that concluded ``success`` and was created at most 13 days
   before now. The age bound is the badge's: on a proven push ci.yml publishes
   the coverage badge from that run's ``coverage-report`` artifact, which is
   kept 14 days, so an older run cannot stand in for this push's tests. A full
   run then measures its own. And that run carries a live (unexpired)
   artifact named ``tested-tree-<this commit's tree>``. Every ``pull_request``
   run uploads one (ci.yml's ``lint`` job), named for ``HEAD^{tree}`` of the
   merge commit it checked out -- the tree it actually built. A run is found
   by its head SHA, and a head SHA does not say which base the run merged it
   into: a PR retargeted to ``main`` after its run (a base change starts no
   new run) or the same head open into a second base can leave a green run
   that built ``head + another branch``, whose head tree still equals the
   tree that lands. Fact 1 cannot see that; this name can;
3. the newest completed whole-codebase run on ``main`` (``schedule`` or
   ``workflow_dispatch``, whichever is newer) concluded ``success`` and was
   created at most 48 hours before now. This is the backstop for what a
   diff-scoped PR gate cannot see: a red nightly turns every push back into a
   full run until it is green again, and so does a *missing* one. The age bound
   is what makes "green" mean "recently": without it, a nightly that quietly
   stopped (workflow disabled, schedules dropped) would keep authorising skips on
   a months-old result. 48 hours tolerates one missed night and not two.

THE DIRECTION IS THE WHOLE POINT. A wrong "skip" ships code no mutation run has
seen; a wrong "run" costs one mutation run. So every fact that is unknown,
missing, errored or ambiguous gives ``skip=false`` with a reason, and exactly one
shape gives ``true``. Concretely:

* ``gather`` catches nothing. A 404, a 403/429 rate limit, a timeout, malformed
  JSON, a missing ``tree.sha`` or a response of the wrong shape all raise, and
  ``main`` -- the only catch site -- turns the exception into
  ``error: <type>``. In particular one of the two whole-codebase queries failing
  is *unknown*, not "use the other one": that would read a stale green nightly as
  current.
* *Empty* is different from *errored*. A query that returns no runs is a real
  answer ("no PR run yet", "no nightly yet"), and one whole-codebase query being
  empty while the other has a run simply means the other is the newest.
* ``gather`` does not trust the server's filters. The run it keeps for a head is
  the newest by parsed ``created_at`` (ties broken by run id), never the first in
  the list, and the run's own ``event``, ``head_sha`` and ``run_attempt`` are
  recorded on the ``Candidate`` for ``decide`` to check. A whole-codebase run must
  itself say ``head_branch == "main"`` (a ``workflow_dispatch`` on a feature
  branch is routine, and its result says nothing about ``main``); a run on another
  branch, or with no branch at all, is unknown, not skipped over. ``run_attempt`` has to
  be 1: a re-run is the "cancelled or re-run" case in the plan's review focus, and
  the cost of reading it as unproven is one extra mutation run. A run object that
  lacks one of those fields yields a value ``decide`` rejects; absence is never
  defaulted into "fine". Likewise the artifact listing is asked for one name
  and every entry is checked for exactly that name, an ``expired`` that is the
  boolean ``false``, and no other run's id; a listing of the wrong shape, or a
  failed request for it, is an error like any other.
* The nightly's age, and the PR run's, are judged against ``now``, which is
  injectable (``decide``'s ``now=``, the CLI's ``--now``) so tests do not depend
  on the day they run; production never passes it. A ``created_at`` that is
  missing, unparseable or without a timezone makes the age unknown, and unknown
  means a full run. A ``created_at`` more than a few minutes in the *future* is
  also refused: skew between GitHub's clock and the runner's is seconds, and
  anything larger is a corrupt fact rather than a fresh run.
* Redirects are refused. ``urllib`` re-sends the ``Authorization`` header to a
  redirect target, and nothing here should ever be sent anywhere but
  ``api.github.com``.

A SECOND, INDEPENDENT QUESTION: was the base commit's mutation verdict green?
A push that is not proven may still plan no mutation run, when the diff from
``github.event.before`` touches nothing that can move the score -- and then
``mutation`` reports green on the strength of the base alone. That is only
sound if the base's own verdict was green. It was not checked: #1285 landed
(push b5d9c4ec, ci run 41148140704) with lint and ``mutation`` red; the next
push (46664146, run 41168736566) changed only ``.github/workflows/publish.yml``,
so its plan was ``none``, ``mutation`` reported success, the run went green and
publish.yml released the code #1285 had left red. ``--before SHA`` asks: the
newest ``ci`` push run on ``main`` for that commit, its jobs (latest attempt,
one page), and the one named exactly ``mutation``. Green only on
``status == completed`` and ``conclusion == success`` -- and then only if the
newest completed whole-codebase run on ``main`` (fact 3's, by the same
``_last_whole`` query) concluded ``success`` too. The base's push run may
itself have planned ``none`` and inherited; a red nightly is the full run that
says the inherited verdict was wrong, and a push run's green must not hide it.
Its age is not judged here: the question is whether a red result is being
hidden, not whether a green one is recent. Everything else -- no base (empty,
all-zero), no run, no such job, still running, any other conclusion, a red or
missing nightly, more jobs or runs than one page holds, any API, HTTP, JSON or
timeout error, a rate limit -- is not green. ci.yml holds a proven push to
this verdict as well as a push its diff calls irrelevant: the PR run that
proves a tree diffed against the same base, and planned ``none`` whenever its
own diff was irrelevant. It is gathered and caught apart from the decision
above: an error in either never changes the other's answer.

CLI. ``ci_proven_tree.py --sha SHA [--before SHA]`` reads ``GITHUB_REPOSITORY``
and ``GITHUB_TOKEN``, appends ``skip=true|false``, ``pr_run_id=<id or empty>``,
``base_mutation_green=true|false`` and ``base_mutation=<word>`` (see
``base_mutation``) to ``$GITHUB_OUTPUT``, and appends the reason to
``$GITHUB_STEP_SUMMARY``. It
**always exits 0**: a nonzero exit would fail the job rather than fall back to a
full run, and the step's outputs are what the workflow reads. The reason can
carry strings that came from the API, so it is flattened to one bounded line
before it goes anywhere (a newline in ``$GITHUB_OUTPUT`` or a line starting
``::`` in the log would be an injection), and only values this script computes
are written to ``$GITHUB_OUTPUT``.

The shapes this reads were checked against the live API for this repository:
``commits/{sha}/pulls`` returns a list whose items carry ``head.sha``;
``git/commits/{sha}`` carries ``tree.sha`` (a squash-merged PR's head and merge
commit report the same one); a ``workflow_runs`` item carries ``id``, ``event``,
``head_sha``, ``status``, ``conclusion``, ``run_attempt`` and ``created_at``;
``actions/runs/{id}/artifacts?name=`` returns ``artifacts``, a list whose items
carry ``name``, ``expired`` and ``workflow_run.id``. The base lookup's two,
on 2026-11-03 for the #1285 incident: ``actions/workflows/ci.yml/runs?branch=
main&event=push&head_sha=b5d9c4ec...&per_page=100`` returned ``total_count`` 1
and run 41148140704 (``event`` push, ``head_branch`` main), and
``actions/runs/41148140704/jobs?filter=latest&per_page=100`` returned
``total_count`` 45 with 45 ``jobs``, each carrying ``run_id``, ``name``,
``status`` and ``conclusion`` -- ``mutation`` among them, completed, failure.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn

# A literal https prefix: the URL is never built from a scheme or host that
# came from anywhere else, which is what ruff's S310 wants to be sure of.
API_ROOT = "https://api.github.com/repos/"
API_VERSION = "2022-11-28"

# Per request. Several are made in one step, so the worst case is a few of
# these, and a hang is read by the workflow as "no answer" (skip=false).
TIMEOUT = 15

# The nightly and the manual dispatch are the two events that run the whole
# codebase; whichever finished last is the current state of "everything".
WHOLE_CODEBASE_EVENTS = ("schedule", "workflow_dispatch")

# The branch a push is being decided for. Used for the whole-codebase query and
# to check the answer to it, and for the base of an associated PR.
MAIN = "main"

# A nightly older than this does not count as "recent". 48 h = one missed night
# tolerated, two not; "more than" means exactly 48 h is still fresh.
MAX_NIGHTLY_AGE = timedelta(hours=48)

# A PR run older than this does not prove the tree. ci.yml keeps the
# `coverage-report` artifact 14 days, and on a proven push `coverage-badge`
# downloads it from the run this script names; a day's margin keeps a run near
# the edge from expiring between this decision and that download. "More than"
# again: exactly 13 days still proves. The `tested-tree-<tree>` artifact is
# kept at least as long (tests/unit/test_ci_proven_tree.py pins it), so a run
# young enough to prove never loses the record of what it built first.
MAX_PR_RUN_AGE = timedelta(days=13)

# The artifact every `pull_request` run of ci.yml uploads, suffixed with the
# tree of the merge commit it checked out. ci.yml spells the same prefix; the
# test of that step reads it from here.
TESTED_TREE_ARTIFACT = "tested-tree-"

# How far ahead of the runner's clock a run's created_at may be before it is
# treated as corrupt rather than as clock skew.
CLOCK_SKEW = timedelta(minutes=5)

# How many per-candidate reasons / characters one reason line may carry.
MAX_REASONS = 5
MAX_REASON_CHARS = 500

#: The ci.yml job whose verdict a push inherits from its base: the required
#: check (.github/required-checks.txt). It sets no `name:`, so the jobs API
#: names it by its key; tests/unit/test_ci_base_mutation.py pins both.
MUTATION_JOB = "mutation"

#: One page. Asked for explicitly, and a listing whose total_count says it
#: holds more than came back is not read: the newest run, or the one job named
#: `mutation`, could be on the page that was never fetched.
PER_PAGE = 100

_COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")      # sha-1 or sha-256
_OBJECT = _COMMIT       # a tree id has a commit id's shape
# `before` on the push that creates a ref: there is no base commit.
_ZERO = re.compile(r"0{40}(?:0{24})?")
# A status or conclusion from the API goes into $GITHUB_OUTPUT only if it is
# a plain lower-case word (GitHub's are: in_progress, timed_out, ...).
_WORD = re.compile(r"[a-z_]{1,32}")
# Everything ``base_mutation`` may say: those, plus this module's hyphenated
# own -- ``nightly-`` (8) before one of those (32) included. The hyphen is
# what keeps the two apart: no API status or conclusion can pass for one of
# this module's words (``missing-run``, ``no-base``, ...).
_BASE_WORD = re.compile(r"[a-z_-]{1,40}")
# owner/name, and neither half may be "." or "..": the value is spliced into a
# URL path, and `../x` would match a bare character class.
_REPO = re.compile(r"(?!\.{1,2}/)[A-Za-z0-9_.-]+/(?!\.{1,2}$)[A-Za-z0-9_.-]+")

Api = Callable[[str], Any]


@dataclass(frozen=True)
class Artifact:
    """One entry of a run's artifact listing, as far as the proof reads it.

    ``expired`` is the entry's own flag, or ``None`` when it has none or a
    non-boolean one -- which ``decide`` does not read as live. ``run_id`` is the
    run the entry says it belongs to (``workflow_run.id``), or ``None`` when it
    does not say: the listing is already per run, so absence is tolerated, but
    a different run is a contradiction ``decide`` refuses.
    """

    name: str
    expired: bool | None
    run_id: int | None = None


@dataclass(frozen=True)
class Candidate:
    """One PR head, and the newest ``ci`` run found for it.

    The first four fields are the brief's interface. The next three describe
    the run itself, and their defaults are the values of a run found by exactly
    the query ``gather`` makes (this head, ``pull_request``, first attempt) so a
    hand-built ``Candidate`` stays terse. ``gather`` never relies on them: it
    always fills all three from the API's own run object, and a field the object
    lacks becomes ``""`` / ``0``, which ``decide`` rejects.

    ``run_created_at`` has no such default, because no query pins it: ``None``
    is "unknown", and ``decide`` never skips on it. ``gather`` fills it from the
    run's own ``created_at`` (``None`` when missing, unparseable or naive).

    ``artifacts`` has none either: it is what the run's artifact listing
    returned for ``tested-tree-<this commit's tree>`` (see the module
    docstring, fact 2), and empty -- the default -- is "this run never said it
    built that tree", which ``decide`` never skips on. ``gather`` lists them
    for every run it finds; the server's ``name`` filter is not trusted, so
    every entry is kept for ``decide`` to check.
    """

    head_sha: str
    head_tree: str
    run_id: int | None
    conclusion: str | None
    run_event: str = "pull_request"
    run_head_sha: str | None = None     # None: the run is for ``head_sha``
    run_attempt: int = 1
    run_created_at: datetime | None = None
    artifacts: tuple[Artifact, ...] = ()


@dataclass(frozen=True)
class Nightly:
    """The newest completed whole-codebase run: how it ended, and when it began.

    ``created_at`` is an aware datetime, or ``None`` when the run's own value was
    missing, unparseable or had no timezone. ``decide`` never skips on ``None``.
    """

    conclusion: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class Decision:
    skip: bool
    reason: str
    pr_run_id: int | None = None


def _is_int(value: Any) -> bool:
    # bool is an int subclass, and a JSON `true` must not read as run number 1.
    return isinstance(value, int) and not isinstance(value, bool)


def _judge(merge_tree: str, cand: Candidate, now: datetime) -> tuple[bool, str]:
    """Is this candidate the proof? Returns (yes, why-not-or-why)."""
    head = (cand.head_sha or "?")[:12]
    if not cand.head_sha:
        return False, "a candidate has no head sha"
    if not cand.head_tree:
        return False, "PR head %s: its tree is unknown" % head
    if cand.head_tree != merge_tree:
        return False, "PR head %s: tree %s differs from this commit's %s" % (
            head, cand.head_tree[:12], merge_tree[:12])
    if not _is_int(cand.run_id):
        return False, "PR head %s: no ci pull_request run found" % head
    where = "PR head %s: ci run %s" % (head, cand.run_id)
    if cand.run_event != "pull_request":
        return False, "%s was a %r run, not pull_request" % (where, cand.run_event)
    run_head = cand.head_sha if cand.run_head_sha is None else cand.run_head_sha
    if run_head != cand.head_sha:
        return False, "%s is for head %s, not this one" % (where, run_head[:12] or "?")
    if cand.conclusion is None:
        return False, "%s has no conclusion yet (still running)" % where
    if cand.conclusion != "success":
        return False, "%s concluded %s" % (where, cand.conclusion)
    if cand.run_attempt != 1:
        return False, "%s is attempt %s, and only a first attempt counts" % (
            where, cand.run_attempt or "unknown")
    # Last, so a run that is red or re-run is reported as that, not as old.
    if cand.run_created_at is None:
        return False, "%s: created_at unknown, so its age is too" % where
    age = now - cand.run_created_at
    if age > MAX_PR_RUN_AGE:
        return False, ("%s is %s days old; a PR run proves a tree for %d days, "
                       "while its coverage-report artifact (kept 14) still exists"
                       % (where, _days(age), MAX_PR_RUN_AGE.days))
    if age < -CLOCK_SKEW:
        return False, "%s: created_at is in the future (%sh ahead of this clock)" % (
            where, _hours(age))
    # The run is green, first-attempt and fresh; did it build THIS tree? Only
    # its own record says so: the head tree matching is not enough, because
    # the run may have merged that head into another base (fact 2).
    want = TESTED_TREE_ARTIFACT + merge_tree
    named = [a for a in cand.artifacts
             if a.name == want and a.run_id in (None, cand.run_id)]
    if not named:
        return False, ("%s left no %s%s artifact, so nothing says it built this "
                       "tree (it may have merged the head into another base)"
                       % (where, TESTED_TREE_ARTIFACT, merge_tree[:12]))
    if not any(a.expired is False for a in named):
        return False, "%s: its %s%s artifact has expired" % (
            where, TESTED_TREE_ARTIFACT, merge_tree[:12])
    return True, "%s succeeded on this exact tree" % where


def _hours(delta: timedelta) -> str:
    """Hours, rounded UP to a tenth: 48 h and 1 s reads 48.1, never a fresh-looking 48."""
    tenths = math.ceil(abs(delta.total_seconds()) / 360)
    return ("%.1f" % (tenths / 10)).removesuffix(".0")


def _days(delta: timedelta) -> str:
    """Days, rounded UP to a tenth, like ``_hours``: 13 days and 1 s reads 13.1."""
    tenths = math.ceil(abs(delta.total_seconds()) / 8640)
    return ("%.1f" % (tenths / 10)).removesuffix(".0")


def _age_problem(created_at: datetime | None, now: datetime) -> str | None:
    """Why a nightly created at ``created_at`` is not recent enough, or None."""
    if created_at is None:
        return "nightly age unknown (created_at missing or unparseable)"
    age = now - created_at
    if age > MAX_NIGHTLY_AGE:
        return "nightly stale (%sh)" % _hours(age)
    if age < -CLOCK_SKEW:
        return "nightly created_at is in the future (%sh ahead of this clock)" % _hours(age)
    return None


def decide(merge_tree: str, candidates: list[Candidate],
           last_whole: str | Nightly | None, now: datetime | None = None) -> Decision:
    """The pure decision: skip only when every fact is known and green.

    ``last_whole`` is what ``gather`` returns, a ``Nightly``, whose age is judged
    against ``now`` (the real clock when omitted). A bare conclusion string is
    also accepted -- the brief's original form -- and is judged on the
    conclusion alone: the caller then owns the freshness of what it passes.
    ``main`` always goes through ``gather``. Each candidate's PR run is aged
    against the same ``now``.
    """
    now = datetime.now(UTC) if now is None else now
    reasons: list[str] = []
    winner: Candidate | None = None
    if not isinstance(merge_tree, str) or not merge_tree:
        reasons.append("this commit's tree is unknown")
    elif not candidates:
        reasons.append("no pull request into main is associated with this commit "
                       "(a direct push, or a PR aimed at another branch)")
    else:
        for cand in candidates:
            ok, why = _judge(merge_tree, cand, now)
            if ok:
                winner = cand
                break
            reasons.append(why)
    if len(reasons) > MAX_REASONS:      # the nightly's reasons below are never cut
        reasons = [*reasons[:MAX_REASONS], "and %d more" % (len(reasons) - MAX_REASONS)]

    if isinstance(last_whole, Nightly):
        conclusion = last_whole.conclusion
        age_problem = _age_problem(last_whole.created_at, now)
    else:
        conclusion, age_problem = last_whole, None
    if conclusion is None:
        reasons.append("no completed nightly or dispatch whole-codebase run on main yet")
    elif conclusion != "success":
        reasons.append("the latest whole-codebase run on main concluded %s" % conclusion)
    if age_problem is not None:
        reasons.append(age_problem)

    if winner is not None and conclusion == "success" and age_problem is None:
        return Decision(
            True,
            "tree %s is PR head %s's tree: ci run %s succeeded on it, and the "
            "latest whole-codebase run on main succeeded" % (
                merge_tree[:12], winner.head_sha[:12], winner.run_id),
            winner.run_id)
    return Decision(False, "; ".join(reasons), None)


# --------------------------------------------------------------------------
# gathering the facts
# --------------------------------------------------------------------------

def _dig(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _tree_sha(commit: Any, what: str) -> str:
    tree = _dig(commit, "tree", "sha")
    if not isinstance(tree, str) or not tree:
        raise ValueError("%s has no tree.sha" % what)
    return tree


def _runs(listing: Any) -> list[dict[str, Any]]:
    """``workflow_runs`` of a list-runs response, or an error if it isn't one.

    A body of the wrong shape (an error message that arrived with a 200, say)
    must not read as "no runs", which is a meaningful answer.
    """
    found = _dig(listing, "workflow_runs")
    if not isinstance(found, list) or not all(isinstance(r, dict) for r in found):
        raise ValueError("response has no workflow_runs list")
    return found


def _parse_when(value: Any) -> datetime | None:
    """An aware datetime from an ISO-8601 string, or None for anything else.

    A timestamp without a timezone is refused rather than assumed to be UTC.
    """
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo is not None else None


def _run_key(run: dict[str, Any]) -> tuple[datetime, int]:
    when = _parse_when(run.get("created_at"))
    if when is None:
        raise ValueError("a run has no usable created_at, so runs cannot be ordered")
    ident = run.get("id")
    return when, ident if _is_int(ident) else 0


def _newest(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The most recently created run -- by timestamp, never by list position."""
    if not runs:
        return None
    if len(runs) == 1:
        return runs[0]
    return max(runs, key=_run_key)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _artifacts(api: Api, run_id: int, merge_tree: str) -> tuple[Artifact, ...]:
    """Run ``run_id``'s artifacts named ``tested-tree-<merge_tree>``, unjudged.

    A body of the wrong shape raises, as ``_runs`` does: it must not read as
    "no artifact", which is a real answer.
    """
    listing = api("actions/runs/%d/artifacts?name=%s%s"
                  % (run_id, TESTED_TREE_ARTIFACT, merge_tree))
    found = _dig(listing, "artifacts")
    if not isinstance(found, list) or not all(isinstance(a, dict) for a in found):
        raise ValueError("response has no artifacts list")
    out = []
    for item in found:
        expired = item.get("expired")
        owner = _dig(item, "workflow_run", "id")
        out.append(Artifact(_text(item.get("name")),
                            expired if isinstance(expired, bool) else None,
                            owner if _is_int(owner) else None))
    return tuple(out)


def _candidate(api: Api, head: str, merge_tree: str) -> Candidate:
    tree = _tree_sha(api("git/commits/%s" % head), "PR head %s" % head[:12])
    run = _newest(_runs(api("actions/workflows/ci.yml/runs?head_sha=%s&event=pull_request" % head)))
    if run is None:
        return Candidate(head, tree, None, None)
    run_id = run["id"] if _is_int(run.get("id")) else None
    # `conclusion` is null while a run (or a re-run) is in flight; a status that
    # contradicts a stale conclusion is read as unfinished.
    status = run.get("status")
    conclusion = run.get("conclusion")
    if (status is not None and status != "completed") or not isinstance(conclusion, str) or not conclusion:
        conclusion = None
    attempt = run.get("run_attempt")
    return Candidate(
        head, tree, run_id, conclusion,
        run_event=_text(run.get("event")),
        run_head_sha=_text(run.get("head_sha")),
        run_attempt=attempt if _is_int(attempt) else 0,
        run_created_at=_parse_when(run.get("created_at")),
        artifacts=() if run_id is None else _artifacts(api, run_id, merge_tree))


def _last_whole(api: Api) -> Nightly | None:
    """The newest completed ``schedule``/``workflow_dispatch`` run, or None.

    Two queries, ``per_page=1`` each, because GitHub's ``event`` filter takes one
    value. An exception from either propagates (see the module docstring); an
    empty answer from one is simply "that event has not run".
    """
    newest: dict[str, Any] | None = None
    for event in WHOLE_CODEBASE_EVENTS:
        found = _newest(_runs(api(
            "actions/workflows/ci.yml/runs?branch=%s&status=completed"
            "&event=%s&per_page=1" % (MAIN, event))))
        if found is None:
            continue
        # The filter is asked for, and checked: a run of another event is not a
        # whole-codebase run. (Absent is tolerated here -- these fields are
        # redundant with the query -- but a contradiction is not.)
        if found.get("event") not in (None, event):
            raise ValueError("a %r query returned a %r run" % (event, found.get("event")))
        # Unlike the two checks above, a run that does not NAME its branch is not
        # accepted: which branch a result is about is the whole question.
        if found.get("head_branch") != MAIN:
            raise ValueError("a branch=%s query returned a run on branch %r"
                             % (MAIN, found.get("head_branch")))
        newest = found if newest is None else max((newest, found), key=_run_key)
    if newest is None:
        return None
    status = newest.get("status")
    conclusion = newest.get("conclusion")
    if (status is not None and status != "completed") or not isinstance(conclusion, str) or not conclusion:
        return None
    return Nightly(conclusion, _parse_when(newest.get("created_at")))


def gather(api: Api, sha: str) -> tuple[str, list[Candidate], Nightly | None]:
    """Collect (merge commit tree, one Candidate per associated PR head, nightly).

    The nightly is a ``Nightly`` (conclusion plus creation time), or None when no
    whole-codebase run has completed. Age is not judged here: ``decide`` does it,
    against an injectable clock.

    ``api(path)`` returns parsed JSON for ``repos/<repo>/<path>``. Raises on any
    transport or shape problem; see the module docstring for why nothing is
    caught here.
    """
    merge_tree = _tree_sha(api("git/commits/%s" % sha), "this commit")
    # It names the artifact asked for, so it goes into a URL: an object id or
    # nothing, never a string the API happened to return.
    if not _OBJECT.fullmatch(merge_tree):
        raise ValueError("this commit's tree.sha is not an object id")
    pulls = api("commits/%s/pulls" % sha)
    if not isinstance(pulls, list):
        raise ValueError("commits/<sha>/pulls did not return a list")
    heads: list[str] = []
    for item in pulls:
        head = _dig(item, "head", "sha")
        # A head that is not a plain commit id is not interpolated into a URL,
        # and could not be proof anyway: it is dropped. So is a PR whose base is
        # not main (or names no base): see the module docstring.
        if (isinstance(head, str) and _COMMIT.fullmatch(head) and head not in heads
                and _dig(item, "base", "ref") == MAIN):
            heads.append(head)
    candidates = [_candidate(api, head, merge_tree) for head in heads]
    return merge_tree, candidates, _last_whole(api)


# --------------------------------------------------------------------------
# the base commit's mutation verdict
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BaseVerdict:
    """Was ``mutation`` green on the base commit's push run, and in one word why.

    ``word`` is written to ``$GITHUB_OUTPUT`` and spliced into the planner's
    reason line, so it is either one of this module's own words or an API
    status/conclusion that is a plain lower-case word (``_WORD``):

    * ``success`` -- the only word that comes with ``green=True``;
    * the job's ``conclusion`` when it completed otherwise (``failure``,
      ``cancelled``, ``skipped``, ``timed_out``, ...), or its ``status`` when it
      has not completed (``queued``, ``in_progress``, ``waiting``, ...);
    * ``unknown`` -- a status or conclusion that is absent or not such a word;
    * ``nightly-<conclusion>`` -- the job was green, but the newest completed
      whole-codebase run on ``main`` concluded otherwise (``nightly-failure``,
      ``nightly-cancelled``, ..., ``nightly-unknown``);
    * ``no-nightly`` -- the job was green, and no whole-codebase run on
      ``main`` has completed;
    * ``no-base`` -- ``before`` is empty or all zeros (the push made the ref);
    * ``invalid-base`` -- ``before`` is not a full lower-case commit id;
    * ``missing-run`` -- no ``ci`` push run on ``main`` for that commit;
    * ``missing-job`` -- that run's latest attempt has no ``mutation`` job;
    * ``error`` -- anything raised: transport, HTTP status (a 403/429 rate
      limit included), JSON, a listing of the wrong shape or longer than one
      page, a run that contradicts the query, two ``mutation`` jobs, missing
      credentials, a command line that does not parse.
    """

    green: bool
    word: str


def _word(value: Any) -> str:
    return value if isinstance(value, str) and _WORD.fullmatch(value) else "unknown"


def _page(listing: Any, key: str) -> list[dict[str, Any]]:
    """``listing[key]`` when it is a list of objects and the whole of the answer.

    A ``total_count`` larger than what came back means the item that matters
    may be on a page never fetched; a missing or non-integer one means the
    shape is not the one this was checked against. Both raise.
    """
    found = _dig(listing, key)
    if not isinstance(found, list) or not all(isinstance(i, dict) for i in found):
        raise ValueError("response has no %s list" % key)
    total = _dig(listing, "total_count")
    if not _is_int(total):
        raise ValueError("a %s listing has no integer total_count" % key)
    if total > len(found):
        raise ValueError("a %s listing holds %d but returned %d: more than one page"
                         % (key, total, len(found)))
    return found


def _unusable_base(before: Any) -> BaseVerdict | None:
    """The verdict for a ``before`` no request should be made for, else None."""
    if not isinstance(before, str) or not before or _ZERO.fullmatch(before):
        return BaseVerdict(False, "no-base")
    if not _COMMIT.fullmatch(before):
        return BaseVerdict(False, "invalid-base")
    return None


def base_mutation(api: Api, before: str) -> BaseVerdict:
    """The ``mutation`` job's verdict on the newest ``ci`` push run of ``before``.

    Raises on any transport or shape problem, like ``gather``; ``main`` turns
    that into ``error``. Only ``status == completed`` with ``conclusion ==
    success`` is green, and then only beside a green newest whole-codebase
    run, which is asked for last: a base that is red on its own says so first.
    """
    unusable = _unusable_base(before)
    if unusable is not None:
        return unusable
    run = _newest(_page(api(
        "actions/workflows/ci.yml/runs?branch=%s&event=push&head_sha=%s&per_page=%d"
        % (MAIN, before, PER_PAGE)), "workflow_runs"))
    if run is None:
        return BaseVerdict(False, "missing-run")
    # The filters are asked for, and checked: a run of another event, branch
    # or commit says nothing about this base.
    for key, want in (("event", "push"), ("head_branch", MAIN), ("head_sha", before)):
        if run.get(key) != want:
            raise ValueError("the base query returned a run whose %s is %r" % (key, run.get(key)))
    run_id = run.get("id")
    # _is_int's test, spelled out so the type checker sees an int below.
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        raise ValueError("the base run has no integer id")
    jobs = _page(api("actions/runs/%d/jobs?filter=latest&per_page=%d" % (run_id, PER_PAGE)),
                 "jobs")
    named = [j for j in jobs if j.get("name") == MUTATION_JOB]
    if not named:
        return BaseVerdict(False, "missing-job")
    if len(named) > 1:
        raise ValueError("the base run lists %d jobs named %s" % (len(named), MUTATION_JOB))
    job = named[0]
    owner = job.get("run_id")
    if owner is not None and not (_is_int(owner) and owner == run_id):
        raise ValueError("the base run's %s job says it belongs to run %r"
                         % (MUTATION_JOB, owner))
    status, conclusion = job.get("status"), job.get("conclusion")
    if status != "completed":
        return BaseVerdict(False, _word(status))
    if conclusion != "success":
        return BaseVerdict(False, _word(conclusion))
    nightly = _last_whole(api)
    if nightly is None:
        return BaseVerdict(False, "no-nightly")
    if nightly.conclusion != "success":
        return BaseVerdict(False, "nightly-" + _word(nightly.conclusion))
    return BaseVerdict(True, "success")


# --------------------------------------------------------------------------
# talking to GitHub
# --------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the token goes to api.github.com and nowhere else."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect)


def make_api(repo: str, token: str, *, opener: Any = None,
             timeout: float = TIMEOUT) -> Api:
    """An ``api(path)`` for ``repo`` that returns parsed JSON and raises otherwise."""
    http = opener if opener is not None else _default_opener()

    def api(path: str) -> Any:
        req = urllib.request.Request(  # noqa: S310  API_ROOT is a literal https prefix
            API_ROOT + repo + "/" + path,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "boost-ci-proven-tree",
            })
        with http.open(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    return api


# --------------------------------------------------------------------------
# the CLI
# --------------------------------------------------------------------------

class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse would print usage and exit 2. This script always exits 0.
        raise UsageError(message)


def _instant(text: str) -> datetime:
    when = _parse_when(text)
    if when is None:
        raise argparse.ArgumentTypeError("needs an ISO-8601 timestamp with a timezone")
    return when


def _oneline(text: str) -> str:
    """One bounded line: no newline of any kind, no control character."""
    flat = " ".join("".join(c if c.isprintable() else " " for c in text).split())
    return flat if len(flat) <= MAX_REASON_CHARS else flat[:MAX_REASON_CHARS] + "..."


def _parser() -> _Parser:
    parser = _Parser(prog="ci_proven_tree.py", description="Decide whether a push to "
                     "main may skip the full mutation run.")
    parser.add_argument("--sha", required=True, help="the commit that landed on main")
    parser.add_argument("--now", type=_instant, default=None,
                        help="ISO-8601 instant to age the nightly against "
                             "(tests only; default: the real clock)")
    parser.add_argument("--before", default="",
                        help="the push's base commit (github.event.before); its ci "
                             "push run's `mutation` verdict is reported, never "
                             "assumed. Empty or absent: not green")
    return parser


def _report(exc: Exception, token: str) -> None:
    detail = _oneline(str(exc))
    print("ci_proven_tree: %s: %s" % (type(exc).__name__,
                                      detail.replace(token, "***") if token else detail),
          file=sys.stderr)


def _base_for(argv: list[str] | None, api: Api | None, env: Mapping[str, str]) -> BaseVerdict:
    """``base_mutation`` for ``--before``, with every failure caught as ``error``.

    Its own parse and its own catch, so nothing in the proven decision -- an
    error, a bad ``--sha`` -- can reach this answer, and nothing here can
    reach that one.
    """
    token = (env.get("GITHUB_TOKEN") or "").strip()
    try:
        before = _parser().parse_args(argv).before
        unusable = _unusable_base(before)
        if unusable is not None:        # answered without credentials or a request
            return unusable
        if api is None:
            repo = (env.get("GITHUB_REPOSITORY") or "").strip()
            if not token or not _REPO.fullmatch(repo):
                return BaseVerdict(False, "error")
            api = make_api(repo, token)
        return base_mutation(api, before)
    except Exception as exc:
        _report(exc, token)
        return BaseVerdict(False, "error")


def _decide_for(argv: list[str] | None, api: Api | None, env: Mapping[str, str]) -> Decision:
    token = (env.get("GITHUB_TOKEN") or "").strip()
    try:
        args = _parser().parse_args(argv)
        if not _COMMIT.fullmatch(args.sha):
            return Decision(False, "--sha is not a full lower-case commit id")
        if api is None:
            repo = (env.get("GITHUB_REPOSITORY") or "").strip()
            if not token:
                return Decision(False, "GITHUB_TOKEN is not set")
            if not _REPO.fullmatch(repo):
                return Decision(False, "GITHUB_REPOSITORY is unset or malformed")
            api = make_api(repo, token)
        return decide(*gather(api, args.sha), now=args.now)
    except Exception as exc:
        _report(exc, token)
        return Decision(False, "error: %s" % type(exc).__name__)


def _append(path: str, text: str, label: str) -> None:
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        print("ci_proven_tree: cannot write %s: %s" % (label, type(exc).__name__),
              file=sys.stderr)


def main(argv: list[str] | None = None, *, api: Api | None = None,
         env: Mapping[str, str] | None = None) -> int:
    """Always returns 0; the verdict is in the outputs.

    With ``api`` injected, no credentials are read: the callable stands in for
    both the network and the token.
    """
    env = os.environ if env is None else env
    decision = _decide_for(argv, api, env)
    base = _base_for(argv, api, env)
    skip = "true" if decision.skip else "false"
    run_id = "" if decision.pr_run_id is None else str(decision.pr_run_id)
    reason = _oneline(decision.reason)
    green = "true" if base.green is True else "false"
    word = base.word if _BASE_WORD.fullmatch(base.word) else "unknown"
    print("ci_proven_tree: skip=%s pr_run_id=%s base_mutation_green=%s base_mutation=%s -- %s"
          % (skip, run_id, green, word, reason))
    lines = "skip=%s\npr_run_id=%s\nbase_mutation_green=%s\nbase_mutation=%s\n" % (
        skip, run_id, green, word)
    if env.get("GITHUB_OUTPUT"):
        _append(env["GITHUB_OUTPUT"], lines, "GITHUB_OUTPUT")
    else:
        print(lines, end="")
    if env.get("GITHUB_STEP_SUMMARY"):
        _append(env["GITHUB_STEP_SUMMARY"],
                "### Proven-tree check\n\n- skip: `%s`\n- reason: %s\n"
                "- base commit's mutation: `%s` (green: `%s`)\n" % (skip, reason, word, green),
                "GITHUB_STEP_SUMMARY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
