#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""May tonight's ``schedule`` run of ci.yml skip the 24-shard mutation run?

On 2026-11-02 run 41512174636 mutated ``b294d51c`` in full and passed. On
2026-11-03 run 41682296301 mutated the same commit again, every shard, because
nothing had merged in between: a second measurement of bytes already scored.
This is the check that lets such a night plan ``none`` and say which real run
it leans on. The walk itself is ``ci_proven_tree.idle`` -- in that module
because ``_last_whole`` re-runs it for every skip fact 3 is asked to trust, and
one definition of "a skip that holds" is the only kind that cannot drift.

Only a ``schedule`` run on ``refs/heads/main`` is asked about, and only its
first attempt: a ``workflow_dispatch`` is the lever for clearing a red nightly
and always plans full, and a re-run was started because the first attempt was
in doubt. This script sees only the re-runs that run it again ("re-run all
jobs"). "Re-run failed jobs" on a red idle night re-runs mutation-plan alone
and hands it this job's outputs from the attempt before, a yes among them, so
ci.yml's scope step checks ``GITHUB_RUN_ATTEMPT`` itself before it trusts one.
Everything else -- no credentials, a malformed argument, any HTTP,
JSON, timeout or shape error -- is ``idle=false`` with a reason, and the step's
consumer plans full.

CLI: ``ci_idle_nightly.py --sha SHA --run-id ID --run-attempt N`` reads
``GITHUB_REPOSITORY``, ``GITHUB_TOKEN``, ``GITHUB_EVENT_NAME`` and
``GITHUB_REF``, and appends to ``$GITHUB_OUTPUT`` only values it computed:
``idle=true|false``, ``source_run=<digits or empty>``, ``source_tree=<object id
or empty>`` and ``reason=<one bounded line>``. It **always exits 0**: a nonzero
exit would fail the job rather than fall back to a full run. Stdlib only, so
the runner's python3 needs no setup step.

``--shadow-base`` asks the other nightly question instead, for the
``nightly-shadow-base`` job: what commit tonight's advisory diff set is diffed
from (``ci_proven_tree.shadow_base``). The same argument and credential checks,
the same "every failure is an answer" rule, and three outputs:
``shadow_base=<commit or empty>``, ``shadow_base_run=<digits or empty>`` and
``shadow_reason=<one bounded line>``. Empty means the nightly plans full with
no shadow. A base that is not a commit id, is ``--sha`` itself, or comes
without a positive run id is written empty. Always exits 0.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_proven_tree():
    """Import ``ci_proven_tree`` from beside this file (see nightly_watch.py)."""
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

#: The only event and ref a skip is ever considered for.
EVENT = "schedule"
REF = "refs/heads/main"

PREFIX = "ci_idle_nightly"


def _parser() -> argparse.ArgumentParser:
    parser = pt._Parser(prog="ci_idle_nightly.py", description="Decide whether "
                        "tonight's whole-codebase run may inherit the last real one.")
    parser.add_argument("--sha", required=True, help="the commit this run checked out")
    parser.add_argument("--run-id", required=True, help="this run's id (GITHUB_RUN_ID)")
    parser.add_argument("--run-attempt", required=True,
                        help="this run's attempt (GITHUB_RUN_ATTEMPT)")
    parser.add_argument("--now", type=pt._instant, default=None,
                        help="ISO-8601 instant to place the window at "
                             "(tests only; default: the real clock)")
    parser.add_argument("--shadow-base", action="store_true",
                        help="answer nightly-shadow-base's question instead: the "
                             "commit tonight's advisory diff set is diffed from")
    return parser


def _checked(argv: list[str] | None, api: Api | None,
             env: Mapping[str, str]) -> tuple[argparse.Namespace, Api] | str:
    """The parsed arguments and an ``api``, or the reason no request may be made.

    Shared by both questions, so a dispatch, another ref, a malformed
    argument or missing credentials stop either one before any request.
    A command line that does not parse raises ``UsageError``.
    """
    token = (env.get("GITHUB_TOKEN") or "").strip()
    args = _parser().parse_args(argv)
    if env.get("GITHUB_EVENT_NAME") != EVENT:
        return "not a %s run: only the nightly may skip" % EVENT
    if env.get("GITHUB_REF") != REF:
        return "not a run of %s" % REF
    if not pt._COMMIT.fullmatch(args.sha):
        return "--sha is not a full lower-case commit id"
    if not pt._RUN_ID.fullmatch(args.run_id):
        return "--run-id is not a run id"
    if not pt._RUN_ID.fullmatch(args.run_attempt):
        return "--run-attempt is not an attempt number"
    if api is None:
        repo = (env.get("GITHUB_REPOSITORY") or "").strip()
        if not token:
            return "GITHUB_TOKEN is not set"
        if not pt._REPO.fullmatch(repo):
            return "GITHUB_REPOSITORY is unset or malformed"
        api = pt.make_api(repo, token)
    return args, api


def _clock(args: argparse.Namespace) -> datetime:
    return args.now if args.now is not None else datetime.now(UTC)


def decide(argv: list[str] | None, api: Api | None, env: Mapping[str, str]) -> Any:
    """``ci_proven_tree.idle`` for this run, with every failure an ``Idle(False, ...)``."""
    token = (env.get("GITHUB_TOKEN") or "").strip()
    try:
        checked = _checked(argv, api, env)
        if isinstance(checked, str):
            return pt.Idle(False, checked)
        args, api = checked
        return pt.idle(api, args.sha, int(args.run_id), int(args.run_attempt), _clock(args))
    except Exception as exc:
        pt._report(exc, token)
        return pt.Idle(False, "error: %s" % type(exc).__name__)


#: Written in place of the walk's own reason when its answer fails the
#: soundness check below: the walk's reason would name the base refused.
UNSOUND_SHADOW = "a shadow base that did not check out"


def decide_shadow(argv: list[str] | None, api: Api | None,
                  env: Mapping[str, str]) -> Any:
    """``ci_proven_tree.shadow_base`` for this run; every failure is no base.

    The answer is checked once more before it leaves: a base that is not a
    commit id, is tonight's own commit, or comes without a positive integer
    run id is no base.
    """
    token = (env.get("GITHUB_TOKEN") or "").strip()
    try:
        checked = _checked(argv, api, env)
        if isinstance(checked, str):
            return pt.ShadowBase(None, checked)
        args, api = checked
        got = pt.shadow_base(api, args.sha, int(args.run_id), int(args.run_attempt),
                             _clock(args))
    except Exception as exc:
        pt._report(exc, token)
        return pt.ShadowBase(None, "error: %s" % type(exc).__name__)
    if got.base is None:
        return pt.ShadowBase(None, got.reason)
    sound = (isinstance(got.base, str) and bool(pt._COMMIT.fullmatch(got.base))
             and got.base != args.sha and pt._is_int(got.source_run) and got.source_run > 0)
    return got if sound else pt.ShadowBase(None, UNSOUND_SHADOW)


def _outputs(verdict: Any) -> tuple[str, str, str]:
    """(idle, source_run, source_tree), and ``false`` unless every source fact is sound."""
    run, tree, created = verdict.source_run, verdict.source_tree, verdict.source_created
    sound = (verdict.idle is True and pt._is_int(run) and run > 0
             and isinstance(tree, str) and bool(pt._OBJECT.fullmatch(tree))
             and isinstance(created, datetime) and created.tzinfo is not None)
    if not sound:
        return "false", "", ""
    return "true", str(run), tree


def main(argv: list[str] | None = None, *, api: Api | None = None,
         env: Mapping[str, str] | None = None) -> int:
    """Always returns 0; the verdict is in the outputs.

    With ``api`` injected, no credentials are read: the callable stands in for
    both the network and the token.
    """
    env = os.environ if env is None else env
    if "--shadow-base" in (sys.argv[1:] if argv is None else argv):
        return _main_shadow(argv, api, env)
    verdict = decide(argv, api, env)
    idle, source_run, source_tree = _outputs(verdict)
    reason = pt._oneline(verdict.reason)
    if verdict.idle is True and idle == "false":
        reason = "an idle verdict whose source run, tree or time did not check out"
    print("%s: idle=%s source_run=%s -- %s" % (PREFIX, idle, source_run, reason))
    lines = "idle=%s\nsource_run=%s\nsource_tree=%s\nreason=%s\n" % (
        idle, source_run, source_tree, reason)
    if env.get("GITHUB_OUTPUT"):
        pt._append(env["GITHUB_OUTPUT"], lines, "GITHUB_OUTPUT")
    else:
        print(lines, end="")
    if env.get("GITHUB_STEP_SUMMARY"):
        pt._append(env["GITHUB_STEP_SUMMARY"],
                   "### Idle-nightly check\n\n- idle: `%s`\n- reason: %s\n" % (idle, reason),
                   "GITHUB_STEP_SUMMARY")
    return 0


def _main_shadow(argv: list[str] | None, api: Api | None, env: Mapping[str, str]) -> int:
    """``--shadow-base``: three outputs, and exit 0 whatever happened."""
    verdict = decide_shadow(argv, api, env)
    base = verdict.base or ""
    run = str(verdict.source_run) if verdict.base else ""
    reason = pt._oneline(verdict.reason)
    print("%s: shadow_base=%s shadow_base_run=%s -- %s" % (PREFIX, base, run, reason))
    lines = "shadow_base=%s\nshadow_base_run=%s\nshadow_reason=%s\n" % (base, run, reason)
    if env.get("GITHUB_OUTPUT"):
        pt._append(env["GITHUB_OUTPUT"], lines, "GITHUB_OUTPUT")
    else:
        print(lines, end="")
    if env.get("GITHUB_STEP_SUMMARY"):
        pt._append(env["GITHUB_STEP_SUMMARY"],
                   "### Nightly diff-shadow base\n\n- base: `%s`\n- reason: %s\n"
                   % (base or "none", reason), "GITHUB_STEP_SUMMARY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
