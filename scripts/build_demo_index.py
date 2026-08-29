#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Emit a compact BM25 index for the browser demo on the docs site.

WHY A SEPARATE ARTEFACT. The live index is 4.65 MB across a JSON file and a
SQLite postings store — fine on disk, wasteful to hand a browser. This packs the
same data into one gzip-friendly JSON: postings as parallel arrays, documents
trimmed to what a result row actually shows.

WHAT THE DEMO CAN AND CANNOT SHOW. BM25 is arithmetic, so it ports to the
browser exactly — the scorer in demo.js mirrors `rag._bm25` term for term, and
the tokenizer mirrors `rag.tokenize`. The *semantic* half cannot: embedding a
query needs the 133 MB local model, and shipping that to a visitor (or paying
for a hosted inference endpoint) is not a free tier. So the demo is honest about
being the keyword engine, and the page says so rather than implying otherwise.

Run:  BOOST_HOME=<a home with a built index> python3 scripts/build_demo_index.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from boost_cli.core import rag  # noqa: E402

OUT = ROOT / "docs" / "demo-index.json"
# Snippets dominate the payload and a result row shows ~160 chars of one.
SNIP = 180


def main() -> int:
    raw = rag._load_raw()
    if not raw or not raw.get("docs"):
        print("no BM25 index — run `boost reindex` against BOOST_HOME first",
              file=sys.stderr)
        return 1
    postings = rag._all_postings()
    if not postings:
        print("no postings store — run `boost reindex` first", file=sys.stderr)
        return 1

    docs = [{
        "n": d["n"],
        "t": d["t"],
        "k": d.get("k", "skill"),
        "l": d["l"],
        "s": (d.get("snip") or "")[:SNIP],
    } for d in raw["docs"]]

    # Parallel arrays rather than [[doc, tf], ...] pairs: same information, far
    # fewer JSON delimiters, and it gzips better over the wire.
    packed = {t: [[p[0] for p in pl], [p[1] for p in pl]]
              for t, pl in postings.items()}

    payload = {
        "generated_from": "boost BM25 index",
        "k1": rag.K1,
        "b": rag.B,
        "avg_len": raw.get("stats", {}).get("avg_len") or 1.0,
        "docs": docs,
        "postings": packed,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    size = OUT.stat().st_size / 1e6
    print("wrote %s — %d docs, %d terms, %.2f MB"
          % (OUT.relative_to(ROOT), len(docs), len(packed), size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
