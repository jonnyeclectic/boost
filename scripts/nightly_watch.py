#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Fail when ``ci``'s whole-codebase mutation run has stopped happening on main.

ci.yml's ``schedule`` (and its ``workflow_dispatch``) is the only run that
scores the whole of ``boost_cli/core``: a pull request's gate scores the
functions it changed, and a push whose tree a green PR run already tested skips
the mutation shards. A *red* nightly is already loud -- ci-failure-issue.yml
watches ``ci`` and opens a tracker. A *missing* one was silent:
``ci_proven_tree.py`` stops authorising the skip once the newest whole-codebase
run is more than 48 h old, which is the safe direction, and tells nobody. Every
push then runs the full gate, and nothing says why or that the nightly is gone.

This script is that alarm. It asks GitHub for exactly the run
``ci_proven_tree`` ages -- the newest completed ``schedule`` /
``workflow_dispatch`` run of ``ci.yml`` on ``main``, through that script's own
``_newest_completed_whole``, the query ``_last_whole`` starts from, so the two
cannot drift onto different definitions -- and exits 1 when there is none or
it was created more than ``MAX_AGE`` ago. The run's conclusion is printed but
not judged: a red one has its own alarm. (``ci_proven_tree`` goes on to read
that run's ``mutation`` job, and for a green one its marker; this asks
neither, so it makes no third request.)

An idle nightly (one that planned no mutation run because main had not moved
since a green real run, ``ci_proven_tree.idle``) is a completed ``schedule``
run like any other, so it counts here as the cron having fired -- which it
did -- and raises no false alarm. It cannot stand in for a missing one: a
cron that stopped leaves no run at all, idle or not, and that still fails at
``MAX_AGE``. Whether the skip's inheritance still holds is not this alarm's
question: ``_last_whole`` re-derives it for every reader that trusts the
result, and reads ``unproven_skip`` when it does not.

THE DIRECTION: an alarm that cannot look must be loud. A 4xx/5xx, a timeout, a
body of the wrong shape, a run on another branch, a ``created_at`` that is
missing or in the future -- every one of them exits 1, saying the check could
not be made, never 0.

CLI: ``python3 scripts/nightly_watch.py`` reads ``GITHUB_REPOSITORY`` and
``GITHUB_TOKEN``. Stdlib only, so the runner's python3 needs no setup step.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _load_proven_tree():
    """Import ``ci_proven_tree`` from beside this file.

    ``scripts/`` is not a package: a plain import works for ``python3
    scripts/nightly_watch.py`` and not for a test loading this file by path
    (the same reason mutation_plan.py loads mutation_shards.py this way). It is
    registered in ``sys.modules`` before it runs because its dataclasses'
    string annotations are resolved through it.
    """
    name = "ci_proven_tree"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / "ci_proven_tree.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load ci_proven_tree.py beside %s" % __file__)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pt = _load_proven_tree()

Api = Callable[[str], Any]

# How old the newest whole-codebase run may be before this fails.
#
# A healthy gap is not 24 h. GitHub starts a scheduled run late, by an amount
# that varies: ci's 09:30 UTC cron began at 19:40:47Z on 2026-11-02 (10 h 10 m
# late) and 17:14:31Z on 2026-11-03 (7 h 44 m), and earlier measurements of this
# repository's crons put the lag between 4 h 50 m and 6 h 56 m. Two consecutive
# nightlies can therefore sit about 24 h + (10 h 10 m - 4 h 50 m), roughly
# 29-30 h, apart with nothing wrong -- and since only a *completed* run counts,
# the newer one's own running time adds to that. 36 h is that plus margin.
#
# It is also below ci_proven_tree.MAX_NIGHTLY_AGE (48 h), so a nightly that
# stopped is normally reported here before the proven-tree skip turns off --
# not always: the 12 h between the two is one interval of nightly-watch.yml's
# twice-daily cron, and that cron starts late too, so the alarm can land a few
# hours after 48 h. Either way it fails loud. tests/unit/test_nightly_watch.py
# pins MAX_AGE + that interval <= 48 h. "More than", as there: exactly 36 h is
# still fresh.
MAX_AGE = timedelta(hours=36)

