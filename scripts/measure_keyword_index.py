#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Measure the BM25 postings store in every layout it has had, x compression.

`publish-the-keyword-index` needs a size answer before it can ship anything,
and `shrink-the-published-index` asked for that answer as one table: each
on-disk layout x none/gzip/zstd, with the import-side decode cost beside each
and the query-side read cost beside each layout. This script re-derives it
from a real, already-built store, so the numbers in the roadmap card are
falsifiable rather than remembered.

The layouts, all built here from the SAME postings:

* ``rows-text`` (index v1-v6): ``postings(term TEXT, doc, tf)`` plus a
  text-keyed index -- the term string repeated on every posting row.
* ``rows-interned`` (v7-v9): ``terms(id, term, df)`` plus
  ``postings(term_id, doc, tf)`` and an integer index -- one row per posting.
* ``blob-delta-varint`` (v10, what boost ships): ``terms`` unchanged, plus one
  ``postings(term_id PRIMARY KEY, plist BLOB)`` row per term. It is written by
  ``rag._fill_postings`` itself, so the table measures the shipped code.

"import decode" is the time to decompress the artifact back to the file a user
ends up with. "query read" is the time to fetch the postings of every golden
query's terms, one reader call per query the way ``rag.retrieve`` does it --
the property ``read_postings`` exists for, which a layout must not regress.
Reads run on a warm page cache. Every layout's reader must return identical
postings for those terms, or the script exits non-zero.

The source store is opened read-only and never written. Everything else goes
in ``--workdir`` (a fresh temp dir by default).

Usage:
    python3 scripts/measure_keyword_index.py [--store PATH] [--index PATH]
        [--queries tests/eval/golden.jsonl ...] [--codecs none,gzip-6,zstd-3,zstd-19]
        [--layouts rows-text,rows-interned,blob-delta-varint] [--json]
"""
from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from boost_cli.core import paths, rag  # noqa: E402

Postings = dict[str, list[list[int]]]
LAYOUTS = ("rows-text", "rows-interned", "blob-delta-varint")
CODECS = ("none", "gzip-6", "zstd-3", "zstd-19")
DEFAULT_QUERIES = (ROOT / "tests" / "eval" / "golden.jsonl",
                   ROOT / "tests" / "eval" / "golden-natural.jsonl")


# --- reading the source store -------------------------------------------------

def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute("PRAGMA table_info(%s)" % table)]


def detect_layout(con: sqlite3.Connection) -> str:
    """Name the layout of an open postings store, or raise ``ValueError``."""
    cols = _columns(con, "postings")
    if "plist" in cols:
        return "blob-delta-varint"
    if "term_id" in cols:
        return "rows-interned"
    if "term" in cols:
        return "rows-text"
    raise ValueError("not a boost postings store (postings columns: %r)" % cols)


def load_postings(store: Path) -> Postings:
    """Every posting in ``store``, whichever layout wrote it, doc-ascending."""
    con = sqlite3.connect("file:%s?mode=ro" % store, uri=True)
    try:
        layout = detect_layout(con)
        out: Postings = {}
        if layout == "blob-delta-varint":
            for term, blob in con.execute(
                    "SELECT t.term, p.plist FROM postings p "
                    "JOIN terms t ON p.term_id = t.id ORDER BY t.id"):
                out[term] = rag._decode_plist(blob)
            return out
        q = ("SELECT term, doc, tf FROM postings ORDER BY rowid"
             if layout == "rows-text" else
             "SELECT t.term, p.doc, p.tf FROM postings p "
             "JOIN terms t ON p.term_id = t.id ORDER BY p.rowid")
        for term, doc, tf in con.execute(q):
            out.setdefault(term, []).append([doc, tf])
    finally:
        con.close()
    for plist in out.values():
        plist.sort()
    return out


# --- writing each layout ------------------------------------------------------

def _fresh(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    return con


def write_rows_text(path: Path, postings: Postings) -> None:
    """The pre-v7 layout, recovered from 693601fd's `_write_postings`."""
    con = _fresh(path)
    try:
        con.execute("CREATE TABLE postings (term TEXT, doc INTEGER, tf INTEGER)")
        con.executemany(
            "INSERT INTO postings (term, doc, tf) VALUES (?, ?, ?)",
            ((term, doc, tf) for term, plist in postings.items()
             for doc, tf in plist))
        con.execute("CREATE INDEX postings_term ON postings(term)")
        con.commit()
    finally:
        con.close()


