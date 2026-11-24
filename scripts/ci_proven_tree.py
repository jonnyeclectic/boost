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
   first-attempt run (but see THE MUTATION VERDICT OF A RE-RUN below) that
   concluded ``success`` and was created at most 13 days
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
   ``workflow_dispatch``, whichever is newer) was created at most 48 hours
   before now, and its ``mutation`` job (latest attempt) concluded
   ``success``. This is the backstop for what a diff-scoped PR gate cannot
   see: a red nightly turns every push back into a full run until it is green
   again, and so does a *missing* one. The age bound is what makes "green"
   mean "recently": without it, a nightly that quietly stopped (workflow
   disabled, schedules dropped) would keep authorising skips on a months-old
   result. 48 hours tolerates one missed night and not two. The job, and
   not the run's conclusion where only ``tests-extended`` legs are red,
   because that run is also ci.yml's ``tests-extended`` (macOS and Windows
   on 3.13/3.14): read as a whole, one red or timed-out extended leg would
   put every later push on the full 26-shard mutation run and the full
   ``tests`` matrix until someone reran it, and that buys nothing -- a
   platform test failure says nothing about the mutation score, and every
   push runs those legs again itself before it can release. That is the
   only red looked past: a run red on any other job (a failed
   ``idle-nightly``) beside a green ``mutation`` reads
   ``red_beyond_extended``, as the run's conclusion read before. The
   nightly diff shadow's two jobs (``nightly-shadow-base`` and the
   ``mutation-advisory-shard`` legs) are dropped from the page first: they
   are job-level ``continue-on-error``, so a red one never made the run red
   and never decides a verdict; it neither explains a red run nor refuses
   one.
   ci-failure-issue.yml still alarms on the run's conclusion, so a red
   extended leg on the nightly is reported all the same.
   An *idle* nightly (see below) counts, but never on its own word: a run
   carrying an ``inherited-tree-`` marker is green here only when the walk
   that let it skip, re-run from that run's own ``created_at``, still finds
   the same real run green on the same commit and tree -- and then, like any
   other, only when its own ``mutation`` job is green too. Anything else reads
   as ``unproven_skip``, which every ``== "success"`` check already refuses.
   Not counting skips at all would have been the simpler rule and the wrong
   trade: a real run older than 48 h fails this fact, so from the second
   idle night on every proven push would pay the full run it exists to save
   -- and the skip is only ever taken over bytes a green real run scored.

What ``skip=true`` lets a push skip is ``tests`` (the matrix the PR run ran),
the mutation shards and the coverage collection. ``tests-extended`` never reads
it: no pull request runs those legs, so no PR run can have proven them, and
every push to ``main`` runs them before publish.yml can release.

