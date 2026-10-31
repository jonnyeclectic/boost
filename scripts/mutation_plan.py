#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Decide, once per run, what the mutation shards will run — and write it down.

Before this, each of the 24 ``mutation-shard`` jobs re-derived its own slice
(``mutation_shards.py plan --index``) and, before its first mutant, re-ran
mutmut's whole ``Running stats`` phase: the full unit suite under trampolines,
to learn which tests cover which function. Every shard learned the same
answer from the same commit, at 5.5-8.8 minutes each. The ``mutation-plan``
job now pays for that once, uploads ``mutants/mutmut-stats.json`` as an
artifact, and writes the shard list here as one JSON plan the matrix is built
from. A shard restores the stats file before ``mutmut run``, and mutmut then
re-collects only for test ids the file does not already know — none, on the
same commit and config.

The plan
--------
::

    {"gate_set": "full" | null,
     "reasons":  ["why this plan, in words a reviewer can check"],
     "sets":     {"<set>": {"shards": [[pattern, ...], ...],
                            "mutants": <int> | null}}}

``sets`` is keyed by name so a run can carry more than one: today there is
only ``full`` (the committed 24-way pack of every mutant in ``boost_cli/core``),
and the diff-scoped gate adds ``diff`` alongside it. ``gate_set`` names the set
the required ``mutation`` check scores; ``null`` means nothing mutable changed
and there is nothing to score. ``matrix`` and ``patterns`` are generic over set
names on purpose, so a new set needs a planner change and nothing else.

Usage
-----
  mutation_plan.py full --shards 24 --out PLAN      # every mutant, committed pack
  mutation_plan.py none --reason TEXT --out PLAN    # nothing to run, and why
  mutation_plan.py matrix --plan PLAN               # [{"set":..,"index":..}, ...]
  mutation_plan.py patterns --plan PLAN --set S --index I   # one shard's argv
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load_shards():
    """Import ``mutation_shards`` from beside this file, as the tests do.

    ``scripts/`` is not a package, and CI invokes this as
    ``python3 scripts/mutation_plan.py`` from the repo root, so a plain import
    would depend on ``sys.path[0]`` being this directory — true for a script
    run, false for a test importing this module by path.
    """
    spec = importlib.util.spec_from_file_location(
        "mutation_shards", Path(__file__).resolve().parent / "mutation_shards.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load mutation_shards.py beside %s" % __file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ms = _load_shards()

#: The full run's width. Python's copy of a number ``ci.yml`` also spells as
#: ``full --shards 24`` and ``merge --shards 24``;
#: ``tests/unit/test_mutation_shard_count.py`` pins them all to each other.
FULL_SHARDS: int = ms.SHARDS


def full_plan(root: Path, shards: int, reasons: list[str]) -> dict[str, Any]:
    """Every mutant, packed exactly as ``mutation_shards.py plan`` packs it.

    The same ``pack`` the gate's ``merge --shards N`` re-derives to learn which
    shard owned which file, so the two cannot disagree about ownership.
    """
    bins = ms.pack(root, shards)
    return {
        "gate_set": "full",
        "reasons": reasons,
        "sets": {"full": {"shards": [ms.patterns_for_bin(root, b) for b in bins],
                          # Counting needs mutmut's generated mutants, which
                          # the planner has not made; null is "not counted",
                          # never zero.
                          "mutants": None}},
    }


def none_plan(reason: str) -> dict[str, Any]:
    """Nothing to run. The reason is the whole point: a skip must say why."""
    return {"gate_set": None, "reasons": [reason], "sets": {}}


def matrix(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """One matrix entry per shard of every set, in the plan's order.

    An empty shard is still listed. Dropping it here would make its patterns
    nobody's job, and the gate's fail-closed merge is the only thing that
    would notice — 40 minutes later, naming an artifact rather than the plan.
    Listing it instead makes that shard's own ``patterns`` call fail at once.
    """
    return [{"set": name, "index": i}
            for name, spec in plan["sets"].items()
            for i in range(len(spec["shards"]))]


def shard_patterns(plan: dict[str, Any], name: str, index: int) -> list[str]:
    """One shard's patterns, or ``[]`` for an unknown set or index."""
    spec = plan["sets"].get(name)
    if spec is None or not 0 <= index < len(spec["shards"]):
        return []
    return list(spec["shards"][index])


def _write(path: str, plan: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")


def _read(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("full", help="plan every mutant on the committed pack")
    f.add_argument("--shards", type=int, default=FULL_SHARDS)
    f.add_argument("--reason", action="append", default=[],
                   help="why a full run (repeatable)")
    f.add_argument("--root", default=str(ROOT), help="repo root (default: this checkout)")
    f.add_argument("--out", required=True)

    n = sub.add_parser("none", help="plan nothing, and record why")
    n.add_argument("--reason", required=True)
    n.add_argument("--out", required=True)

    m = sub.add_parser("matrix", help="print the shard matrix as compact JSON")
    m.add_argument("--plan", required=True)

    p = sub.add_parser("patterns", help="print one shard's patterns, space-joined")
    p.add_argument("--plan", required=True)
    p.add_argument("--set", required=True, dest="name")
    p.add_argument("--index", type=int, required=True)

    args = ap.parse_args(argv)

    if args.cmd == "full":
        if args.shards < 1:
            ap.error("--shards must be at least 1")
        _write(args.out, full_plan(Path(args.root), args.shards,
                                   args.reason or ["full run"]))
        return 0
    if args.cmd == "none":
        _write(args.out, none_plan(args.reason))
        return 0
    if args.cmd == "matrix":
        # One line, no spaces: it is written to $GITHUB_OUTPUT as `matrix=...`
        # and read back with fromJSON, and a newline would end the value.
        print(json.dumps(matrix(_read(args.plan)), separators=(",", ":")))
        return 0

    # patterns. Every word printed here becomes an argument to `mutmut run`,
    # and `mutmut run` with no argument runs EVERY mutant — so an empty answer
    # is a failure with nothing on stdout, never an empty line the shell would
    # turn into an unfiltered 26-minute run.
    patterns = shard_patterns(_read(args.plan), args.name, args.index)
    if not patterns:
        print("mutation_plan patterns: set %r shard %d has no patterns"
              % (args.name, args.index), file=sys.stderr)
        return 1
    print(" ".join(patterns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
