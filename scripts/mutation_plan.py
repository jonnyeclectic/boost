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

    {"gate_set": "full" | "diff" | null,
     "reasons":  ["why this plan, in words a reviewer can check"],
     "sets":     {"<set>": {"shards": [[pattern, ...], ...],
                            "mutants": <int> | null,
                            "functions": [qualified, ...],     # diff only
                            "counts": {qualified: <int>}}}}    # diff only

``sets`` is keyed by name so a run can carry more than one: ``full`` (the
committed 24-way pack of every mutant in ``boost_cli/core``) and ``diff`` (the
mutants of the functions a PR changed plus their direct callers, see
``mutation_diff.py``). ``gate_set`` names the set the required ``mutation``
check scores. Two plans mean "nothing to score": ``null`` (``none``: nothing
mutable changed) and ``"diff"`` with ``sets.diff.shards == []`` (core changed,
but no function body did, or the ones that did have no mutants left).
``matrix`` and ``patterns`` are generic over set names on purpose, so a new set
needs a planner change and nothing else.

Usage
-----
  mutation_plan.py full --shards 24 --out PLAN      # every mutant, committed pack
  mutation_plan.py none --reason TEXT --out PLAN    # nothing to run, and why
  mutation_plan.py base --event E --sha SHA --base-sha B --head-sha H
                                                    # the diff base, on stdout
  mutation_plan.py diff --base SHA --head SHA --stats mutants/mutmut-stats.json \
                        [--shadow] --out PLAN       # the PR's functions, or full
  mutation_plan.py matrix --plan PLAN               # [{"set":..,"index":..}, ...]
  mutation_plan.py patterns --plan PLAN --set S --index I   # one shard's argv
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
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


def _load_diff():
    """Import ``mutation_diff`` lazily, only for the ``diff`` subcommand.

    It imports mutmut and PyYAML at module level; ``matrix`` and ``patterns``
    run in every shard and the planner tests must run where PyYAML is absent,
    so neither may pay for an import they never use.
    """
    spec = importlib.util.spec_from_file_location(
        "mutation_diff", Path(__file__).resolve().parent / "mutation_diff.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load mutation_diff.py beside %s" % __file__)
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: `@dataclass` looks its own module up in
    # sys.modules, and an unregistered module crashes it at import.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(root: Path, *args: str) -> bytes:
    # An argv list, never a shell string: mangled method names (`xǁKǁm`) and
    # paths go through untouched by word-splitting or globbing. check=True:
    # a git failure fails the planner, and so the required `mutation` check.
    return subprocess.run(["git", "--literal-pathspecs", *args], cwd=root,
                          check=True, capture_output=True).stdout


def git_reader(root: Path, base: str, head: str):
    """``read(rev, path)`` over two commits: the file's text, or ``None`` if absent.

    Both revisions are verified up front. Without that, a typo'd or unfetched
    SHA makes every ``git show`` fail, every file reads as absent, the scope
    comes out empty, and an empty scope is a pass.

    For the same reason "absent" is decided from the *tree* (``ls-tree``, which
    needs no blobs), never from ``git show`` failing: in a partial clone whose
    lazy blob fetch fails, a changed core file would otherwise read as deleted.
    A path the tree lists but git cannot read is an error.
    """
    revs = {"base": base, "head": head}
    for rev in revs.values():
        _git(root, "rev-parse", "--verify", "--quiet", rev + "^{commit}")
    cache: dict[tuple[str, str], str | None] = {}

    def read(rev: str, path: str) -> str | None:
        key = (revs[rev], path)
        if key not in cache:
            listed = _git(root, "ls-tree", "--full-tree", "--name-only", "-z",
                          key[0], "--", path).split(b"\0")
            cache[key] = (_git(root, "show", "%s:%s" % key).decode("utf-8")
                          if path.encode("utf-8") in listed else None)
        return cache[key]

    return read


def changed_paths(root: Path, base: str, head: str) -> list[str]:
    """Paths changed between two commits; a rename is a delete plus an add.

    ``-z`` so ``core.quotePath`` cannot octal-escape a non-ASCII path into a
    name that matches nothing.
    """
    out = _git(root, "diff", "--name-only", "--no-renames", "-z", base, head)
    return [p for p in out.decode("utf-8").split("\0") if p]


def diff_base(root: Path, event: str, sha: str, *, base_sha: str,
              head_sha: str) -> tuple[str, str]:
    """The commit to diff ``sha`` against, and a line saying how it was chosen.

    ``sha`` is the commit the shards check out. On a pull request that is
    GitHub's merge commit (``refs/pull/N/merge``), whose first parent is the
    base it was merged onto: diffing against it is the PR's change exactly as
    applied to the tree the shards test. When ``sha`` is not a two-parent
    merge, the merge base of the event's base and head stands in. It is wider
    whenever main has moved since the branch point (main's interim changes
    join the scope), which is the safe direction. A merge-queue entry is
    built on ``base_sha``, so that is its base.

    Every git failure propagates (``check=True``): an unknown or empty SHA
    must stop the diff plan, and ci.yml then plans the full run instead.
    """
    if event == "pull_request":
        line = _git(root, "rev-list", "--parents", "-n1", sha + "^{commit}")
        parents = line.decode("utf-8").split()[1:]
        if len(parents) == 2:
            return parents[0], "first parent of %s (the PR as merged)" % sha
        base = _git(root, "merge-base", base_sha, head_sha).decode("utf-8").strip()
        return base, ("merge base of %s and %s (%s has %d parents, not 2; "
                      "wider than the PR alone)"
                      % (base_sha, head_sha, sha, len(parents)))
    if event == "merge_group":
        base = _git(root, "rev-parse", "--verify", base_sha + "^{commit}")
        return base.decode("utf-8").strip(), "merge_group base_sha %s" % base_sha
    raise ValueError("no diff base for event %r" % event)