def write_rows_interned(path: Path, postings: Postings) -> None:
    """The v7-v9 layout: interned terms, one row per posting."""
    con = _fresh(path)
    try:
        con.execute("CREATE TABLE terms (id INTEGER PRIMARY KEY, "
                    "term TEXT NOT NULL, df INTEGER NOT NULL)")
        con.execute("CREATE TABLE postings (term_id INTEGER, doc INTEGER, "
                    "tf INTEGER)")
        items = list(postings.items())
        con.executemany(
            "INSERT INTO terms (id, term, df) VALUES (?, ?, ?)",
            ((i, term, len(plist)) for i, (term, plist) in enumerate(items)))
        con.executemany(
            "INSERT INTO postings (term_id, doc, tf) VALUES (?, ?, ?)",
            ((i, doc, tf) for i, (_t, plist) in enumerate(items)
             for doc, tf in plist))
        con.execute("CREATE UNIQUE INDEX terms_term ON terms(term)")
        con.execute("CREATE INDEX postings_term_id ON postings(term_id)")
        con.commit()
    finally:
        con.close()


def write_blob(path: Path, postings: Postings) -> None:
    """The shipped layout, written by boost's own `rag._fill_postings`."""
    con = _fresh(path)
    try:
        rag._fill_postings(con, postings)
    finally:
        con.close()


WRITERS: dict[str, Callable[[Path, Postings], None]] = {
    "rows-text": write_rows_text,
    "rows-interned": write_rows_interned,
    "blob-delta-varint": write_blob,
}


# --- reading each layout the way a query does ---------------------------------

def read_terms(con: sqlite3.Connection, layout: str,
               terms: Sequence[str]) -> Postings:
    """Postings for ``terms`` from ``con``, read the way each layout's reader
    did (one indexed lookup per term; blob layout decodes on the spot)."""
    uniq = sorted(set(terms))
    if not uniq:
        return {}
    marks = ",".join("?" * len(uniq))
    out: Postings = {}
    if layout == "blob-delta-varint":
        for term, blob in con.execute(
                "SELECT t.term, p.plist FROM postings p "  # noqa: S608  only `?` placeholders
                "JOIN terms t ON p.term_id = t.id WHERE t.term IN (%s)" % marks,
                uniq):
            out[term] = rag._decode_plist(blob)
        return out
    q = ("SELECT term, doc, tf FROM postings WHERE term IN (%s)" % marks  # noqa: S608
         if layout == "rows-text" else
         "SELECT t.term, p.doc, p.tf FROM postings p "  # noqa: S608
         "JOIN terms t ON p.term_id = t.id WHERE t.term IN (%s)" % marks)
    for term, doc, tf in con.execute(q, uniq):
        out.setdefault(term, []).append([doc, tf])
    return out


def query_terms(files: Iterable[Path]) -> list[list[str]]:
    """Each golden query as `rag.tokenize` sees it; blank/comment lines skip."""
    out: list[list[str]] = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            terms = rag.tokenize(json.loads(line)["query"])
            if terms:
                out.append(terms)
    return out


def digest(postings: Postings) -> str:
    """A layout-independent fingerprint of what one read returned."""
    canon = sorted((term, sorted(map(tuple, plist)))
                   for term, plist in postings.items())
    return hashlib.sha256(repr(canon).encode()).hexdigest()


def time_queries(path: Path, layout: str,
                 queries: Sequence[Sequence[str]]) -> tuple[dict, list[str]]:
    """Per-query read latency in ms, and a digest of what each query read.

    Digests, not the postings themselves: holding every query's result alive
    grows the heap until a cyclic-GC pass lands inside a later read, which
    is a cost of this loop and not of the layout being timed.
    """
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        for q in queries:              # warm the page cache: steady state only
            read_terms(con, layout, q)
        ms: list[float] = []
        got: list[str] = []
        for q in queries:
            t0 = time.perf_counter()
            res = read_terms(con, layout, q)
            ms.append((time.perf_counter() - t0) * 1000)
            got.append(digest(res))
            del res
    finally:
        con.close()
    if not ms:
        return {"queries": 0, "total_ms": 0.0, "p50_ms": 0.0,
                "max_ms": 0.0}, got
    return {"queries": len(ms), "total_ms": sum(ms),
            "p50_ms": statistics.median(ms), "max_ms": max(ms)}, got


