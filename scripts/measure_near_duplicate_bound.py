#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Count near-duplicate clusters that span more than one distinct name.

`rag.dedupe_by_content`'s byte-identical bound was adoptable because one count
settled it: of 14,153 distinct bodies, the number of clusters spanning more
than one NAME was zero, so collapsing by content hash could never merge two
differently-named skills. `dense.collapse_near_duplicates` (roadmap item
`near-identical-copies-still-eat-the-slots`) has no such free proof handed to
it -- any cosine threshold loose enough to merge a translation with its
original is loose enough to merge two skills that happen to share
boilerplate.

This script re-derives the equivalent count against a real, already-built
dense store: at `dense.NEAR_DUP_THRESHOLD` (or `--threshold`), it clusters
every entry's chunk-0 vector -- the same vector `collapse_near_duplicates`
compares, see that function's docstring for why chunk 0 -- by cosine
similarity, and reports how many clusters span more than one distinct `name`,
the same proxy for "different meaning" the byte-identical proof used. A count
of zero supports the threshold; a nonzero count names the offending pairs so
the threshold (or the name-based "different meaning" proxy itself) can be
tightened before this collapse is trusted at production scale.

O(n^2) over the store's distinct chunk-0 vectors. That is fine for a
corpus of a few thousand entries -- the eval corpus this script was written
to be run against first -- but not for a full production install; use
`--limit` to sample a manageable slice of a larger store. **This has not yet
been run against a real multi-hundred-tap install** (see the roadmap item):
that measurement, not this script, is the outstanding half of this card's
"establish the equivalent bound first" requirement.

Usage:
    export BOOST_HOME=~/.boost   # wherever the dense store already lives
    python3 scripts/measure_near_duplicate_bound.py [--threshold 0.96] [--limit N]
"""
from __future__ import annotations

import argparse
import array
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boost_cli.core import dense


def _cosine(a: array.array, b: array.array) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold", type=float, default=dense.NEAR_DUP_THRESHOLD)
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the number of distinct vectors compared (O(n^2))")
    args = parser.parse_args(argv)

    if not dense.ready():
        print("no ready dense store -- run `boost reindex --dense` first",
             file=sys.stderr)
        return 1
    con = dense._connect()
    if con is None:
        print("dense store unusable here (sqlite-vec not loadable)",
             file=sys.stderr)
        return 1
    try:
        if not dense.quantized(con):
            print("store is not quantized -- collapse_near_duplicates is a "
                 "no-op on it, nothing to measure", file=sys.stderr)
            return 1
        rows = con.execute(
            "SELECT chunks.name, vec_raw.id, vec_raw.embedding FROM chunks "
            "JOIN vec_raw ON vec_raw.id = chunks.vid WHERE chunks.cix = 0"
        ).fetchall()
    finally:
        con.close()

    # One row per distinct VECTOR, not per entry: several entries can already
    # share a chunk-0 vector (identical name + description), and comparing a
    # vector against itself would report a free "cluster of one name" that
    # tells us nothing about the threshold.
    by_vid: dict[int, tuple[set, array.array]] = {}
    for name, vid, blob in rows:
        names, _v = by_vid.setdefault(vid, (set(), array.array("f", blob)))
        names.add(name)

    vids = sorted(by_vid)
    if args.limit:
        vids = vids[:args.limit]
    total_pairs = len(vids) * (len(vids) - 1) // 2
    print("comparing %d distinct chunk-0 vectors at threshold %.3f (%d pairs)"
         % (len(vids), args.threshold, total_pairs))

    parent = {v: v for v in vids}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    pairs_over = 0
    for i, a in enumerate(vids):
        va = by_vid[a][1]
        for b in vids[i + 1:]:
            if _cosine(va, by_vid[b][1]) >= args.threshold:
                union(a, b)
                pairs_over += 1

    clusters: dict[int, set] = {}
    for v in vids:
        clusters.setdefault(find(v), set()).update(by_vid[v][0])
    spanning = {root: names for root, names in clusters.items() if len(names) > 1}

    print("%d pairs at/above threshold, %d clusters total, %d span more than "
         "one name" % (pairs_over, len(clusters), len(spanning)))
    for _root, names in sorted(spanning.items(), key=lambda kv: sorted(kv[1]))[:20]:
        print("  spans: %s" % ", ".join(sorted(names)))
    return 1 if spanning else 0


if __name__ == "__main__":
    raise SystemExit(main())