PREFIX = "nightly_watch"


def _newest_whole(api: Api) -> tuple[Any, dict[str, Any] | None]:
    """The run ``ci_proven_tree._newest_completed_whole`` chose, as a ``Nightly``, plus the run.

    Both from that one helper -- the same two ``per_page=1`` requests
    ``_last_whole`` begins with, and nothing else. The ``Nightly`` carries the
    run's own conclusion (for the log; it is not judged) and its creation
    time, parsed as ``ci_proven_tree`` parses it; the run object is only for
    naming the run in the log. Not ``_last_whole`` itself: that goes on to
    read the run's ``mutation`` job, for a green one its marker, and for an
    idle nightly the whole window -- questions about the verdict and the
    skip's provenance, not about whether the cron fired.
    """
    run = pt._newest_completed_whole(api)
    if run is None:
        return None, None
    return pt.Nightly(pt._text(run.get("conclusion")), pt._parse_when(run.get("created_at"))), run


def judge(nightly: Any, run: dict[str, Any] | None, now: datetime) -> tuple[bool, str]:
    """(fresh enough, one line saying so or why not)."""
    if nightly is None:
        return False, ("no completed schedule or workflow_dispatch run of ci.yml "
                       "exists on main")
    run = run or {}
    ident = run.get("id")
    what = "run %s (%s, concluded %s)" % (
        ident if pt._is_int(ident) else "?",
        pt._text(run.get("event")) or "?",
        nightly.conclusion)
    if nightly.created_at is None:
        return False, "%s: created_at is missing or unparseable, so its age is unknown" % what
    age = now - nightly.created_at
    if age < -pt.CLOCK_SKEW:
        return False, "%s: created_at is %sh ahead of this clock" % (what, pt._hours(age))
    limit = pt._hours(MAX_AGE)
    if age > MAX_AGE:
        return False, ("%s was created %sh ago, more than %sh: ci's nightly "
                       "whole-codebase mutation run is overdue"
                       % (what, pt._hours(age), limit))
    return True, "%s was created %sh ago (limit %sh)" % (
        what, pt._hours(max(age, timedelta(0))), limit)


def main(*, api: Api | None = None, env: Mapping[str, str] | None = None,
         now: datetime | None = None) -> int:
    """0 when the newest whole-codebase run is recent; 1 otherwise, or when unknown.

    ``api`` and ``now`` are for tests: an injected ``api`` stands in for both
    the network and the token, and ``now`` for the clock.
    """
    env = os.environ if env is None else env
    token = (env.get("GITHUB_TOKEN") or "").strip()
    try:
        if api is None:
            repo = (env.get("GITHUB_REPOSITORY") or "").strip()
            if not token:
                raise ValueError("GITHUB_TOKEN is not set")
            if not pt._REPO.fullmatch(repo):
                raise ValueError("GITHUB_REPOSITORY is unset or malformed")
            api = pt.make_api(repo, token)
        nightly, run = _newest_whole(api)
    except Exception as exc:
        detail = pt._oneline("%s: %s" % (type(exc).__name__, exc))
        if token:
            detail = detail.replace(token, "***")
        print("::error::%s could not check ci's whole-codebase run, so it cannot "
              "say the nightly is running -- %s" % (PREFIX, detail))
        return 1
    ok, message = judge(nightly, run, now if now is not None else datetime.now(UTC))
    message = pt._oneline(message)
    if ok:
        print("%s: ok -- %s" % (PREFIX, message))
        return 0
    print("::error::%s: %s" % (PREFIX, message))
    return 1


if __name__ == "__main__":
    sys.exit(main())