# --- compression ---------------------------------------------------------------

def _zstd_module():
    """`compression.zstd` (3.14+), else `zstandard`, else None."""
    for name in ("compression.zstd", "zstandard"):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


def codec_available(codec: str) -> bool:
    if codec in ("none", "gzip-6"):
        return True
    if codec.startswith("zstd-"):
        return _zstd_module() is not None or shutil.which("zstd") is not None
    return False


def compress(data: bytes, codec: str) -> bytes:
    """``data`` under ``codec``; raises ``ValueError`` for an unknown codec."""
    if codec == "none":
        return data
    if codec == "gzip-6":
        return gzip.compress(data, compresslevel=6, mtime=0)
    if codec.startswith("zstd-"):
        level = int(codec.split("-", 1)[1])
        mod = _zstd_module()
        if mod is not None and mod.__name__ == "compression.zstd":
            opts = {mod.CompressionParameter.compression_level: level,
                    mod.CompressionParameter.nb_workers: os.cpu_count() or 1}
            return mod.compress(data, options=opts)
        if mod is not None:
            return mod.ZstdCompressor(level=level, threads=-1).compress(data)
        return subprocess.run(
            ["zstd", "-q", "-c", "-T0", "-%d" % level],
            input=data, capture_output=True, check=True).stdout
    raise ValueError("unknown codec %r (known: %s)" % (codec, ", ".join(CODECS)))


def decompress(data: bytes, codec: str) -> bytes:
    if codec == "none":
        return data
    if codec == "gzip-6":
        return gzip.decompress(data)
    if codec.startswith("zstd-"):
        mod = _zstd_module()
        if mod is not None and mod.__name__ == "compression.zstd":
            return mod.decompress(data)
        if mod is not None:
            return mod.ZstdDecompressor().decompressobj().decompress(data)
        return subprocess.run(
            ["zstd", "-q", "-d", "-c"], input=data,
            capture_output=True, check=True).stdout
    raise ValueError("unknown codec %r (known: %s)" % (codec, ", ".join(CODECS)))


def codec_cells(data: bytes, codec: str) -> dict:
    """Size, ratio and timings of one artifact under one codec."""
    if not codec_available(codec):
        return {"codec": codec, "bytes": None}
    t0 = time.perf_counter()
    packed = compress(data, codec)
    t1 = time.perf_counter()
    back = decompress(packed, codec)
    t2 = time.perf_counter()
    if back != data:
        raise RuntimeError("%s did not round-trip" % codec)
    return {"codec": codec, "bytes": len(packed),
            "ratio": len(data) / len(packed) if packed else 0.0,
            "compress_s": t1 - t0, "decode_s": t2 - t1}


# --- the whole measurement ----------------------------------------------------

def measure(store: Path, workdir: Path, layouts: Sequence[str],
            codecs: Sequence[str], queries: Sequence[Sequence[str]],
            index: Path | None = None) -> dict:
    postings = load_postings(store)
    report: dict = {
        "source": {"store": str(store),
                   "terms": len(postings),
                   "postings": sum(len(p) for p in postings.values()),
                   "queries": len(queries)},
        "layouts": [],
    }
    built: dict[str, float] = {}
    for layout in layouts:
        t0 = time.perf_counter()
        WRITERS[layout](workdir / ("%s.sqlite" % layout), postings)
        built[layout] = time.perf_counter() - t0
    # Time reads only once the multi-GB in-memory postings map is gone: with
    # it alive, a cyclic-GC pass over it lands inside some query's read and
    # reports a multi-second "max" that no real `boost search` process pays.
    del postings
    gc.collect()
    reference: list[str] | None = None
    for layout in layouts:
        path = workdir / ("%s.sqlite" % layout)
        reads, got = time_queries(path, layout, queries)
        if reference is None:
            reference = got
        elif got != reference:
            raise RuntimeError("%s read different postings than %s"
                               % (layout, layouts[0]))
        data = path.read_bytes()
        report["layouts"].append({
            "layout": layout, "bytes": len(data), "build_s": built[layout],
            "reads": reads,
            "codecs": [codec_cells(data, c) for c in codecs]})
        del data
    if index is not None and index.exists():
        data = index.read_bytes()
        report["docs_json"] = {"bytes": len(data),
                               "codecs": [codec_cells(data, c) for c in codecs]}
    return report