def diff_plan(root: Path, base: str, head: str, stats: Path, *,
              shadow: bool = False, shards: int = FULL_SHARDS,
              per_shard: int | None = None) -> dict[str, Any]:
    """The diff-scoped plan for ``base..head``, or the full one when forced.

    A full-run trigger (``mutation_diff.full_run_reasons``) returns exactly
    the ``full`` plan with those reasons. Otherwise every mutant of every
    in-scope function is counted with mutmut's own generator at ``head`` and
    packed by measured time; ``--shadow`` also carries the full set and gates
    on it, so the two can be compared on one SHA before the diff gate binds.
    """
    md = _load_diff()
    read = git_reader(root, base, head)
    changed = changed_paths(root, base, head)
    reasons = md.full_run_reasons(changed, read)
    if reasons:
        return full_plan(root, shards, reasons)

    # A stats file without the key would scope no callers at all; refuse
    # rather than under-scope (a KeyError fails the planner, so `mutation`).
    deps = json.loads(Path(stats).read_text(encoding="utf-8"))["function_dependencies"]
    scope = md.diff_scope(changed, read, deps)

    by_file: dict[str, list[tuple[str, str]]] = {}
    for q in scope:
        path, mangled = md.split_qualified(q)
        by_file.setdefault(path, []).append((q, mangled))
    counts: dict[str, int] = {}
    with md.mutmut_config(root):
        for path, funcs in sorted(by_file.items()):
            src = read("head", path)
            if src is None:
                continue  # the file is gone at head: nothing left to mutate
            per_function = md.mutant_counts(path, src)
            for q, mangled in funcs:
                # A deleted function, or one with nothing to mutate, gets no
                # pattern: mutmut asserts when a pattern matches no mutant.
                if per_function.get(mangled):
                    counts[q] = per_function[mangled]

    bins = md.pack_functions(counts, md.ms_per_mutant(root, list(counts)),
                             per_shard=per_shard or md.PER_SHARD)
    # `matrix` keeps an empty shard on purpose (it would be a slice of the full
    # pack that nobody ran). Here an empty bin is only arithmetic — one
    # function can't be split across shards — and every function is already
    # in a non-empty bin, so dropping it loses nothing and keeps `patterns`
    # from failing that shard.
    shard_patterns_ = [[md.pattern(q) for q in b] for b in bins if b]
    total = sum(counts.values())
    if total:
        why = ("diff scope: %d mutants in %d functions (changed + direct callers), "
               "%d shards" % (total, len(counts), len(shard_patterns_)))
    elif scope:
        why = "diff scope: %d functions in scope, none with mutants" % len(scope)
    else:
        why = "diff scope: no boost_cli/core function changed"
    plan: dict[str, Any] = {
        "gate_set": "diff",
        "reasons": [why],
        "sets": {"diff": {"shards": shard_patterns_, "mutants": total,
                          "functions": scope,
                          # Per-function, so the gate can tell one function's
                          # shortfall from another's surplus.
                          "counts": {q: counts[q] for q in sorted(counts)}}},
    }
    if shadow:
        plan["sets"]["full"] = full_plan(root, shards, [])["sets"]["full"]
        plan["gate_set"] = "full"
        plan["reasons"].append("shadow: gating on the full run; the diff set "
                               "runs alongside for comparison")
    return plan


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

    d = sub.add_parser("diff", help="plan the PR's changed functions (or full)")
    d.add_argument("--base", required=True, help="merge-base SHA")
    d.add_argument("--head", required=True, help="PR head SHA")
    d.add_argument("--stats", required=True, help="mutants/mutmut-stats.json")
    d.add_argument("--shadow", action="store_true",
                   help="also plan the full set, and gate on it")
    d.add_argument("--shards", type=int, default=FULL_SHARDS,
                   help="full set's width when forced or shadowed")
    d.add_argument("--root", default=str(ROOT), help="repo root (default: this checkout)")
    d.add_argument("--out", required=True)

    b = sub.add_parser("base", help="print the commit the diff plan diffs against")
    b.add_argument("--event", required=True, help="github.event_name")
    b.add_argument("--sha", required=True, help="the commit the shards check out")
    b.add_argument("--base-sha", required=True, help="the event's base SHA")
    b.add_argument("--head-sha", required=True, help="the event's head SHA")
    b.add_argument("--root", default=str(ROOT), help="repo root (default: this checkout)")

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
    if args.cmd == "diff":
        if args.shards < 1:
            ap.error("--shards must be at least 1")
        _write(args.out, diff_plan(Path(args.root), args.base, args.head,
                                   Path(args.stats), shadow=args.shadow,
                                   shards=args.shards))
        return 0
    if args.cmd == "base":
        # The SHA alone on stdout, because ci.yml captures it with $(...); the
        # reason on stderr, so the log says which base the plan used.
        try:
            base, why = diff_base(Path(args.root), args.event, args.sha,
                                  base_sha=args.base_sha, head_sha=args.head_sha)
        except (subprocess.CalledProcessError, ValueError) as exc:
            detail = getattr(exc, "stderr", None) or b""
            print("mutation_plan base: %s %s" % (exc, detail.decode("utf-8", "replace").strip()),
                  file=sys.stderr)
            return 1
        print("mutation_plan base: %s -- %s" % (base, why), file=sys.stderr)
        print(base)
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