THE MUTATION VERDICT OF A RE-RUN (approved 2026-11-24 for the mutation verdict
only; docs/superpowers/plans/2026-10-31-ci-speed.md, review focus 4). A PR run
re-run for a reason that is not mutation -- typically a macOS ``tests`` cell
cancelled with no steps after ~52 min, then "re-run failed jobs" -- used to
send its merge push to the full mutation run (24 shards then): 42430658365 (push 42444697189,
179.6 min) and 41861286489 (push 41892921723, 187.7 min). Its tests are still
not first-attempt evidence, so such a run never gives ``skip=true``. But when
every mutation job of it executed exactly once, in attempt 1, and passed
there (``_mutation_carried``), its mutation verdict is first-attempt evidence,
and ``decide`` returns ``mutation_only``: ``skip=false`` (this push runs its
tests) with ``mutation_proven=true`` and the run's id. Facts 1 and 3 and the
rest of fact 2 hold exactly as for a full proof. A re-run that executed any
mutation job again -- 42463209202 re-ran them all in attempt 2, then only
``lint`` in attempt 3 -- proves nothing, and neither does one whose first
mutation verdict was red (41893440023, 42674048836). ``gather`` reads every
attempt's jobs (``actions/runs/{id}/attempts/{n}/jobs``, paginated) only for
a green re-run of this tree of at most ``MAX_ATTEMPTS`` attempts, and any
error there is an error like any other: nothing is proven.

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
  be 1 for ``skip=true``: a re-run is the "cancelled or re-run" case in the plan's
  review focus. Since 2026-11-24 a re-run may still prove the mutation verdict
  alone (see above), and only on its attempts' own job listings: every
  mutation job carried over from attempt 1, green there. A run object that
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
``mutation`` job of the newest completed whole-codebase run on ``main``
(fact 3's, by the same ``_last_whole`` query) concluded ``success`` too. The
base's push run may itself have planned ``none`` and inherited; a red nightly
is the full run that says the inherited verdict was wrong, and a push run's
green must not hide it.
Its age is not judged here: the question is whether a red result is being
hidden, not whether a green one is recent. Everything else -- no base (empty,
all-zero), no run, no such job, still running, any other conclusion, a red or
missing nightly, more jobs or runs than one page holds, any API, HTTP, JSON or
timeout error, a rate limit -- is not green. ci.yml holds a proven push to
this verdict as well as a push its diff calls irrelevant: the PR run that
proves a tree diffed against the same base, and planned ``none`` whenever its
own diff was irrelevant. It is gathered and caught apart from the decision
above: an error in either never changes the other's answer.

A THIRD QUESTION: MAY TONIGHT'S NIGHTLY INHERIT THE LAST REAL ONE? (``idle``,
run by scripts/ci_idle_nightly.py in ci.yml's ``idle-nightly`` job.) On
2026-11-02 run 41512174636 mutated ``b294d51c`` in full and passed; on
2026-11-03 run 41682296301 mutated the same commit again, all 24 shards,
because nothing had merged in between. ``idle`` lets a ``schedule`` run plan
``none`` instead, and only when, walking the whole-codebase runs of ``ci.yml``
on ``main`` that were created before it, newest first:

* every run passed over is a completed, first-attempt, green *skip* of this
  same commit and tree that names the run found below as its source -- a skip
  is walked past, never inherited from, so the clock cannot restart on one;
* the first run that is not a skip is the newest *real* run R, and R is
  completed, first-attempt, green, of this same commit (so any push since, proven
  or not, makes the next nightly full), its marker names this same tree, its
  ``mutation`` job completed with ``success``, and it was created less than
  ``MAX_INHERIT_AGE`` (7 days) before the run deciding -- the clock runs from R,
  never from the last skip.

"Green" in both bullets is the run's own conclusion, and for R its ``mutation``
job as well. That is stricter than fact 3, which looks past a red
``tests-extended`` leg on the newest run (and nothing else) so that one cannot
put every push on the full run. It is stricter on purpose: an idle night
*replaces* a full mutation run, so a wrong yes reports green over bytes no run
scored this week, while fact 3 only lets a push skip what its own PR run
already proved. A night after a whole-codebase run with one red platform leg
therefore plans full.

Anything else the walk reaches stops it and plans full: a run still going, a
red, cancelled or re-run one (red is never looked past, whatever lies behind
it), a run with no marker or two, an expired or malformed one, a window with no
real run. "Reaches" is the limit, and it is deliberate. The walk judges runs in
``created_at`` order, newest first, and ends at R; a whole-codebase run created
before R is never read, even one still going tonight or one that went red after
R went green. ``ci-<event>-<sha>`` puts a dispatch and a nightly of one commit
in different concurrency groups, so the two can overlap. R scored these same
bytes in full and green, so such a run is a second measurement that disagrees,
not code nothing has seen. It is also the order fact 3 reads
(``_newest_completed_whole``). And refusing on it would let a *later* re-run of
an older run unprove, through ``_proven_skip``, a skip that held when it was
taken. A marker is how a run says what it was. mutation-plan uploads
``mutated-tree-<tree>`` when its plan's gate set is ``full`` and
``inherited-tree-<tree>-from-<R's id>`` when it planned an idle ``none``, both
before any shard starts and so before the outcome is known: a red real run is
marked exactly like a green one, and is found, read, and refused. Only
``schedule`` may skip; a ``workflow_dispatch`` always plans full, and is the
lever for clearing a red nightly. Every failure to answer -- an HTTP error, a
listing longer than its page, an undated run, a run of another branch or event,
this run missing from the listing -- is ``idle=false`` with ``error: <type>``,
the same discipline as the decision above.

CLI. ``ci_proven_tree.py --sha SHA [--before SHA]`` reads ``GITHUB_REPOSITORY``
and ``GITHUB_TOKEN``, appends ``skip=true|false``, ``pr_run_id=<id or empty>``,
``base_mutation_green=true|false``, ``base_mutation=<word>`` (see
``base_mutation``) and ``mutation_proven=true|false`` to ``$GITHUB_OUTPUT``,
and appends the reason to ``$GITHUB_STEP_SUMMARY``. ``mutation_proven`` is
true whenever ``skip`` is, and also on a re-run that proves the mutation
verdict alone; ``pr_run_id`` names the PR run whenever ``mutation_proven`` is
true, and is empty otherwise. It
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
The idle walk's two, on 2026-11-04: ``actions/workflows/ci.yml/runs?branch=
main&event=schedule&created=%3E%3D2026-10-27&per_page=100`` returned
``total_count`` 2 (41682296301 and 41512174636, both ``head_branch`` main) and
the ``workflow_dispatch`` twin 0; ``actions/runs/41682296301/artifacts?
per_page=100`` returned ``total_count`` 27 with 27 ``artifacts``, each carrying
``name``, ``expired`` and ``workflow_run.id``.
A whole-codebase run's jobs come from the same endpoint: on 2026-11-04,
``actions/runs/41682296301/jobs?filter=latest&per_page=100`` (the 11-03
nightly) returned ``total_count`` 36 with 36 ``jobs``, the skipped ones
included, and one named ``mutation`` (completed, success, ``run_id``
41682296301). A re-run keeps the jobs it did not re-run, so re-running one
red ``tests-extended`` leg leaves the run's ``mutation`` listed: push run
39729763526 (three attempts) listed 34 jobs under ``filter=latest``, every one
with ``run_attempt`` 3, ``lint`` among them under a new job id but with its
attempt-1 ``started_at`` (05:44:42Z on 10-22) -- carried over, not re-run.
The re-run rule's one, on 2026-11-24: ``actions/runs/45263898738/attempts/
{1,2}/jobs?per_page=100`` returned ``total_count`` 46 and 46 ``jobs`` each,
every one carrying ``id``, ``run_id``, ``run_attempt`` (the attempt asked
for), ``name``, ``status``, ``conclusion``, ``created_at``, ``started_at`` and
``completed_at``; attempt 2's ``mutation`` (job 138090277492) was created at
23:22:57Z with attempt 1's (138089484031) start and end, 23:21:27Z and
23:22:18Z, while its re-run ``tests (macos-latest, 3.12)`` was created at
23:22:56Z and started at 23:23:00Z. ``actions/runs/42463209202/attempts/
{1,2,3}/jobs`` returned 44 each; attempt 3's ``mutation-shard (full, 0)``
was created at 11:48:27Z with attempt 2's start (10:38:55Z), not attempt 1's
(08:40:24Z).
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
# codebase (the full mutation plan, and ci.yml's `tests-extended` legs);
# whichever finished last is the current state of "everything", and its
# `mutation` job is the verdict read from it (fact 3).
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

#: The rest of a pull request run's mutation verdict, as the jobs API names
#: them: the planner (no matrix) and each shard leg, a matrix job with no
#: `name:` over ``{"set": ..., "index": N}``, so ``mutation-shard (full, 3)``
#: -- the shape every recorded PR run's attempts listed. ``_is_mutation_job``
#: says which jobs a re-run must have carried over;
#: test_the_rerun_rules_job_names_are_ci_ymls ties both names to ci.yml.
PLAN_JOB = "mutation-plan"
SHARD_JOB = "mutation-shard"
_FULL_SHARD = re.compile(re.escape(SHARD_JOB) + r" \(full, (0|[1-9][0-9]{0,3})\)")

#: The most attempts of one PR run that are read. Each costs a jobs request
#: (two past 100 jobs), inside `proven`'s 5-minute job cap; the re-run PR runs
#: on record stopped at attempt 3. A run re-run more often than this proves
#: nothing, which costs one mutation run.
MAX_ATTEMPTS = 5

#: Pages of one attempt's job listing that are read. A pull request run lists
#: 44-46 jobs (a full plan), plus up to 16 diff shards in shadow mode: one page.
#: A listing that does not end inside this many is an error, not a guess.
MAX_JOB_PAGES = 3

#: One page. Asked for explicitly, and a listing whose total_count says it
#: holds more than came back is not read: the newest run, or the one job named
#: `mutation`, could be on the page that was never fetched.
PER_PAGE = 100

# What a whole-codebase run says it was, in an artifact name (contents cannot
# be read without following a redirect, which make_api refuses). ci.yml's
# mutation-plan spells the same prefixes; the tests of those steps read them
# from here. `mutated-tree-<tree>`: the plan's gate set was `full`.
# `inherited-tree-<tree>-from-<run id>`: an idle nightly planned `none` on the
# strength of that run. Neither starts with the other or with TESTED_TREE_ARTIFACT.
MUTATED_TREE_ARTIFACT = "mutated-tree-"
INHERITED_TREE_ARTIFACT = "inherited-tree-"

# How long a real whole-codebase run's verdict may be inherited, measured from
# its created_at to the created_at of the run deciding. "Less than": a run
# exactly 7 days older is not inherited. The age bound is drift outside the
# tree -- the runner image, setup-python's "3.14" patch release, the unpinned
# `pip install sqlite-vec || true` -- which a byte-identical tree cannot
# rule out, so a week of it is the most a skip may lean on.
MAX_INHERIT_AGE = timedelta(days=7)

# What `_last_whole` reports for a skip whose inheritance no longer holds. A
# plain word, so `decide` says "concluded unproven_skip" and `base_mutation`
# "nightly-unproven_skip" with no change to either.
UNPROVEN_SKIP = "unproven_skip"

#: ci.yml's macOS/Windows 3.13/3.14 job. A matrix job with no `name:`, so the
#: jobs API names each leg ``tests-extended (<os>, <python>)``. The one job
#: whose red fact 3 looks past (see fact 3).
EXTENDED_JOB = "tests-extended"

#: ci.yml's two jobs of the nightly diff shadow, as the jobs API names them:
#: ``nightly-shadow-base`` (no matrix) and each ``mutation-advisory-shard``
#: leg, a matrix job with no `name:` over ``{"set": "diff", "index": N}``
#: entries, so ``mutation-advisory-shard (diff, N)`` -- the shape
#: ``mutation-shard (full, 6)`` has on nightly 41682296301's page. Both
#: carry job-level ``continue-on-error: true``: a red one leaves the run's
#: conclusion alone and is evidence, never a verdict, so
#: ``_red_only_on_extended`` drops them before it reads the page -- once
#: completed with a conclusion; one that is not stays red. Matched
#: whole, never by a looser prefix: a name this misses stays in the red set,
#: and the run reads ``RED_BEYOND_EXTENDED`` -- the full-run direction.
#: tests/unit/test_ci_proven_tree.py ties both to ci.yml.
ADVISORY_JOB_NAMES = re.compile(
    r"nightly-shadow-base|mutation-advisory-shard \(diff, (?:0|[1-9][0-9]*)\)")

# What `_last_whole` reports for a whole-codebase run whose `mutation` job
# passed but whose own conclusion is red for a reason other than
# `tests-extended` legs: another job (`idle-nightly`, say) is red, or no job
# on the page is (the diff shadow's advisory jobs aside) and the run is red
# anyway. A plain word, like UNPROVEN_SKIP,
# so `base_mutation` says "nightly-red_beyond_extended".
RED_BEYOND_EXTENDED = "red_beyond_extended"

_RUN_ID = re.compile(r"[1-9][0-9]{0,19}")
_TREE_PART = r"(?P<tree>[0-9a-f]{40}(?:[0-9a-f]{24})?)"
_MUTATED_NAME = re.compile(re.escape(MUTATED_TREE_ARTIFACT) + _TREE_PART)
_INHERITED_NAME = re.compile(re.escape(INHERITED_TREE_ARTIFACT) + _TREE_PART
                             + r"-from-(?P<source>[1-9][0-9]{0,19})")

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
class Job:
    """One entry of a run attempt's job listing, as far as the re-run rule reads it.

    Every field is the entry's own, or ``None`` / ``""`` when it is absent or
    of the wrong type -- which ``_mutation_carried`` never reads as fine.
    """

    name: str
    run_id: int | None
    attempt: int | None
    status: str
    conclusion: str
    created_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None


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

    ``attempts`` is every attempt's job listing, attempt 1 first, and is read
    only for a re-run (``run_attempt`` 2 to ``MAX_ATTEMPTS``): it is what
    ``_mutation_carried`` judges. ``gather`` fills it only for a re-run that
    concluded ``success`` on this commit's tree, and empty -- the default --
    is "not read", which never proves anything.
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
    attempts: tuple[tuple[Job, ...], ...] = ()


@dataclass(frozen=True)
class Nightly:
    """The newest completed whole-codebase run: its mutation verdict, and when it began.

    ``conclusion`` is the run's ``mutation`` job's (its status when it has not
    completed), not the run's own: see fact 3 for why a red ``tests-extended``
    leg must not count. When ``mutation`` is green it can still be one of
    ``_last_whole``'s own words, ``RED_BEYOND_EXTENDED`` or ``UNPROVEN_SKIP``.
    ``created_at`` is the run's, an aware datetime, or
    ``None`` when the run's own value was missing, unparseable or had no
    timezone. ``decide`` never skips on ``None``.
    """

    conclusion: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class Decision:
    """The verdict ``main`` writes.

    ``skip`` is the whole proof: the PR run's first attempt passed, so this
    push skips its tests and its mutation run alike. ``mutation_only`` is the
    narrower one, only ever beside ``skip=False``: the PR run is a re-run, so
    its tests are not first-attempt evidence and this push runs them, but its
    mutation jobs all ran once, in attempt 1, and passed (``_mutation_carried``).
    ``pr_run_id`` names the PR run in both cases and is ``None`` otherwise.
    """

    skip: bool
    reason: str
    pr_run_id: int | None = None
    mutation_only: bool = False

    @property
    def mutation_proven(self) -> bool:
        """Is this push's mutation verdict the PR run's? True for both proofs."""
        return self.skip is True or self.mutation_only is True


def _is_int(value: Any) -> bool:
    # bool is an int subclass, and a JSON `true` must not read as run number 1.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_mutation_job(name: str) -> bool:
    """Is a PR run's job of this name one the mutation verdict is made of?

    ``mutation-plan``, ``mutation`` and every ``mutation-shard`` leg, whatever
    its set (``full`` or ``diff``), and the bare ``mutation-shard`` a skipped
    matrix is listed as. Never a looser prefix: ``mutation-advisory-shard`` is
    skipped on every pull request, and a re-run re-evaluates a skipped job
    with a fresh ``started_at`` -- matched, it would refuse every re-run.
    Matching every shard name, not only ``full`` ones, is the strict
    direction: each one matched must be green in attempt 1 and carried after.
    """
    return (name in (PLAN_JOB, MUTATION_JOB, SHARD_JOB)
            or name.startswith(SHARD_JOB + " ("))


def _mutation_jobs(jobs: tuple[Job, ...], run_id: int, attempt: int) -> dict[str, Job] | str:
    """Attempt ``attempt``'s mutation jobs by name, or why the listing cannot say.

    A name listed twice, or a job that does not say it is this run's job in
    this attempt (absent included), is a listing this rule was not checked
    against.
    """
    found: dict[str, Job] = {}
    for job in jobs:
        if not _is_mutation_job(job.name):
            continue
        if job.name in found:
            return "attempt %d lists %s twice" % (attempt, job.name)
        if job.run_id != run_id or job.attempt != attempt:
            return "attempt %d lists a %s that does not say it is run %d's attempt %d" % (
                attempt, job.name, run_id, attempt)
        found[job.name] = job
    return found


def _mutation_carried(run_id: int, attempts: tuple[tuple[Job, ...], ...]) -> str | None:
    """Did every mutation job of this re-run execute once, in attempt 1, and pass?

    None when it did; otherwise why not, as a clause. ``attempts`` holds every
    attempt's job listing, attempt 1 first. The rule (approved 2026-11-24,
    docs/superpowers/plans/2026-10-31-ci-speed.md, review focus 4):

    * attempt 1 ran ``mutation-plan``, ``mutation`` and full shards
      ``0..n-1`` (``n`` at least 1), and every mutation job in it
      (``_is_mutation_job``) completed with ``success``, has a start and an
      end time, and was created no later than it started (it ran there).
      So a PR that planned no shards is refused (its bare
      ``mutation-shard`` is ``skipped``), and so is a run whose first
      verdict was red, whatever a later attempt made of it;
    * every later attempt lists exactly the same mutation jobs, and each copy
      is attempt 1's execution carried over: completed ``success``, the same
      ``started_at`` and ``completed_at`` as attempt 1's, and a ``created_at``
      after that start. GitHub copies a job a re-run does not run into the new
      attempt under a new id, keeping the old start and end and stamping the
      new attempt's creation time (45263898738, 42430658365, 41861286489). A
      job that ran again starts after its new attempt was created, so it fails
      both tests.

    Comparing with attempt 1's copy, rather than with the latest attempt's
    start, is the point: 42463209202 re-ran every mutation job in attempt 2
    and only ``lint`` in attempt 3, so attempt 3's copies all started before
    attempt 3 did -- carried, but carried from attempt 2. Those timestamps are
    observed, not documented by GitHub; a copy that does not match them is
    refused, which costs one mutation run.
    """
    if len(attempts) < 2:
        return "no later attempt's jobs were read"
    first = _mutation_jobs(attempts[0], run_id, 1)
    if isinstance(first, str):
        return first
    if PLAN_JOB not in first or MUTATION_JOB not in first:
        return "attempt 1 ran no %s or no %s job" % (PLAN_JOB, MUTATION_JOB)
    full = sorted(int(m[1]) for name in first if (m := _FULL_SHARD.fullmatch(name)))
    if not full or full != list(range(len(full))):
        return "attempt 1's full mutation shards are not 0 to n-1"
    for name, job in sorted(first.items()):
        if job.status != "completed" or job.conclusion != "success":
            return "attempt 1's %s is %s/%s" % (name, _word(job.status), _word(job.conclusion))
        if job.started_at is None or job.completed_at is None:
            return "attempt 1's %s has no start or end time" % name
        # Where it ran, so created no later than it started -- the converse
        # of the carried-over test below, and what every recorded one shows.
        if job.created_at is None or job.created_at > job.started_at:
            return "attempt 1's %s was created after it started, so it did not run " \
                   "there" % name
    for attempt, listing in enumerate(attempts[1:], start=2):
        later = _mutation_jobs(listing, run_id, attempt)
        if isinstance(later, str):
            return later
        if set(later) != set(first):
            return "attempt %d's mutation jobs are not attempt 1's" % attempt
        for name, job in sorted(later.items()):
            one = first[name]
            if job.status != "completed" or job.conclusion != "success":
                return "attempt %d's %s is %s/%s" % (
                    attempt, name, _word(job.status), _word(job.conclusion))
            if (job.started_at is None or job.started_at != one.started_at
                    or job.completed_at != one.completed_at):
                return "%s ran again in attempt %d" % (name, attempt)
            if job.created_at is None or not job.created_at > job.started_at:
                return "attempt %d's %s was not created after it started, so it is not " \
                       "a carried-over copy" % (attempt, name)
    return None


def _rerun_problem(cand: Candidate) -> str | None:
    """Why this re-run does not prove its tree's mutation, or None when it does."""
    attempt = cand.run_attempt
    if not _is_int(attempt) or attempt < 1:
        return "only a first attempt, or a re-run whose mutation jobs all ran in it, counts"
    if attempt > MAX_ATTEMPTS:
        return "a run re-run more than %d times is not read" % (MAX_ATTEMPTS - 1)
    run_id = cand.run_id
    # _is_int's test, spelled out so the type checker sees an int below.
    if len(cand.attempts) != attempt or not isinstance(run_id, int) or isinstance(run_id, bool):
        return "its attempts' job listings were not all read"
    return _mutation_carried(run_id, cand.attempts)


#: What ``_judge`` says a candidate proves: everything this push would run
#: again, its mutation verdict alone, or nothing.
FULL = "full"
MUTATION_ONLY = "mutation"


def _judge(merge_tree: str, cand: Candidate, now: datetime) -> tuple[str | None, str]:
    """What does this candidate prove? Returns (FULL | MUTATION_ONLY | None, why)."""
    head = (cand.head_sha or "?")[:12]
    if not cand.head_sha:
        return None, "a candidate has no head sha"
    if not cand.head_tree:
        return None, "PR head %s: its tree is unknown" % head
    if cand.head_tree != merge_tree:
        return None, "PR head %s: tree %s differs from this commit's %s" % (
            head, cand.head_tree[:12], merge_tree[:12])
    if not _is_int(cand.run_id):
        return None, "PR head %s: no ci pull_request run found" % head
    where = "PR head %s: ci run %s" % (head, cand.run_id)
    if cand.run_event != "pull_request":
        return None, "%s was a %r run, not pull_request" % (where, cand.run_event)
    run_head = cand.head_sha if cand.run_head_sha is None else cand.run_head_sha
    if run_head != cand.head_sha:
        return None, "%s is for head %s, not this one" % (where, run_head[:12] or "?")
    if cand.conclusion is None:
        return None, "%s has no conclusion yet (still running)" % where
    if cand.conclusion != "success":
        return None, "%s concluded %s" % (where, cand.conclusion)
    proof = FULL
    if cand.run_attempt != 1:
        # A re-run's tests are not first-attempt evidence; its mutation
        # verdict still is when no mutation job ran after attempt 1.
        problem = _rerun_problem(cand)
        if problem is not None:
            return None, "%s is attempt %s, and %s" % (
                where, cand.run_attempt or "unknown", problem)
        proof = MUTATION_ONLY
    # Last, so a run that is red or re-run is reported as that, not as old.
    if cand.run_created_at is None:
        return None, "%s: created_at unknown, so its age is too" % where
    age = now - cand.run_created_at
    if age > MAX_PR_RUN_AGE:
        return None, ("%s is %s days old; a PR run proves a tree for %d days, "
                      "while its coverage-report artifact (kept 14) still exists"
                      % (where, _days(age), MAX_PR_RUN_AGE.days))
    if age < -CLOCK_SKEW:
        return None, "%s: created_at is in the future (%sh ahead of this clock)" % (
            where, _hours(age))
    # The run is green, first-attempt (or carried its mutation jobs from
    # there) and fresh; did it build THIS tree? Only its own record says so:
    # the head tree matching is not enough, because the run may have merged
    # that head into another base (fact 2).
    want = TESTED_TREE_ARTIFACT + merge_tree
    named = [a for a in cand.artifacts
             if a.name == want and a.run_id in (None, cand.run_id)]
    if not named:
        return None, ("%s left no %s%s artifact, so nothing says it built this "
                      "tree (it may have merged the head into another base)"
                      % (where, TESTED_TREE_ARTIFACT, merge_tree[:12]))
    if not any(a.expired is False for a in named):
        return None, "%s: its %s%s artifact has expired" % (
            where, TESTED_TREE_ARTIFACT, merge_tree[:12])
    if proof == MUTATION_ONLY:
        return proof, ("%s succeeded on this exact tree at attempt %d: every mutation "
                       "job ran once, in attempt 1, and passed, so its mutation verdict "
                       "counts and its tests do not" % (where, cand.run_attempt))
    return proof, "%s succeeded on this exact tree" % where


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
    # A re-run that proves the mutation verdict alone. Kept in case no
    # candidate proves everything; its reason is kept as well, so a red
    # nightly behind it still says what it would have proven.
    partial: Candidate | None = None
    if not isinstance(merge_tree, str) or not merge_tree:
        reasons.append("this commit's tree is unknown")
    elif not candidates:
        reasons.append("no pull request into main is associated with this commit "
                       "(a direct push, or a PR aimed at another branch)")
    else:
        for cand in candidates:
            proof, why = _judge(merge_tree, cand, now)
            if proof == FULL:
                winner = cand
                break
            if proof == MUTATION_ONLY and partial is None:
                partial = cand
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
    elif conclusion == RED_BEYOND_EXTENDED:
        reasons.append("the latest whole-codebase run on main concluded %s: its mutation "
                       "job passed, but tests-extended legs are not all that was red"
                       % conclusion)
    elif conclusion != "success":
        reasons.append("the mutation job of the latest whole-codebase run on main "
                       "concluded %s" % conclusion)
    if age_problem is not None:
        reasons.append(age_problem)

    if winner is not None and conclusion == "success" and age_problem is None:
        return Decision(
            True,
            "tree %s is PR head %s's tree: ci run %s succeeded on it, and the "
            "latest whole-codebase run on main passed mutation" % (
                merge_tree[:12], winner.head_sha[:12], winner.run_id),
            winner.run_id)
    if partial is not None and conclusion == "success" and age_problem is None:
        # Fact 3 holds as it does for a full proof: the nightly backstop is
        # about the mutation score, which is exactly what this proves.
        return Decision(
            False,
            "mutation only: tree %s is PR head %s's tree, and ci run %s succeeded on "
            "it at attempt %d with every mutation job run once, in attempt 1, and "
            "green; the latest whole-codebase run on main passed mutation. A re-run's "
            "tests are not first-attempt proof, so this push runs them"
            % (merge_tree[:12], partial.head_sha[:12], partial.run_id, partial.run_attempt),
            partial.run_id, mutation_only=True)
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


def _job(item: dict[str, Any]) -> Job:
    def number(key: str) -> int | None:
        value = item.get(key)
        return value if _is_int(value) else None

    return Job(_text(item.get("name")), number("run_id"), number("run_attempt"),
               _text(item.get("status")), _text(item.get("conclusion")),
               _parse_when(item.get("created_at")), _parse_when(item.get("started_at")),
               _parse_when(item.get("completed_at")))


def _attempt_jobs(api: Api, run_id: int, attempt: int) -> tuple[Job, ...]:
    """Every job of run ``run_id``'s attempt ``attempt``, unjudged, or it raises.

    ``actions/runs/{id}/attempts/{n}/jobs``, page by page, never
    ``filter=all``: that lists every attempt's copies at once and overflowed
    one page on 42463209202 (132 jobs). The pages must add up to the
    ``total_count`` every one of them states -- a short page, a count that
    changes between pages, a job id seen twice, more than ``MAX_JOB_PAGES``
    pages or a listing of the wrong shape raises, as ``_page`` does: a job
    that matters could be the one that never came back.
    """
    found: list[dict[str, Any]] = []
    total: int | None = None
    for page in range(1, MAX_JOB_PAGES + 1):
        listing = api("actions/runs/%d/attempts/%d/jobs?per_page=%d&page=%d"
                      % (run_id, attempt, PER_PAGE, page))
        jobs = _dig(listing, "jobs")
        if not isinstance(jobs, list) or not all(isinstance(j, dict) for j in jobs):
            raise ValueError("response has no jobs list")
        count = _dig(listing, "total_count")
        if not _is_int(count) or (total is not None and count != total):
            raise ValueError("attempt %d's jobs listing has no steady integer total_count"
                             % attempt)
        total = count
        if not jobs:
            break
        found.extend(jobs)
        if len(found) >= count:
            break
    if len(found) != total:
        raise ValueError("attempt %d of run %d lists %s jobs, and %d came back"
                         % (attempt, run_id, total, len(found)))
    ids = [j.get("id") for j in found]
    if not all(_is_int(i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("attempt %d's jobs listing repeats a job or lacks an id" % attempt)
    return tuple(_job(j) for j in found)


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
    found = run.get("run_attempt")
    attempt = found if isinstance(found, int) and not isinstance(found, bool) else 0
    # A green re-run of this tree is asked what each attempt ran: the only
    # requests beyond what a first attempt costs, and only where they can
    # matter. Everything is judged again in `decide`.
    attempts: tuple[tuple[Job, ...], ...] = ()
    if (run_id is not None and conclusion == "success" and tree == merge_tree
            and 2 <= attempt <= MAX_ATTEMPTS):
        attempts = tuple(_attempt_jobs(api, run_id, n) for n in range(1, attempt + 1))
    return Candidate(
        head, tree, run_id, conclusion,
        run_event=_text(run.get("event")),
        run_head_sha=_text(run.get("head_sha")),
        run_attempt=attempt,
        run_created_at=_parse_when(run.get("created_at")),
        artifacts=() if run_id is None else _artifacts(api, run_id, merge_tree),
        attempts=attempts)


def _newest_completed_whole(api: Api) -> dict[str, Any] | None:
    """The newest completed ``schedule``/``workflow_dispatch`` run object, or None.

    Two queries, ``per_page=1`` each, because GitHub's ``event`` filter takes one
    value. An exception from either propagates (see the module docstring); an
    empty answer from one is simply "that event has not run". A newest run that
    is not completed, or has no conclusion, is None too: not yet a result.
    This is the one definition of "the newest completed whole-codebase run":
    ``_last_whole`` (fact 3 and the base) starts from it, and nightly_watch.py
    asks it and nothing else, so the alarm and the skip agree on which run is
    the newest; only ``_last_whole`` goes on to read the run's verdict.
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
    return newest


def _last_whole(api: Api) -> Nightly | None:
    """The newest completed whole-codebase run's verdict, as fact 3 and the base read it.

    The run is ``_newest_completed_whole``'s. Its verdict is its ``mutation``
    job's (latest attempt), and the run's own conclusion counts only as far as
    a ``tests-extended`` leg cannot explain it: the run is also ci.yml's
    ``tests-extended``, and a red platform leg says nothing about the score
    (fact 3). A completed whole-codebase run with no such job contradicts
    ci.yml, where it runs on every event under ``always()``, and raises. A job
    that has not completed is reported by its status.

    A red ``mutation`` is returned as it is, with no further request: red is
    never looked past, whatever the run was. A green one in a run that did
    not conclude ``success`` is then held to the same page, still with no
    further request: unless every job on it that is not green is a
    ``tests-extended`` leg, and there is one, the run reads
    ``RED_BEYOND_EXTENDED``. So fact 3 refuses whatever the run's conclusion
    alone refused, except a red extended leg. On a schedule or dispatch run
    the other jobs are ``idle-nightly``, ``mutation-plan``, the shards and
    ``mutation`` (on a schedule run also the diff shadow's
    ``nightly-shadow-base`` and ``mutation-advisory-shard`` legs, which are
    continue-on-error and dropped from the page before it is read:
    ``ADVISORY_JOB_NAMES``). ``mutation`` already goes red on a red plan or
    shard, so in practice this is a failed ``idle-nightly``. Its outputs are then
    empty and the plan full, so the green ``mutation`` beside it is a real
    measurement; it is refused anyway, because it is not the red fact 3 was
    written to look past. Then the run is asked what it was: a run marked
    only ``mutated-tree-`` (a real run), or one with
    no marker at all, is green -- every whole-codebase run before the idle
    nightly existed planned full, and after it a run that reaches its plan
    uploads a marker or fails. A run carrying an ``inherited-tree-`` marker
    (an idle nightly) is green only when it is that run's one marker, on its
    first attempt (an integer 1: a JSON ``true`` or ``1.0`` is not), and
    ``_proven_skip`` re-derives it; otherwise it concludes
    ``UNPROVEN_SKIP``, whatever its ``mutation`` job said. So a skip is green
    only when both hold, and the order of the two reads changes only which
    not-green word is reported, never whether it is green. The re-derivation
    reads the source run R as ``idle`` does -- R's run conclusion *and* its
    ``mutation`` job -- which is stricter than this function's own read of
    the newest run, on purpose (see ``_inherit``).

    A re-run of a skip is the case that makes "one marker" matter: its second
    attempt is not idle, plans full and uploads a ``mutated-tree-`` beside the
    first attempt's ``inherited-tree-``, and a listing cannot say which attempt
    left which. "Not idle" holds for both kinds of re-run, by two different
    checks. Re-run in full, ``idle-nightly`` runs again and ``idle`` refuses
    any attempt but 1. Re-run from a failed job, ``idle-nightly`` does not run
    again -- GitHub reuses the outputs of jobs that succeeded in the attempt
    before -- so ci.yml's scope step refuses that reused yes on
    ``GITHUB_RUN_ATTEMPT``. The cost of that rule falls on the obvious cleanup
    of an idle nightly red only on ``tests-extended``: "re-run failed jobs"
    turns it green on attempt 2, which reads ``UNPROVEN_SKIP`` here, so every
    push runs in full until the next nightly -- ci-failure-issue.yml's note
    says to leave such a run alone.
    """
    newest = _newest_completed_whole(api)
    if newest is None:
        return None
    ident = newest.get("id")
    # _is_int's test, spelled out so the type checker sees an int below.
    if not isinstance(ident, int) or isinstance(ident, bool):
        raise ValueError("the newest whole-codebase run has no integer id")
    created = _parse_when(newest.get("created_at"))
    jobs = _jobs(api, ident)
    job = _the_mutation_job(jobs, ident)
    if job is None:
        raise ValueError("whole-codebase run %d lists no %s job" % (ident, MUTATION_JOB))
    # A job that has not completed inside a completed run is a contradiction;
    # its status is what gets reported, and only `success` is green anyway.
    verdict = job.get("conclusion") if job.get("status") == "completed" else job.get("status")
    nightly = Nightly(_text(verdict) or "unknown", created)
    if nightly.conclusion != "success":
        return nightly
    # The run's own red is looked past for `tests-extended` legs and nothing
    # else -- read off the page just fetched, so at no extra request.
    if newest.get("conclusion") != "success" and not _red_only_on_extended(jobs, ident):
        return Nightly(RED_BEYOND_EXTENDED, created)
    markers = _markers(api, ident)
    if all(m.kind == "real" for m in markers):
        return nightly
    # _is_int first, as `_inherit` checks it: a JSON `true` or `1.0` equals 1.
    attempt = newest.get("run_attempt")
    if len(markers) != 1 or not _is_int(attempt) or attempt != 1 \
            or not _proven_skip(api, newest, markers[0]):
        return Nightly(UNPROVEN_SKIP, created)
    return nightly


# --------------------------------------------------------------------------
# an idle nightly: what it inherits, and from whom
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Marker:
    """What one whole-codebase run's artifact listing says the run was.

    ``kind`` is ``"real"`` (``mutated-tree-<tree>``) or ``"skip"``
    (``inherited-tree-<tree>-from-<source>``); ``source`` is the real run a
    skip named, None for a real run. ``expired`` is the entry's own flag, or
    None when it is absent or not a boolean -- which the walk does not read as
    live.
    """

    kind: str
    tree: str
    source: int | None
    expired: bool | None


@dataclass(frozen=True)
class Inheritance:
    """The walk's answer: the real run inherited (None: none may be), and why."""

    source: dict[str, Any] | None
    reason: str


@dataclass(frozen=True)
class Idle:
    """May this nightly plan ``none``? And if so, which real run it leans on.

    ``source_*`` are filled only with ``idle=True``, and only from values the
    walk checked: an integer id, an object id, an aware instant.
    """

    idle: bool
    reason: str
    source_run: int | None = None
    source_tree: str = ""
    source_created: datetime | None = None


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short(sha: Any) -> str:
    """The first 12 characters of an object id, or ``?`` for anything else."""
    return sha[:12] if isinstance(sha, str) and _OBJECT.fullmatch(sha) else "?"


def _markers(api: Api, run_id: int) -> list[Marker]:
    """Every marker run ``run_id``'s artifact listing holds, unjudged.

    The whole listing, one page: the name carries the tree, which is the thing
    being asked, so the server's ``name`` filter cannot be used. A marker of
    another run, or a name with a marker's prefix that does not parse, raises:
    the listing is not the shape this was checked against. How many markers
    is the caller's question -- a run that says two things says nothing, and
    each caller turns that into its own safe answer.
    """
    listing = api("actions/runs/%d/artifacts?per_page=%d" % (run_id, PER_PAGE))
    found: list[Marker] = []
    for item in _page(listing, "artifacts"):
        name = item.get("name")
        if not isinstance(name, str) or not name.startswith(
                (MUTATED_TREE_ARTIFACT, INHERITED_TREE_ARTIFACT)):
            continue
        owner = _dig(item, "workflow_run", "id")
        if owner is not None and not (_is_int(owner) and owner == run_id):
            raise ValueError("run %d's artifact listing holds another run's marker" % run_id)
        expired = item.get("expired")
        expired = expired if isinstance(expired, bool) else None
        real, skip = _MUTATED_NAME.fullmatch(name), _INHERITED_NAME.fullmatch(name)
        if real is not None:
            found.append(Marker("real", real["tree"], None, expired))
        elif skip is not None:
            found.append(Marker("skip", skip["tree"], int(skip["source"]), expired))
        else:
            raise ValueError("run %d carries a malformed marker" % run_id)
    return found


def _whole_window(api: Api, since: datetime) -> tuple[list[dict[str, Any]], str]:
    """Every whole-codebase run of ci.yml on main created since a floor, newest first.

    The floor is a UTC date a day before ``since - MAX_INHERIT_AGE``, so any
    run the walk may inherit from is inside it. No ``status`` filter: a run
    still in progress between R and the run deciding must be seen, because it
    stops the walk (one created before R is listed too, and never reached). Each run must
    say the event and branch it was asked for and carry an integer id and a
    usable ``created_at`` -- anything else raises, as ``_last_whole`` does.
    Returns the runs and the floor, which the reasons name.
    """
    floor = (since - MAX_INHERIT_AGE - timedelta(days=1)).astimezone(UTC).date().isoformat()
    found: list[dict[str, Any]] = []
    for event in WHOLE_CODEBASE_EVENTS:
        listing = api("actions/workflows/ci.yml/runs?branch=%s&event=%s"
                      "&created=%%3E%%3D%s&per_page=%d" % (MAIN, event, floor, PER_PAGE))
        for item in _page(listing, "workflow_runs"):
            if item.get("event") != event:
                raise ValueError("a %r window query returned a %r run" % (event, item.get("event")))
            if item.get("head_branch") != MAIN:
                raise ValueError("a branch=%s window query returned a run on branch %r"
                                 % (MAIN, item.get("head_branch")))
            if not _is_int(item.get("id")):
                raise ValueError("a whole-codebase run in the window has no integer id")
            _run_key(item)      # raises on a run with no usable created_at
            found.append(item)
    return sorted(found, key=_run_key, reverse=True), floor


def _jobs(api: Api, run_id: int) -> list[dict[str, Any]]:
    """Run ``run_id``'s jobs, latest attempt: one page, or it raises (``_page``)."""
    return _page(api("actions/runs/%d/jobs?filter=latest&per_page=%d" % (run_id, PER_PAGE)),
                 "jobs")


def _mutation_job(api: Api, run_id: int) -> dict[str, Any] | None:
    """Run ``run_id``'s job named exactly ``mutation`` (latest attempt), or None."""
    return _the_mutation_job(_jobs(api, run_id), run_id)


def _the_mutation_job(jobs: list[dict[str, Any]], run_id: int) -> dict[str, Any] | None:
    """The job named exactly ``mutation`` in run ``run_id``'s listing, or None.

    Two such jobs, or one that names another run, raise.
    """
    named = [j for j in jobs if j.get("name") == MUTATION_JOB]
    if not named:
        return None
    if len(named) > 1:
        raise ValueError("run %d lists %d jobs named %s" % (run_id, len(named), MUTATION_JOB))
    job = named[0]
    owner = job.get("run_id")
    if owner is not None and not (_is_int(owner) and owner == run_id):
        raise ValueError("run %d's %s job says it belongs to run %r" % (run_id, MUTATION_JOB, owner))
    return job


def _a_finished_advisory_job(job: dict[str, Any]) -> bool:
    """Is ``job`` one of the diff shadow's advisory jobs, completed with a conclusion?"""
    name = job.get("name")
    conclusion = job.get("conclusion")
    return (job.get("status") == "completed"
            and isinstance(conclusion, str) and conclusion != ""
            and isinstance(name, str) and ADVISORY_JOB_NAMES.fullmatch(name) is not None)


def _red_only_on_extended(jobs: list[dict[str, Any]], run_id: int) -> bool:
    """Is every job of this listing that is not green a ``tests-extended`` leg -- and is there one?

    Green is completed with ``success`` or ``skipped`` (a dispatch skips
    ``idle-nightly``; a schedule or dispatch run skips every pull-request
    job). The diff shadow's advisory jobs (``ADVISORY_JOB_NAMES``) are
    dropped from the not-green set first: they are job-level
    ``continue-on-error``, so one can be red on the page of a run its red
    did not make red, and it decides nothing. True only when something else
    is not green and all of that is an extended leg: that is the one red
    fact 3 looks past, so a run red with nothing red on its page, or nothing
    but advisory jobs, is not explained by it. Only an advisory job that
    completed with a conclusion is dropped: one still running, or with no
    conclusion, inside a completed run is the contradiction ``mutation`` is
    refused for, so it stays in the not-green set and the run reads
    ``RED_BEYOND_EXTENDED``. A not-green job that names another run raises,
    advisory or not, as ``_the_mutation_job`` does.
    """
    red = [j for j in jobs
           if j.get("status") != "completed" or j.get("conclusion") not in ("success", "skipped")]
    for job in red:
        owner = job.get("run_id")
        if owner is not None and not (_is_int(owner) and owner == run_id):
            raise ValueError("run %d's job listing holds another run's job" % run_id)
    red = [j for j in red if not _a_finished_advisory_job(j)]
    return bool(red) and all(
        isinstance(name := job.get("name"), str)
        and (name == EXTENDED_JOB or name.startswith(EXTENDED_JOB + " ("))
        for job in red)


def _inherit(api: Api, ref: dict[str, Any], sha: str, tree: str,
             runs: list[dict[str, Any]], floor: str) -> Inheritance:
    """The walk (module docstring): may ``ref``, a run of ``sha`` over ``tree``, inherit?

    ``ref`` is the run deciding -- tonight's nightly, or a skip being re-checked
    for fact 3 -- and ``runs`` is ``_whole_window``'s listing, newest first.
    ``ref`` itself and every run created after it are left out *before*
    anything else is judged: the nightly asking is in the listing, in progress,
    and a dispatch started after it has no bearing on what it may inherit.
    Every reason is built from integers, ``_word``, ``_short``, ``_iso`` and
    ``_days`` output, never from a string the API returned.
    """
    ref_key = _run_key(ref)
    ref_id = ref.get("id")
    skips: list[tuple[int, int | None]] = []
    for run in runs:
        ident = run["id"]
        if ident == ref_id or _run_key(run) >= ref_key:
            continue
        where = "run %d (%s)" % (ident, _word(run.get("event")))
        status, conclusion = run.get("status"), run.get("conclusion")
        if status != "completed":
            return Inheritance(None, "%s is %s, so what it will say is unknown"
                               % (where, _word(status)))
        # The run's own conclusion, deliberately -- for a skip passed over and
        # for R alike, and on top of R's `mutation` job below. Fact 3
        # (`_last_whole`) looks past a red `tests-extended` leg on the newest
        # run, so that one does not put every push on the full run; this walk
        # does not take that leniency. An idle night replaces
        # a full mutation run, and being wrong here reports green over bytes
        # no run scored this week -- on the way to a release. Fact 3 only lets
        # a push skip what its own PR run already proved. So a whole-codebase
        # run red for any reason, a platform leg included, sends the next
        # nightly back to the full plan: one extra run, the cheap direction.
        if conclusion != "success":
            return Inheritance(None, "%s concluded %s, and a whole-codebase run that is "
                               "not green is never looked past" % (where, _word(conclusion)))
        attempt = run.get("run_attempt")
        if attempt != 1 or not _is_int(attempt):
            return Inheritance(None, "%s is attempt %s, and only a first attempt counts"
                               % (where, attempt if _is_int(attempt) else "unknown"))
        if run.get("head_sha") != sha:
            return Inheritance(None, "%s ran commit %s, not %s: main has moved since"
                               % (where, _short(run.get("head_sha")), sha[:12]))
        markers = _markers(api, ident)
        if not markers:
            return Inheritance(None, "%s carries no %s or %s marker"
                               % (where, MUTATED_TREE_ARTIFACT, INHERITED_TREE_ARTIFACT))
        if len(markers) > 1:
            return Inheritance(None, "%s carries %d markers, so what it was is ambiguous"
                               % (where, len(markers)))
        marker = markers[0]
        if marker.expired is not False:
            return Inheritance(None, "%s's marker has expired" % where)
        if marker.tree != tree:
            return Inheritance(None, "%s recorded tree %s, not %s"
                               % (where, marker.tree[:12], tree[:12]))
        if marker.kind == "skip":
            skips.append((ident, marker.source))
            continue
        # The newest real run. Its age first: an old run needs no more requests.
        age = ref_key[0] - _run_key(run)[0]
        if age >= MAX_INHERIT_AGE:
            return Inheritance(None, "%s, the newest real whole-codebase run, was created "
                               "%s days before this one; a real run is inherited for "
                               "less than %d" % (where, _days(age), MAX_INHERIT_AGE.days))
        job = _mutation_job(api, ident)
        if job is None:
            return Inheritance(None, "%s has no %s job" % (where, MUTATION_JOB))
        if job.get("status") != "completed" or job.get("conclusion") != "success":
            return Inheritance(None, "%s's %s job is %s/%s" % (
                where, MUTATION_JOB, _word(job.get("status")), _word(job.get("conclusion"))))
        for skip_id, source in skips:
            if source != ident:
                return Inheritance(None, "run %d inherited from run %s, not from %s"
                                   % (skip_id, source if _is_int(source) else "?", where))
        return Inheritance(run, "inherits %s, created %s, which mutated tree %s in full with "
                           "%s green, %s days earlier" % (
                               where, _iso(_run_key(run)[0]), tree[:12], MUTATION_JOB,
                               _days(age)))
    return Inheritance(None, "no real whole-codebase run of ci.yml on main created since %s"
                       % floor)


def _proven_skip(api: Api, run: dict[str, Any], marker: Marker) -> bool:
    """Does the skip ``run`` still inherit what its marker says it did?

    Re-run from the skip's own ``created_at``, so R is aged as the skip aged
    it (fact 3 then judges the skip's own 48 h); and the real run found must
    be the one the marker names. Anything unknown is False.
    """
    created = _parse_when(run.get("created_at"))
    sha = run.get("head_sha")
    if created is None or not isinstance(sha, str) or not _COMMIT.fullmatch(sha):
        return False
    runs, floor = _whole_window(api, created)
    got = _inherit(api, run, sha, marker.tree, runs, floor)
    return got.source is not None and got.source.get("id") == marker.source


def idle(api: Api, sha: str, run_id: int, run_attempt: int, now: datetime) -> Idle:
    """May the ``schedule`` run ``run_id`` of ``sha`` plan no mutation run?

    Raises on any transport or shape problem; ci_idle_nightly.py turns that
    into ``error: <type>``. A re-run is answered with no request: it was
    started because something about the first attempt was in doubt.
    """
    if run_attempt != 1:
        return Idle(False, "this run is attempt %d, and a re-run plans the full set"
                    % run_attempt)
    tree = _tree_sha(api("git/commits/%s" % sha), "this commit")
    if not _OBJECT.fullmatch(tree):
        raise ValueError("this commit's tree.sha is not an object id")
    runs, floor = _whole_window(api, now)
    mine = [r for r in runs if r["id"] == run_id]
    if len(mine) != 1:
        raise ValueError("run %d is listed %d times in the window" % (run_id, len(mine)))
    me = mine[0]
    # The run asking must be the one this step runs in: a schedule run of
    # this commit. The window already checked its branch.
    if me.get("event") != "schedule" or me.get("head_sha") != sha:
        raise ValueError("run %d is not a schedule run of this commit" % run_id)
    if _run_key(me)[0] - now > CLOCK_SKEW:
        raise ValueError("run %d's created_at is ahead of this clock" % run_id)
    got = _inherit(api, me, sha, tree, runs, floor)
    if got.source is None:
        return Idle(False, "not idle: " + got.reason)
    created = _run_key(got.source)[0]
    return Idle(True, "idle nightly: main is still %s, tree %s; %s; inherited, not "
                "re-measured, until %s" % (sha[:12], tree[:12], got.reason,
                                           _iso(created + MAX_INHERIT_AGE)),
                got.source["id"], tree, created)


# --------------------------------------------------------------------------
# the nightly diff shadow: what tonight's diff set is diffed from
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ShadowBase:
    """The commit a full nightly's advisory diff set is diffed from, or None.

    ``base`` is a commit id the walk checked, ``source_run`` the real run it
    is the ``head_sha`` of. With ``base=None`` the nightly plans full only.
    """

    base: str | None
    reason: str
    source_run: int | None = None


def shadow_base(api: Api, sha: str, run_id: int, run_attempt: int,
                now: datetime) -> ShadowBase:
    """The ``head_sha`` of the newest green real whole-codebase run before tonight.

    The scope a full nightly shadows (docs/superpowers/plans/2026-10-31-ci-speed.md,
    Task 7 Step 6) is everything merged since main was last proven whole: the
    diff the nightly backstop stands behind once the diff gate binds (spec
    option B). It is its own walk rather than a reuse of ``_inherit``, whose
    every stop is a "not idle" answer this question does not share:

    * a run that is not a completed green first attempt is LOOKED PAST, where
      ``_inherit`` stops on it. A base is not an inheritance: an older one only
      widens the diff, and after a red night the wider scope is the most
      useful evidence there is;
    * a skip (``inherited-tree-``) is looked past toward the real run it
      names, and so is a real run whose own ``mutation`` job is not green;
    * a green run with no marker or several, or a marker not plainly live,
      stops it with no base: what that run was is unknown;
    * the newest green real run being of ``sha`` itself is "nothing to
      shadow" -- tonight's diff would be empty.

    The window is ``_whole_window``'s, so the oldest base a shadow can diff
    from is ``MAX_INHERIT_AGE`` plus a day back; past that it plans full only.
    Tonight must be listed once, as a ``schedule`` run of ``sha`` created no
    later than the clock allows, exactly as ``idle`` checks it. Raises on any
    transport or shape problem (ci_idle_nightly.py turns that into ``error:
    <type>``); every reason is built from integers and this module's helpers,
    never from API text. A re-run is answered with no request.
    """
    if run_attempt != 1:
        return ShadowBase(None, "this run is attempt %d, and a re-run plans full only"
                          % run_attempt)
    runs, floor = _whole_window(api, now)
    mine = [r for r in runs if r["id"] == run_id]
    if len(mine) != 1:
        raise ValueError("run %d is listed %d times in the window" % (run_id, len(mine)))
    me = mine[0]
    if me.get("event") != "schedule" or me.get("head_sha") != sha:
        raise ValueError("run %d is not a schedule run of this commit" % run_id)
    ref_key = _run_key(me)
    if ref_key[0] - now > CLOCK_SKEW:
        raise ValueError("run %d's created_at is ahead of this clock" % run_id)
    passed = 0
    for run in runs:
        ident = run["id"]
        if ident == run_id or _run_key(run) >= ref_key:
            continue
        where = "run %d (%s)" % (ident, _word(run.get("event")))
        attempt = run.get("run_attempt")
        if (run.get("status") != "completed" or run.get("conclusion") != "success"
                or not _is_int(attempt) or attempt != 1):
            passed += 1
            continue
        markers = _markers(api, ident)
        if len(markers) != 1:
            return ShadowBase(None, "%s carries %d markers, so what it was is unknown"
                              % (where, len(markers)))
        marker = markers[0]
        if marker.expired is not False:
            return ShadowBase(None, "%s's marker has expired" % where)
        if marker.kind == "skip":
            passed += 1
            continue
        job = _mutation_job(api, ident)
        if job is None or job.get("status") != "completed" or job.get("conclusion") != "success":
            passed += 1
            continue
        head = run.get("head_sha")
        if not isinstance(head, str) or not _COMMIT.fullmatch(head):
            return ShadowBase(None, "%s ran no commit id" % where)
        if head == sha:
            return ShadowBase(None, "%s, the newest green real whole-codebase run, is of "
                              "this same commit %s: nothing to shadow" % (where, sha[:12]))
        return ShadowBase(head, "diff shadow against %s, created %s, commit %s; %d runs "
                          "looked past" % (where, _iso(_run_key(run)[0]), head[:12], passed),
                          ident)
    return ShadowBase(None, "no green real whole-codebase run of ci.yml on main created "
                      "since %s" % floor)


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
    * ``nightly-<conclusion>`` -- the job was green, but the ``mutation`` job
      of the newest completed whole-codebase run on ``main`` concluded
      otherwise (``nightly-failure``, ``nightly-cancelled``, ...,
      ``nightly-unknown``), or that run is an idle nightly whose inheritance
      ``_last_whole`` could not re-derive (``nightly-unproven_skip``), or
      that run is red on a job other than a ``tests-extended`` leg
      (``nightly-red_beyond_extended``); a red ``tests-extended`` leg in that
      run is not one of these (fact 3);
    * ``no-nightly`` -- the job was green, and no whole-codebase run on
      ``main`` has completed;
    * ``no-base`` -- ``before`` is empty or all zeros (the push made the ref);
    * ``invalid-base`` -- ``before`` is not a full lower-case commit id;
    * ``missing-run`` -- no ``ci`` push run on ``main`` for that commit;
    * ``missing-job`` -- that run's latest attempt has no ``mutation`` job;
    * ``error`` -- anything raised: transport, HTTP status (a 403/429 rate
      limit included), JSON, a listing of the wrong shape or longer than one
      page, a run that contradicts the query, two ``mutation`` jobs, a
      whole-codebase run with none, missing credentials, a command line that
      does not parse.
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
    success`` is green, and then only beside a green ``mutation`` in the
    newest whole-codebase run, which is asked for last: a base that is red on
    its own says so first.
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
    job = _mutation_job(api, run_id)
    if job is None:
        return BaseVerdict(False, "missing-job")
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
    # Never without a run to name: the planner's reason names it.
    proven = "true" if decision.mutation_proven and run_id else "false"
    reason = _oneline(decision.reason)
    green = "true" if base.green is True else "false"
    word = base.word if _BASE_WORD.fullmatch(base.word) else "unknown"
    print("ci_proven_tree: skip=%s pr_run_id=%s base_mutation_green=%s base_mutation=%s "
          "mutation_proven=%s -- %s" % (skip, run_id, green, word, proven, reason))
    lines = ("skip=%s\npr_run_id=%s\nbase_mutation_green=%s\nbase_mutation=%s\n"
             "mutation_proven=%s\n" % (skip, run_id, green, word, proven))
    if env.get("GITHUB_OUTPUT"):
        _append(env["GITHUB_OUTPUT"], lines, "GITHUB_OUTPUT")
    else:
        print(lines, end="")
    if env.get("GITHUB_STEP_SUMMARY"):
        _append(env["GITHUB_STEP_SUMMARY"],
                "### Proven-tree check\n\n- skip: `%s`\n- mutation proven: `%s`\n"
                "- reason: %s\n- base commit's mutation: `%s` (green: `%s`)\n"
                % (skip, proven, reason, word, green),
                "GITHUB_STEP_SUMMARY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