def _mb(n: float | None) -> str:
    return "n/a" if n is None else "%.1f MB" % (n / 1e6)


def render_markdown(report: dict) -> str:
    src = report["source"]
    lines = ["Source: %s -- %s terms, %s postings, %d golden queries."
             % (src["store"], format(src["terms"], ","),
                format(src["postings"], ","), src["queries"]), ""]
    codecs = [c["codec"] for c in report["layouts"][0]["codecs"]] \
        if report["layouts"] else []
    head = ["layout", "build", "query read (total / p50 / max)"] + [
        "%s (import decode)" % c for c in codecs]
    lines += ["| " + " | ".join(head) + " |",
              "|" + "---|" * len(head)]
    for row in report["layouts"]:
        r = row["reads"]
        cells = [row["layout"], "%.1f s" % row["build_s"],
                 "%.1f / %.2f / %.2f ms" % (r["total_ms"], r["p50_ms"],
                                            r["max_ms"])]
        for c in row["codecs"]:
            if c["bytes"] is None:
                cells.append("n/a")
            elif c["codec"] == "none":
                cells.append(_mb(c["bytes"]))
            else:
                cells.append("%s, %.2fx (%.2f s)" % (_mb(c["bytes"]),
                                                     c["ratio"], c["decode_s"]))
        lines.append("| " + " | ".join(cells) + " |")
    docs = report.get("docs_json")
    if docs:
        cells = ["rag_index.json (docs, any layout)", "", ""]
        for c in docs["codecs"]:
            cells.append("n/a" if c["bytes"] is None else
                         _mb(c["bytes"]) if c["codec"] == "none" else
                         "%s, %.2fx (%.2f s)" % (_mb(c["bytes"]), c["ratio"],
                                                 c["decode_s"]))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _csv(value: str, known: Sequence[str], what: str) -> list[str]:
    items = [v.strip() for v in value.split(",") if v.strip()]
    bad = [v for v in items if v not in known]
    if bad or not items:
        raise argparse.ArgumentTypeError(
            "unknown %s %r (known: %s)" % (what, ",".join(bad) or value,
                                           ", ".join(known)))
    return items


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--store", type=Path, default=None,
                    help="postings store to read (default: boost's own, read-only)")
    ap.add_argument("--index", type=Path, default=None,
                    help="rag_index.json to size alongside (default: boost's own)")
    ap.add_argument("--queries", type=Path, action="append", default=None,
                    help="golden .jsonl file(s) whose queries time the reads")
    ap.add_argument("--layouts", default=",".join(LAYOUTS),
                    type=lambda v: _csv(v, LAYOUTS, "layout"))
    ap.add_argument("--codecs", default=",".join(CODECS),
                    type=lambda v: _csv(v, CODECS, "codec"))
    ap.add_argument("--workdir", type=Path, default=None,
                    help="where the rebuilt layouts go (default: a temp dir)")
    ap.add_argument("--json", action="store_true", help="emit JSON, not Markdown")
    args = ap.parse_args(argv)

    store = args.store or rag.postings_path()
    if not store.exists():
        print("no postings store at %s -- run `boost reindex` or pass --store"
              % store, file=sys.stderr)
        return 2
    index = args.index or (paths.cache_dir() / "rag_index.json")
    files = args.queries or [p for p in DEFAULT_QUERIES if p.exists()]
    queries = query_terms(files)
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="kwindex-"))
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        report = measure(store, workdir, args.layouts, args.codecs, queries,
                         index=index)
    except (RuntimeError, ValueError, sqlite3.Error) as e:
        print("measure_keyword_index: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2) if args.json else render_markdown(report),
          end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
