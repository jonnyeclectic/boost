#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Pack the registry catalogue into a bounded, balanced Actions matrix.

WHY THIS EXISTS. `shards.yml` ran one job per registry, which is fine for the
20-repo eval corpus and impossible for the 463-registry catalogue: **GitHub
caps a matrix at 256 jobs per workflow run**, so 463 rows do not start at all.
Chunking is therefore not an optimisation, it is the difference between the
workflow running and not.

WHY BIN-PACKING RATHER THAN SLICING. Embedding cost is wildly uneven — the
catalogue's largest registry is 880 measured items against a median of 30 and a
minimum of 1 — so a naive `chunk(n)` puts several giants in one job and leaves
others with nothing. The whole run then takes as long as its unluckiest chunk, against
a hard 6-hour job ceiling. Longest-processing-time-first (sort by cost
descending, always add to the currently cheapest bin) is the standard greedy
answer and is within 4/3 of optimal, which is far inside the margin that
matters here. The practical effect is that the biggest registry ends up
effectively alone in its bin, which is exactly what you want: it is the run's
critical path either way.

COST PROXY. `est_items` from the bundled catalogue, which is *measured* (see
`scripts/measure_registry.py`) rather than guessed. It is a proxy for chunk
count, not chunk count itself — deduplication means a registry that mirrors
itself is cheaper than its size suggests — but it is the only per-registry
number available before cloning, and it is right about the ordering, which is
what the packing needs.

    shard_plan.py --scope catalog                 # matrix JSON for GITHUB_OUTPUT
    shard_plan.py --scope catalog --explain       # what each job would carry
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import config

#: GitHub's documented ceiling. Not a tunable — a matrix that exceeds it fails
#: the whole run before a single job starts.
MAX_MATRIX_JOBS = 256

#: Default jobs to plan for. Under the ceiling with room to spare, and enough
#: parallelism that the run is bounded by its largest registry rather than by
#: how many bins there are.
DEFAULT_JOBS = 60


def catalog_rows(include_lists: bool = False) -> list[dict]:
    """Every catalogued registry as ``{"name", "cost"}``, biggest first."""
    rows = []
    for entry in config.load_registry_catalog():
        if not include_lists and entry.get("list_only"):
            # An awesome-list repo indexes other repos; there is nothing of its
            # own to embed.
            continue
        name = str(entry.get("name") or "")
        if not name:
            continue
        rows.append({"name": name, "cost": int(entry.get("est_items") or 0)})
    rows.sort(key=lambda r: (-r["cost"], r["name"]))
    return rows


def pack(rows: list[dict], jobs: int) -> list[list[str]]:
    """Longest-processing-time-first packing into at most `jobs` bins.

    Deterministic: rows arrive sorted by (-cost, name), and ties between bins
    are broken by index, so the same catalogue always plans the same matrix.
    That matters for reruns — a rerun that repacked differently would re-embed
    registries whose shards were already published.
    """
    if jobs < 1:
        raise SystemExit("--jobs must be at least 1")
    bins: list[list[str]] = [[] for _ in range(min(jobs, max(1, len(rows))))]
    loads = [0] * len(bins)
    for row in rows:
        i = loads.index(min(loads))
        bins[i].append(row["name"])
        loads[i] += row["cost"]
    return [b for b in bins if b]


def plan(scope: str, jobs: int, include_lists: bool = False) -> list[list[str]]:
    """The matrix for `scope`, as a list of registry-name lists."""
    if scope == "eval":
        # The pinned corpus every other gate measures against: one job per
        # registry, because there are twenty of them and no packing is needed.
        import subprocess
        out = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("eval_corpus.py")),
             "--list-repos"], check=True, capture_output=True, text=True).stdout
        return [[name] for name in out.split()]
    rows = catalog_rows(include_lists=include_lists)
    if not rows:
        raise SystemExit("the bundled registry catalogue is empty")
    return pack(rows, jobs)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scope", choices=("catalog", "eval"), default="catalog",
                   help="which registries to shard (default: %(default)s)")
    p.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                   help="how many matrix jobs to plan for (default: %(default)s)")
    p.add_argument("--include-lists", action="store_true",
                   help="also shard awesome-list/index repos")
    p.add_argument("--explain", action="store_true",
                   help="print the packing as a table instead of JSON")
    args = p.parse_args(argv)

    if args.jobs > MAX_MATRIX_JOBS:
        raise SystemExit(
            "--jobs %d exceeds GitHub's %d-job matrix ceiling; the run would "
            "fail before starting" % (args.jobs, MAX_MATRIX_JOBS))
    chunks = plan(args.scope, args.jobs, args.include_lists)
    if len(chunks) > MAX_MATRIX_JOBS:
        raise SystemExit("planned %d jobs, over the %d-job ceiling"
                         % (len(chunks), MAX_MATRIX_JOBS))
    if args.explain:
        costs = {r["name"]: r["cost"] for r in catalog_rows(args.include_lists)}
        for i, chunk in enumerate(chunks):
            load = sum(costs.get(n, 0) for n in chunk)
            print("job %2d  %5d est. items  %2d registries  %s"
                  % (i, load, len(chunk),
                     ", ".join(chunk[:3]) + (" …" if len(chunk) > 3 else "")))
        loads = [sum(costs.get(n, 0) for n in c) for c in chunks]
        print("\n%d jobs · %d registries · %d est. items · heaviest %d, "
              "lightest %d" % (len(chunks), sum(len(c) for c in chunks),
                               sum(loads), max(loads), min(loads)))
        return 0
    # One matrix entry per job: a space-separated list the workflow splits in
    # Python, never in shell — `shards.yml`'s header records what happened the
    # last time a list was word-split by the runner.
    print(json.dumps([" ".join(chunk) for chunk in chunks]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
