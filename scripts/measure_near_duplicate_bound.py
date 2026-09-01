#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Count near-duplicate clusters that span more than one distinct name.

`rag.dedupe_by_content`'s byte-identical bound was adoptable because one count
settled it: of 14,153 distinct bodies, the number of clusters spanning more
than one NAME was zero, so collapsing by content hash could never merge two
differently-named skills. `rag.collapse_near_duplicate_hits` has no such free
proof handed to it -- any cosine threshold loose enough to merge a translation
with its original is loose enough to merge two skills that happen to share
boilerplate.

This script re-derives the equivalent count against a real, already-built
dense store: at `rag.NEAR_DUPLICATE_THRESHOLD` (or `--threshold`), it clusters
every entry's chunk-0 vector by cosine similarity and reports how many
clusters span more than one distinct `name` -- the same proxy for "different
meaning" the byte-identical proof used.

**Two numbers matter, not one.** Entries that already share a chunk-0 vector
byte for byte cluster at *any* threshold, so a nonzero result is not
automatically the threshold's fault. `--floor` reports that share-a-vector
count on its own; the threshold is responsible only for the difference.

A cosine threshold is a property of ONE embedding space. A bound measured in
`BAAI/bge-small-en-v1.5` (384-d) says nothing about a `voyage-4` (1024-d)
store -- rerun this against each space you intend to ship the collapse in.

Usage:
    export BOOST_HOME=~/.boost   # wherever the dense store already lives
    python3 scripts/measure_near_duplicate_bound.py [--threshold 0.97] [--limit N]
"""
from __future__ import annotations

import argparse
import array
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import dense, rag


def _load_numpy():
    """numpy if importable, else None. It ships with the [rag] extra (via
    onnxruntime), so it is present wherever a dense store can exist -- but this
    script must still run without it rather than fail to start."""
    try:
        import numpy
    except ImportError:
        return None
    return numpy


def _norm(v: array.array) -> float:
    return math.sqrt(sum(x * x for x in v))


def _pairs_over_stdlib(vecs, norms, thresh):
    """Yield (i, j) whose cosine is at/above `thresh`, in pure Python.

    Norms are precomputed rather than recomputed per comparison: this is
    O(n^2) either way, but the inner loop is a dot product alone.
    """
    n = len(vecs)
    for i in range(n):
        vi, ni = vecs[i], norms[i]
        if ni == 0.0:
            continue
        for j in range(i + 1, n):
            nj = norms[j]
            if nj == 0.0:
                continue
            dot = sum(x * y for x, y in zip(vi, vecs[j], strict=True))
            if dot / (ni * nj) >= thresh:
                yield i, j


def _pairs_over_numpy(np, vecs, thresh):
    """Same pairs, as a blocked matmul. numpy ships with the [rag] extra."""
    m = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mn = m / norms
    n = len(vecs)
    for start in range(0, n, 512):
        block = mn[start:start + 512] @ mn.T
        for row in range(block.shape[0]):
            i = start + row
            for j in (block[row, i + 1:] >= thresh).nonzero()[0]:
                yield i, i + 1 + int(j)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold", type=float, default=rag.NEAR_DUPLICATE_THRESHOLD)
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the number of distinct vectors compared (O(n^2))")
    parser.add_argument("--floor", action="store_true",
                        help="report only the share-a-vector count, no comparisons")
    args = parser.parse_args(argv)

    if not dense.ready():
        print("no ready dense store -- run `boost reindex --dense` first", file=sys.stderr)
        return 1
    con = dense._connect()
    if con is None:
        print("dense store unusable here (sqlite-vec not loadable)", file=sys.stderr)
        return 1
    try:
        rows = con.execute(
            "SELECT chunks.name, vec_raw.id, vec_raw.embedding FROM chunks "
            "JOIN vec_raw ON vec_raw.id = chunks.vid WHERE chunks.cix = 0"
        ).fetchall()
    finally:
        con.close()
    if not rows:
        print("store has no chunk-0 vectors -- is it quantized? "
              "(`boost reindex --dense` builds vec_raw)", file=sys.stderr)
        return 1

    # One entry per distinct VECTOR: entries whose chunk 0 is byte-identical
    # already share a row, and comparing a vector with itself would report a
    # free cluster that says nothing about the threshold.
    by_vid: dict[int, tuple[set, array.array]] = {}
    for name, vid, blob in rows:
        names, _v = by_vid.setdefault(vid, (set(), array.array("f", blob)))
        names.add(name)

    vids = sorted(by_vid)
    if args.limit:
        vids = vids[:args.limit]
    floor = sum(1 for v in vids if len(by_vid[v][0]) > 1)
    print("%d entries over %d distinct chunk-0 vectors; %d of those vectors are "
          "shared by more than one name already" % (len(rows), len(vids), floor))
    if args.floor:
        return 0

    parent = list(range(len(vids)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    vecs = [by_vid[v][1] for v in vids]
    np = _load_numpy()
    print("comparing %d vectors at threshold %.3f (%d pairs, %s)"
          % (len(vids), args.threshold, len(vids) * (len(vids) - 1) // 2,
             "numpy" if np is not None else "stdlib -- slow"))
    gen = (_pairs_over_numpy(np, vecs, args.threshold) if np is not None
           else _pairs_over_stdlib(vecs, [_norm(v) for v in vecs], args.threshold))

    pairs_over = 0
    for i, j in gen:
        pairs_over += 1
        ra, rb = find(i), find(j)
        if ra != rb:
            parent[ra] = rb

    clusters: dict[int, set] = {}
    for i in range(len(vids)):
        clusters.setdefault(find(i), set()).update(by_vid[vids[i]][0])
    spanning = {r: n for r, n in clusters.items() if len(n) > 1}

    print("%d pairs at/above threshold, %d clusters, %d span more than one name "
          "(%d of those from vectors already shared, %d added by the threshold)"
          % (pairs_over, len(clusters), len(spanning), floor, len(spanning) - floor))
    for _root, names in sorted(spanning.items(), key=lambda kv: -len(kv[1]))[:20]:
        print("  spans %d: %s" % (len(names), ", ".join(sorted(names))[:160]))
    return 1 if spanning else 0


if __name__ == "__main__":
    raise SystemExit(main())
