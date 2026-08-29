#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Performance-regression gate: complexity scaling, not wall-clock baselines.

A saved-baseline benchmark compare flakes on shared CI runners — machine speed
varies run to run, so absolute thresholds either false-alarm or sandbag. What
a gate CAN assert robustly is *how cost grows with input size*: time the hot
paths at two catalog sizes on the SAME machine in the SAME process, and fail
when the big/small ratio blows past the size ratio times a slack factor. An
accidental O(n²) (size ratio 8 → time ratio ~64×) is caught decisively; noise
and slow runners cancel out of the ratio. One generous absolute backstop
catches only catch-fire regressions.

Paths gated (the ones `boost search`/`tap` lean on):
  * catalog.scan_dir  — walking + classifying a tap tree
  * rag.build         — BM25 indexing of the scanned entries
  * rag.retrieve      — query over the built index

Usage:
  PYTHONPATH=. python3 scripts/perf_gate.py          # run the gate
  PYTHONPATH=. python3 scripts/perf_gate.py -v       # per-path timings

Deliberately NOT part of `make check`'s five-gate contract (v1 blast-radius);
CI runs it in the lint job. The opt-in micro-benchmarks (tests/perf, `make
bench`) remain the profiling tool; this is the regression tripwire.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

# Run from a source checkout without an install (same shim as the eval gate).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SMALL, BIG = 64, 512          # catalog sizes; 8× input
SLACK = 3.0                   # fail when time-ratio > size-ratio × SLACK (24×)
ABS_BACKSTOP_S = 30.0         # any single big-size op slower than this fails
MIN_SAMPLE_S = 0.05           # repeat an op until a sample is ≥ 50ms (jitter)
BEST_OF = 3


def _mk_catalog(root: Path, n: int) -> None:
    """Materialize a synthetic tap tree with n skills + n rules + n workflows.

    Content scales with the tree so indexing has real text to chew on, and
    names are unique per size so nothing is accidentally shared or cached.
    """
    lorem = ["retrieval", "augmentation", "index", "tokens", "ranking", "corpus", "recall", "precision", "embedding", "catalog", "skill", "agent", "workflow", "rule"]
    for i in range(n):
        d = root / ("skill-%04d" % i)
        d.mkdir(parents=True)
        words = " ".join(lorem[(i + j) % len(lorem)] for j in range(60))
        (d / "SKILL.md").write_text(
            "---\nname: skill-%04d\ndescription: synthetic skill %d for the "
            "perf gate\n---\n\n# skill-%04d\n\n%s\n" % (i, i, i, words),
            encoding="utf-8")
        (root / "rules" / ("rule-%04d.mdc" % i)).parent.mkdir(exist_ok=True)
        (root / "rules" / ("rule-%04d.mdc" % i)).write_text(
            "---\ndescription: synthetic rule %d\n---\nAlways %s.\n"
            % (i, " ".join(lorem[i % len(lorem)] for _ in range(20))),
            encoding="utf-8")
        (root / "commands" / ("wf-%04d.md" % i)).parent.mkdir(exist_ok=True)
        (root / "commands" / ("wf-%04d.md" % i)).write_text(
            "# wf-%04d\n\nRun the synthetic workflow %d: %s\n"
            % (i, i, words[:120]), encoding="utf-8")


def _time(fn) -> float:
    """Best-of-BEST_OF timing; each sample loops fn until ≥ MIN_SAMPLE_S."""
    best = float("inf")
    for _ in range(BEST_OF):
        reps = 0
        t0 = time.perf_counter()
        while True:
            fn()
            reps += 1
            dt = time.perf_counter() - t0
            if dt >= MIN_SAMPLE_S:
                break
        best = min(best, dt / reps)
    return best


def _measure(size: int, verbose: bool) -> dict:
    """Time the three hot paths against a fresh synthetic catalog of `size`."""
    from boost_cli.core import catalog, rag

    with tempfile.TemporaryDirectory(prefix="perfgate-") as tmp:
        tap = Path(tmp) / "tap"
        _mk_catalog(tap, size)
        os.environ["BOOST_HOME"] = str(Path(tmp) / "home")
        os.environ["HOME"] = tmp

        out = {"scan": _time(lambda: catalog.scan_dir(tap, "perf"))}
        entries = catalog.scan_dir(tap, "perf")
        if len(entries) != 3 * size:  # a generator bug would invalidate ratios
            raise SystemExit("perf-gate: generator drift: %d entries for n=%d"
                             % (len(entries), size))

        # build is once-per-corpus in real life — time single builds (forced).
        best = float("inf")
        for _ in range(BEST_OF):
            t0 = time.perf_counter()
            rag.build(entries, force=True)
            best = min(best, time.perf_counter() - t0)
        out["build"] = best

        out["retrieve"] = _time(
            lambda: rag.retrieve("ranking corpus recall skill", k=20))
        if verbose:
            for k, v in out.items():
                print("  n=%-4d %-9s %8.1f ms" % (size, k, v * 1000))
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    small = _measure(SMALL, args.verbose)
    big = _measure(BIG, args.verbose)

    size_ratio = BIG / SMALL
    limit = size_ratio * SLACK
    failed = []
    for path in ("scan", "build", "retrieve"):
        ratio = big[path] / small[path] if small[path] > 0 else float("inf")
        line = "%-9s %7.1fms -> %8.1fms  ratio %5.1fx (limit %.0fx)" % (
            path, small[path] * 1000, big[path] * 1000, ratio, limit)
        ok = ratio <= limit and big[path] <= ABS_BACKSTOP_S
        print(("  PASS " if ok else "  FAIL ") + line)
        if not ok:
            failed.append(path)

    if failed:
        print("perf-gate: FAILED — superlinear scaling (or >%ds backstop) on: %s"
              % (int(ABS_BACKSTOP_S), ", ".join(failed)), file=sys.stderr)
        return 1
    print("perf-gate: OK — all paths scale within %.0fx of linear at %dx input"
          % (SLACK, int(size_ratio)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
