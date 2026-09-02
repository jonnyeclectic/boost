# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Full-content retrieval over tapped skills/rules/workflows (RAG — Phase 1).

Pure stdlib. Where `catalog.search` scores only an item's name + one-line
description + frontmatter, this indexes the *whole* body of every item and
ranks it with BM25, then optionally reranks the shortlist through the
`core.ai` bridge. See docs/rag-architecture.md.

The index is persisted at ``~/.boost/cache/rag_index.json`` and refreshed
per-tap, keyed on the git commit each tap cache was built from, so the
expensive step — reading and chunking thousands of files — happens once and
again only when a tap actually changes.

Everything degrades: no index -> callers fall back to ``catalog.search``;
no AI -> the BM25 order is returned as-is.
"""
from __future__ import annotations

import array
import contextlib
import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import cast

try:  # TypedDict lives in typing on 3.9+, kept optional for safety
    from typing import TypedDict
except ImportError:  # pragma: no cover - 3.9+ always has it
    TypedDict = None  # type: ignore

from . import ai, catalog, config, frontmatter, gitutil, paths, registry, util

# v2: `snip` stores a larger head of the matched chunk (not just SNIP_WIDTH
# chars) so `retrieve` can window it onto the query terms; bump forces a
# one-time reindex.
# v7: postings interns term text into its own `terms` table instead of
# repeating it on every posting row — see `_write_postings`; bump forces a
# one-time reindex so every store gets the smaller layout.
INDEX_VERSION = 7
ENGINE = "bm25"

# Chunking defaults (documented in docs/rag-architecture.md §4).
CHUNK_CHARS = 1000
OVERLAP = 150
MAX_CHUNKS = 40

# Width of the passage surfaced for display + rerank context, and how much of
# the matched chunk is stored to center that window on. SNIP_STORE bounds index
# growth: a match in the chunk's first half still lands in the window; storing
# the whole chunk instead bloated the index ~70%.
SNIP_WIDTH = 200
SNIP_STORE = 500

# BM25 parameters (§6a). Exposed in the persisted `params` so they are
# tunable without a format change.
K1 = 1.2
B = 0.75

# A deliberately tiny stopword list — full-content indexing already dilutes
# common words, so we only drop the most frequent glue.
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
    "is", "are", "be", "this", "that", "it", "as", "at", "by", "from",
    "your", "you", "can", "will", "if", "when", "how",
})


class Hit(TypedDict, total=False):  # type: ignore[misc]
    entry: dict     # the live catalog entry (name, tap, kind, skill_md, ...)
    score: float    # BM25 relevance (higher = better)
    snippet: str    # best-matching passage, for display + rerank context
    content: str    # digest of the body, for collapsing byte-identical copies.
                    # Optional: dense hits arrive without one and have it
                    # attached from the BM25 index (see `_with_content`).


# --------------------------------------------------------------- tokenizing

def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and 1-char noise."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower())
            if len(t) >= 2 and t not in _STOPWORDS]


def chunk(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP,
          cap: int = MAX_CHUNKS) -> list[str]:
    """Split a body into passage-sized chunks on paragraph boundaries.

    Paragraphs are packed up to ``size`` chars; an oversized paragraph is
    hard-split with ``overlap`` carried across the cut so a match spanning a
    boundary is not lost. At most ``cap`` chunks are returned.
    """
    text = text.strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        while len(p) > size:
            chunks.append(p[:size])
            if len(chunks) >= cap:
                return chunks
            p = p[size - overlap:]
        if not cur:
            cur = p
        elif len(cur) + 1 + len(p) <= size:
            cur += "\n" + p
        else:
            chunks.append(cur)
            if len(chunks) >= cap:
                return chunks
            tail = cur[-overlap:] if overlap else ""
            cur = (tail + "\n" + p) if tail else p
    if cur and len(chunks) < cap:
        chunks.append(cur)
    return chunks


# ------------------------------------------------------------ body reading

def _tap_paths() -> dict[str, Path]:
    return {t.name: t.path for t in registry.list_taps()}


def _tap_commits() -> dict[str, str]:
    """Map safe tap name -> the commit its cache was built from."""
    commits: dict[str, str] = {}
    for t in registry.list_taps():
        commit = ""
        try:
            data = json.loads(t.cache_file.read_text(encoding="utf-8"))
            commit = str(data.get("commit") or "")
        except (OSError, json.JSONDecodeError):
            pass
        if not commit and t.is_cloned:
            commit = gitutil.head_commit(t.path)
        commits[t.safe_name] = commit
    return commits


def entry_path(entry: dict, tap_paths: dict[str, Path] | None = None
               ) -> Path | None:
    """Where a catalog entry's defining file actually lives on this machine.

    ``skill_md`` is stored relative to the tap's repo root (see ``catalog``), so
    it is not openable on its own; joining it to that tap's clone directory is
    the only thing that makes it one. That join used to live inside
    ``read_body``, which kept the answer private — a caller that wanted the
    *location* rather than the *bytes* had nothing to call, and passed the
    relative path off as a real one instead. ``boost_langchain`` shipped exactly
    that bug in its Document metadata.

    Returns ``None`` when the entry names no defining file. A bare tap root is
    not where the item is, so returning one would hand the caller a path that
    opens the wrong thing rather than an absence it has to handle.
    """
    rel = entry.get("skill_md")
    if not rel:
        return None
    paths_map = _tap_paths() if tap_paths is None else tap_paths
    base = paths_map.get(entry.get("tap", ""))
    if base is None:
        base = paths.repos_dir() / str(entry.get("tap", "")).replace("/", "__")
    return Path(base) / rel


def read_body(entry: dict, tap_paths: dict[str, Path] | None = None) -> str:
    """Return an item's searchable text: name + description + prose body.

    The frontmatter is stripped (reusing ``frontmatter.parse``); the name and
    description are prepended so short items keep keyword parity with the old
    search. Missing files degrade to just the catalog metadata.
    """
    header = "%s\n%s" % (entry.get("name", ""), entry.get("description", ""))
    src = entry_path(entry, tap_paths)
    if src is None:
        return header.strip()
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return header.strip()
    _meta, body = frontmatter.parse(text)
    return ("%s\n%s" % (header, body)).strip()


# ----------------------------------------------------------------- build

def index_path() -> Path:
    return paths.cache_dir() / "rag_index.json"


def surface(entry: dict) -> str:
    """The item's own identifying text, indexed alongside its body.

    A chunked index got name matching for free: the name sat in whichever chunk
    happened to contain it. One document per entry has to state it, and the
    de-hyphenated form matters because `tokenize` does not split on hyphens —
    without it the query "code reviewer" cannot match the item `code-reviewer`.
    """
    name = entry.get("name", "")
    return " ".join([name, name.replace("-", " ").replace("_", " "),
                     entry.get("description") or ""])


def _make_docs(entries: list[dict], tap_paths: dict[str, Path]) -> list[dict]:
    """Tokenize every entry into ONE scored document.

    Chunking cost far more than it bought. Each 1000-char window carried its own
    copy of the shared per-doc fields and its own `snip`, which is how a 743-entry
    corpus became 3,740 documents and how the roadmap item measured a real
    83-tap install at 132 MB and 8-13 s of `json.loads` on *every cold search* —
    against 31-70 ms of actual BM25 scoring.

    The one thing chunking genuinely provided was locality: a term only had to
    beat the length normalisation of its own window, not of an entire long
    document. BM25's `b` parameter already handles that, and `retrieve` was
    collapsing chunks back to one hit per entry anyway (max score across
    chunks), so the extra documents were discarded at query time.
    """
    docs: list[dict] = []
    for e in entries:
        body = read_body(e, tap_paths)
        # The scanner already hashed this exact text (`catalog._content_digest`
        # assembles name + description + body, the same string `read_body`
        # returns), so an entry from a current cache hands the value over. The
        # fallback is not dead code: a cache written before CACHE_FORMAT, or an
        # entry synthesised by a caller rather than scanned, still has to index.
        digest = e.get("content") or hashlib.sha256(
            body.strip().encode("utf-8", "replace")).hexdigest()[:16]
        tf: dict[str, int] = defaultdict(int)
        for tok in tokenize(surface(e) + "\n" + body):
            tf[tok] += 1
        if not tf:
            continue
        docs.append({
            "n": e["name"], "t": e["tap"], "f": e["skill_md"], "h": digest,
            "k": e.get("kind", "skill"),
            "c": 0, "l": sum(tf.values()),
            "snip": body[:SNIP_STORE].strip(),  # windowed at retrieve time
            "tf": dict(tf),  # noqa: FURB123  tf is a defaultdict; .copy() would keep the factory
        })
    return docs


def _postings_to_doc_tf(raw: dict) -> dict[int, dict[str, int]]:
    """Invert persisted postings back to per-doc term frequencies.

    Pure: it inverts whatever ``raw`` carries and reads nothing. An earlier
    version fell back to the SQLite store with ``or``, which made a caller
    passing ``{}`` silently receive tens of thousands of postings from the live
    index — invisible in CI, where no store exists, and wrong everywhere else.
    Callers that need the store now say so; see :func:`_kept_docs`.
    """
    doc_tf: dict[int, dict[str, int]] = defaultdict(dict)
    for term, plist in (raw.get("postings") or {}).items():
        for doc_id, tf in plist:
            doc_tf[doc_id][term] = tf
    return doc_tf


def _kept_docs(raw: dict, keep_safe: set) -> list[dict]:
    """Recover cached docs (with term freqs) for taps that did not change.

    Term frequencies live in the SQLite postings store since they left the JSON
    index, so an index without an inline ``postings`` key is normal rather than
    empty — this is the caller that reaches for the store, explicitly.
    """
    # Key ABSENCE, not falsiness: an index carrying an explicit empty
    # `postings` is stating it has none, and must not be answered from the
    # store. Only an index with no such key predates the SQLite move.
    doc_tf = _postings_to_doc_tf(
        raw if "postings" in raw else {"postings": _all_postings()})
    return [{**meta, "tf": doc_tf.get(doc_id, {})}
            for doc_id, meta in enumerate(raw.get("docs", []))
            if meta["t"].replace("/", "__") in keep_safe]


def build(entries: list[dict] | None = None, force: bool = False) -> dict:
    """(Re)build the full-content index, reusing unchanged taps.

    Returns stats: ``{"entries", "docs", "taps", "reindexed", "reused"}``.
    """
    entries = catalog.all_entries() if entries is None else entries
    tap_paths = _tap_paths()
    commits = _tap_commits()

    old = _load_raw()
    reused_safe: set = set()
    if old is not None and not force:
        old_commits = old.get("commits", {})
        for safe, commit in commits.items():
            if commit and old_commits.get(safe) == commit:
                reused_safe.add(safe)

    fresh = [e for e in entries
             if e["tap"].replace("/", "__") not in reused_safe]
    docs = _make_docs(fresh, tap_paths)
    if old is not None and reused_safe:
        docs = _kept_docs(old, reused_safe) + docs

    _save(docs, commits)
    reindexed = sorted({e["tap"] for e in fresh})
    return {
        "entries": len({entry_key(e) for e in entries}),
        "docs": len(docs),
        "taps": len(commits),
        "reindexed": reindexed,
        "reused": sorted(reused_safe),
    }


def postings_path() -> Path:
    return paths.cache_dir() / "rag_postings.sqlite"


def _write_postings(postings: dict[str, list[list[int]]]) -> None:
    """Persist the term -> [(doc, tf)] map to SQLite, replacing any existing one.

    Postings were the largest part of the JSON index — measured 64% of it after
    unchunking — and `json.loads` had to materialise every one of them to answer
    a query that touches a handful of terms. On a real 83-tap install that was
    8-13 s and multiple GB resident per cold `boost search`, against 31-70 ms of
    actual scoring.

    SQLite is used purely as an indexed key-value store here, not as a search
    engine: BM25 scoring stays in `_bm25` byte for byte, so this changes cold
    start cost and nothing about which results come back.

    Terms are interned into their own table rather than repeated on every
    posting row. Measured on a real 458-tap store: 18,619,658 posting rows over
    210,422 distinct terms averaging 6.6 characters — the term string alone was
    ~123 MB of the 653 MB file, stored on average 88 times over. `postings` now
    carries an integer `term_id`, and `terms` also carries each term's document
    frequency (`df`, the length of its posting list) so `stem_expansions` can
    read it directly instead of re-deriving it with `GROUP BY` on every lookup.
    """
    paths.ensure_dirs()
    final = postings_path()
    # A UNIQUE temp per build, not a fixed `.sqlite.tmp`, and this is a
    # concurrency fix rather than tidiness. Every build used to write the same
    # name and unlink it on entry, so a second build starting mid-flight
    # deleted the first's *finished* file and the first died on the swap:
    #
    #   FileNotFoundError: rag_postings.sqlite.tmp -> rag_postings.sqlite
    #
    # observed on a real 464-tap install. The loser threw away several minutes
    # of work and returned a crash report instead of an index. Nothing here is
    # exotic — `boost search` builds on a cold index, so two terminals is
    # enough to hit it. Same mkstemp-then-replace shape as
    # `util.atomic_write_text`, which every other file boost must not lose
    # already goes through.
    fd, tmp_name = tempfile.mkstemp(dir=str(final.parent),
                                    prefix="." + final.name + ".",
                                    suffix=".tmp")
    os.close(fd)                # SQLite opens the path itself
    tmp = Path(tmp_name)
    con = sqlite3.connect(str(tmp))
    try:
        # No durability needed: this file is a derived cache, and a crash
        # mid-build leaves the .tmp behind rather than a torn index.
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        con.execute("CREATE TABLE terms (id INTEGER PRIMARY KEY, "
                    "term TEXT NOT NULL, df INTEGER NOT NULL)")
        con.execute("CREATE TABLE postings (term_id INTEGER, doc INTEGER, "
                    "tf INTEGER)")
        items = list(postings.items())
        con.executemany(
            "INSERT INTO terms (id, term, df) VALUES (?, ?, ?)",
            ((term_id, term, len(plist))
             for term_id, (term, plist) in enumerate(items)))
        con.executemany(
            "INSERT INTO postings (term_id, doc, tf) VALUES (?, ?, ?)",
            ((term_id, doc, tf) for term_id, (_term, plist) in enumerate(items)
             for doc, tf in plist))
        # Built after the insert: maintaining it per-row is far slower.
        con.execute("CREATE UNIQUE INDEX terms_term ON terms(term)")
        con.execute("CREATE INDEX postings_term_id ON postings(term_id)")
        con.commit()
    except BaseException:
        # Never leave a temp behind, and never mask the original error —
        # `util.atomic_write_text`'s rule, for the same reason.
        con.close()
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    else:
        con.close()
    tmp.replace(final)          # atomic swap, same as the JSON half


def read_postings(terms: Sequence[str]) -> dict[str, list[list[int]]]:
    """Postings for just these terms — the whole point of the SQLite store.

    A query touches a handful of terms out of tens of thousands, so this reads
    kilobytes where the JSON index read the entire file.
    """
    uniq = sorted(set(terms))
    if not uniq:
        return {}
    try:
        con = sqlite3.connect("file:%s?mode=ro" % postings_path(), uri=True)
    except sqlite3.Error:
        return {}
    out: dict[str, list[list[int]]] = defaultdict(list)
    try:
        # Chunked: SQLite caps host parameters (999 on older builds), and a
        # long query can exceed it.
        for i in range(0, len(uniq), 500):
            batch = uniq[i:i + 500]
            q = ("SELECT t.term, p.doc, p.tf FROM postings p "  # noqa: S608  interpolates only `?` placeholders; terms are bound params
                 "JOIN terms t ON p.term_id = t.id "
                 "WHERE t.term IN (%s)" % ",".join("?" * len(batch)))
            for term, doc, tf in con.execute(q, batch):
                out[term].append([doc, tf])
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return dict(out)  # noqa: FURB123  out is a defaultdict; .copy() would keep the factory


# A query term shorter than this expands to noise: `cal` prefixes `calendar`,
# `calculate` and `callbacks` alike, and picking one of them for the user is a
# guess rather than a correction.
STEM_MIN_LEN = 4


def stem_expansions(terms: Sequence[str]) -> dict[str, str]:
    """Map each term that indexes *nothing* to the commonest term it prefixes.

    `tokenize` is exact-match, so a query term and its own inflection are
    unrelated strings: `boost search brainstorm` returned zero matches while
    `brainstorming` returned the skill, and `boost chat` had the same hole.
    Measured over the 461 tap caches on one real machine, 4,663 of 29,607 item
    names (15.7%) were unreachable by an attested stem — `pattern` missed 474
    names ending `-patterns`, `skill` missed 252 ending `-skills`.

    **A term that has postings is never expanded.** That is the whole safety
    argument: this can only ever add signal where `_bm25` scored exactly none
    (it skips a term with no posting list), so a query whose terms all exist
    ranks byte-identically and the retrieval floors cannot move. It is also why
    this is a fallback rather than a stemmer — a real stemmer conflates terms
    that both exist, which changes established rankings and needs an index
    format bump and a regenerated baseline.

    Returns ``{}`` — never raises — when the store is missing or unreadable,
    matching :func:`read_postings`.
    """
    uniq = [t for t in dict.fromkeys(terms) if len(t) >= STEM_MIN_LEN]
    if not uniq:
        return {}
    indexed = read_postings(uniq)
    missing = [t for t in uniq if not indexed.get(t)]
    if not missing:
        return {}
    try:
        con = sqlite3.connect("file:%s?mode=ro" % postings_path(), uri=True)
    except sqlite3.Error:
        return {}
    out: dict[str, str] = {}
    try:
        for term in missing:
            # `tokenize` emits only [a-z0-9]+, and "~" sorts above every
            # character it can produce — so this half-open range is exactly the
            # terms beginning with `term`, and it rides the terms_term index
            # instead of scanning. `df` (document frequency) is stored per term
            # at build time, so this needs no join and no GROUP BY. Ties break
            # on the term itself so the choice is deterministic across
            # machines.
            row = con.execute(
                "SELECT term FROM terms WHERE term > ? AND term < ? "
                "ORDER BY df DESC, term LIMIT 1",
                (term, term + "~")).fetchone()
            if row:
                out[term] = row[0]
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return out


def _all_postings() -> dict[str, list[list[int]]]:
    """Every posting — only the incremental rebuild path needs this."""
    try:
        con = sqlite3.connect("file:%s?mode=ro" % postings_path(), uri=True)
    except sqlite3.Error:
        return {}
    out: dict[str, list[list[int]]] = defaultdict(list)
    try:
        for term, doc, tf in con.execute(
                "SELECT t.term, p.doc, p.tf FROM postings p "
                "JOIN terms t ON p.term_id = t.id"):
            out[term].append([doc, tf])
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return dict(out)  # noqa: FURB123  out is a defaultdict; .copy() would keep the factory


def _save(docs: list[dict], commits: dict[str, str]) -> None:
    postings: dict[str, list[list[int]]] = defaultdict(list)
    meta_docs: list[dict] = []
    total_len = 0
    for doc_id, d in enumerate(docs):
        for term, tf in d["tf"].items():
            postings[term].append([doc_id, tf])
        total_len += d["l"]
        meta_docs.append({"n": d["n"], "t": d["t"], "f": d["f"], "k": d["k"],
                          "h": d.get("h", ""),
                          "c": d["c"], "l": d["l"], "snip": d["snip"]})
    payload = {
        "version": INDEX_VERSION,
        "engine": ENGINE,
        "generated": _now(),
        "commits": commits,
        "params": {"chunk_chars": CHUNK_CHARS, "overlap": OVERLAP,
                   "k1": K1, "b": B},
        "stats": {"docs": len(docs),
                  "avg_len": (total_len / len(docs)) if docs else 0.0},
        "docs": meta_docs,
    }
    paths.ensure_dirs()
    p = index_path()
    # Atomic swap: a bare write_text here can leave a truncated/corrupt index
    # on disk if the process dies mid-write or a query reads concurrently.
    _write_postings(postings)
    util.atomic_write_text(p, json.dumps(payload))
    # Drop the mtime-keyed cache so a reindex is visible to an immediately
    # following query even when the filesystem mtime granularity is coarse.
    _CACHE.pop(str(p), None)


def _now() -> str:
    return util.now_iso()


# ----------------------------------------------------------------- query

_CACHE: dict[str, object] = {}


def _load_raw() -> dict | None:
    p = index_path()
    key = str(p)
    try:
        st = p.stat()
    except OSError:
        _CACHE.pop(key, None)
        return None
    # (mtime_ns, size), not bare mtime: a rewrite landing inside one mtime
    # tick would otherwise serve the previous index from this cache forever —
    # the same stamp `catalog._cached_tap` already uses, for the same reason.
    stamp = (st.st_mtime_ns, st.st_size)
    cached = _CACHE.get(key)
    if isinstance(cached, tuple) and cached[0] == stamp:
        return cached[1]  # type: ignore[return-value]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("version") != INDEX_VERSION:
        return None
    _CACHE[key] = (stamp, data)
    return data


def ready() -> bool:
    """True when a usable index exists on disk.

    Both halves are required: the JSON carries the documents, the SQLite file
    carries the postings, and scoring needs both. A docs-only index reports not
    ready rather than silently returning zero hits for every query.
    """
    raw = _load_raw()
    return bool(raw and raw.get("docs") and postings_path().exists())


def stale() -> bool:
    """True when the index no longer reflects the taps on disk.

    ``ready()`` only asks whether an index *exists*, which is why ``ensure()``
    would serve a first build forever: ``boost tap X`` rebuilds X's catalog
    cache but nothing rebuilt the BM25 index, so ``boost search`` answered "no
    matches" — and suggested searching GitHub — for a skill ``boost info`` could
    already describe from the same machine.

    Deliberately **stat-only**. The obvious test, comparing ``_tap_commits()``
    against the stored commits, means parsing every tap's catalog JSON on every
    search — reintroducing exactly the cold-start cost that moving postings into
    SQLite existed to remove. Two cheap signals cover it instead:

    * the tap set must still match the set the index recorded (catches a tap
      added or removed, neither of which need touch an existing cache file);
    * no tap's catalog cache may be newer than the index (catches a tap whose
      contents moved, since ``build()`` writes the index only after every
      catalog cache it consumed).

    The residual gap is a cache rewritten inside the same filesystem mtime tick
    as the index; the next tap operation catches it, and paying a full parse on
    every search to close it is the worse trade.
    """
    raw = _load_raw()
    if raw is None:
        return True
    taps = registry.list_taps()
    if {t.safe_name for t in taps} != set(raw.get("commits") or {}):
        return True
    try:
        built_at = index_path().stat().st_mtime
    except OSError:
        return True
    for t in taps:
        try:
            if t.cache_file.stat().st_mtime > built_at:
                return True
        except OSError:
            continue        # no cache yet — build() will pick it up regardless
    return False


def ensure() -> bool:
    """Ensure a *current* full-content index exists, building it on first use.

    This makes BM25 search the default for every surface (CLI + MCP) without the
    user having to run ``boost reindex`` first. Returns True when RAG is usable.
    Never raises: with no taps, or if the build fails, it returns False so the
    caller degrades to frontmatter search instead of erroring.

    A stale index rebuilds rather than being served: ``build()`` reuses every
    tap whose commit is unchanged, so noticing one new tap costs one tap's
    indexing, not the whole corpus.
    """
    if ready() and not stale():
        return True
    if not registry.list_taps():
        return False
    try:
        build()
    except Exception:
        return False
    return ready()


def _bm25(query_terms: list[str], raw: dict,
          postings: dict[str, list[list[int]]]) -> dict[int, float]:
    """Score documents for ``query_terms``. Pure: postings are passed in.

    Reading them inside would hide I/O in the one function whose arithmetic is
    pinned exactly (`TestBm25Math`), and would tie the scorer to where postings
    happen to live — which is the thing this change moved.
    """
    docs = raw["docs"]
    n = len(docs)
    avg = raw.get("stats", {}).get("avg_len") or 1.0
    scores: dict[int, float] = defaultdict(float)
    for term in set(query_terms):
        plist = postings.get(term)
        if not plist:
            continue
        df = len(plist)
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for doc_id, tf in plist:
            dl = docs[doc_id]["l"] or 1
            denom = tf + K1 * (1 - B + B * dl / avg)
            scores[doc_id] += idf * (tf * (K1 + 1)) / denom
    return scores


def _passage(text: str, terms: Sequence[str], width: int = SNIP_WIDTH) -> str:
    """A ``width``-char window of ``text`` centered on the first query term.

    The stored ``snip`` is a large head of the matched chunk (``SNIP_STORE``);
    this surfaces the passage that earned the match rather than the chunk's
    first ``SNIP_WIDTH`` chars, improving both
    display and the rerank context sent to the LLM. Falls back to the head (the
    old ``piece[:width]`` behavior) when no term is present. Trimmed edges are
    marked with a single-character ellipsis.
    """
    text = text.strip()
    if len(text) <= width:
        return text
    low = text.lower()
    positions = [p for p in (low.find(t) for t in terms) if p >= 0]
    if not positions:
        return text[:width].rstrip() + "…"
    start = max(0, min(min(positions) - width // 4, len(text) - width))
    end = start + width
    snip = text[start:end].strip()
    lead = "…" if start > 0 else ""
    tail = "…" if end < len(text) else ""
    return lead + snip + tail


def entry_key(entry: dict) -> tuple[str, str]:
    """Identity of a catalog entry: the tap it came from and its file.

    NOT ``(name, tap)``, which both engines used and which is not unique. On the
    pinned 6-tap eval corpus 743 entries collapse to 694 such pairs; on a real
    83-tap install the roadmap item measures 1,557 of 11,147 (14.0%) colliding,
    worst case ``('survivorforge/cursor-rules', 'rule')`` x47. One tap can
    legitimately ship two different files under one name —

        docs/rules/backend/nodejs/express-mongodb/admin-interface-rule.mdc
        docs/rules/backend/nodejs/fullstack-mern-guide/admin-interface-rule.mdc

    — and keying on the name made the second shadow the first in a dict
    comprehension, so a query matching the first's body was reported under the
    second's name and description. ``skill_md`` is the tap-relative path, so
    ``(tap, skill_md)`` is 743/743 and 11,147/11,147 distinct respectively.

    Deliberately strict. An earlier draft fell back to the name when
    ``skill_md`` was missing, on the theory that a malformed row should not
    crash a search. It is the worse failure: the index side and the entry side
    then degrade differently, the keys stop matching, and retrieval silently
    returns *nothing* — which takes far longer to diagnose than a KeyError
    naming the field. Every catalog entry has ``skill_md`` (743/743 on the eval
    corpus), and INDEX_VERSION rejects any index built without it.
    """
    return (entry["tap"], entry["skill_md"])


@lru_cache(maxsize=1)
def _confidence_map() -> dict[str, str]:
    """``tap name -> confidence`` from the shipped registry catalog.

    Cached because dedup asks per hit and the catalog is 466 rows; parsing it
    inside a search loop would be a real cost for a value that cannot change
    while the process runs.
    """
    out: dict[str, str] = {}
    for row in config.load_registry_catalog():
        name = row.get("name")
        conf = row.get("confidence")
        if name and conf:
            out[str(name)] = str(conf)
    return out


def registry_confidence(tap: str) -> str | None:
    """The shipped confidence for a tap, or None if it is not catalogued."""
    return _confidence_map().get(tap)


# Lower sorts better. Unknown registries rank below every known one rather than
# above, so an uncatalogued tap never outranks a vetted one by default.
_CONFIDENCE_ORDER = {"high": 0, "med": 1, "low": 2}


def source_rank(entry: dict) -> tuple[int, int]:
    """How much this copy's *source* is worth, for choosing between identical bodies.

    Only ever used inside a content cluster, where every candidate has the same
    body — so this decides where the user installs from, not what they find.

    The user's own ``curated`` flag comes first and the shipped ``confidence``
    second, deliberately: a maintainer opinion baked into the package should
    never override a decision the machine's owner made with `boost tap
    --curated`.
    """
    curated = 0 if entry.get("curated") else 1
    conf = _CONFIDENCE_ORDER.get(registry_confidence(entry.get("tap", "")) or "",
                                 len(_CONFIDENCE_ORDER))
    return (curated, conf)


def dedupe_by_content(hits: list[Hit], limit: int) -> list[Hit]:
    """Collapse byte-identical copies, then take ``limit``.

    Measured over 77 tapped registries: 78.3% of 29,938 entries are
    byte-identical duplicates (largest cluster 40 copies), and the
    natural-language query set averaged 4.94 of 10 result slots consumed by a
    repeat — worst case 9 of 10. Registries mirror each other, so N copies of one
    rule across N taps ate N of the ten slots a user sees.

    Clustering is on the **body**, never the name. 82.7% of entries share a name
    but only 78.3% share a body, and that ~4.4% gap is real distinct content —
    the ``admin-interface-rule`` pair fixed in #366 is two different rules under
    one name. Clustering on content cannot make that mistake: of 14,153 distinct
    bodies, the number of clusters spanning more than one name is zero.

    Within a cluster every copy is byte-identical, so *which* one survives is
    purely about where the user would rather install from: a ``curated`` tap wins
    over a better-ranked uncurated one. The cluster keeps its best score either
    way, so promoting the trusted copy never demotes the result.

    A hit with no recorded content hash is always kept — two unknowns must not
    collapse into each other, which would hide real results.
    """
    best: dict[str, int] = {}          # content hash -> index into `out`
    out: list[Hit] = []
    for hit in hits:
        digest = hit.get("content")
        if not digest:
            out.append(hit)            # unknown content is never a match
            continue
        seen = best.get(digest)
        if seen is None:
            best[digest] = len(out)
            out.append(hit)
            continue
        # Same body already shown. Keep its rank, but prefer a better source.
        kept = out[seen]
        if source_rank(hit["entry"]) < source_rank(kept["entry"]):
            # Copy the kept hit wholesale and swap only the entry: a literal
            # rebuild here would silently drop anything else the caller
            # carried on the hit (retrieve defers snippet windowing through
            # this function, so the carry is load-bearing, not hygiene).
            out[seen] = cast(Hit, {**kept, "entry": hit["entry"]})
    return out[:limit]


#: Cosine-similarity floor for two entries to collapse as near-duplicates.
#:
#: Deliberately conservative and deliberately unproven. `dedupe_by_content`
#: above shipped only after one count settled its safety: of 14,153 distinct
#: bodies, the clusters spanning more than one *name* numbered zero, so
#: collapsing on content hash could not merge two different skills. No
#: equivalent count exists yet for near-identical clustering — the measurement
#: the roadmap card asks for is "over a real corpus, at the chosen threshold,
#: count clusters spanning more than one meaning" and nobody has run it. Until
#: someone does, `collapse_near_duplicate_hits` stays reachable only opt-in
#: (see `retrieve_any`'s `collapse_near_duplicates` parameter), so the default
#: search path is unaffected by a threshold nobody has validated.
NEAR_DUPLICATE_THRESHOLD = 0.97


def _decode_vector(blob: bytes) -> array.array:
    """A stored float32 embedding blob as a sequence of floats."""
    vec = array.array("f")
    vec.frombytes(blob)
    return vec


def _cosine(a: array.array, b: array.array) -> float:
    """Cosine similarity of two float32 vectors, 0.0 for any comparison that
    cannot be trusted: a dimension mismatch (different embedding models) or
    either side being the zero vector. An ambiguous comparison must never read
    as a match, the same rule a missing content hash follows above.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if 0.0 in (norm_a, norm_b):
        return 0.0
    return dot / (norm_a * norm_b)


def collapse_near_duplicate_hits(hits: list[Hit],
                                  vectors: dict[tuple[str, str], bytes],
                                  limit: int,
                                  threshold: float = NEAR_DUPLICATE_THRESHOLD,
                                  ) -> list[Hit]:
    """Collapse entries whose embeddings are near-identical, then take ``limit``.

    Runs on the output of :func:`dedupe_by_content`, on the same contract —
    keep the earliest rank slot, promote a better source into it — for the
    residual that survives byte-identical dedup: the same skill translated or
    paraphrased across mirrors. Observed on a real 466-tap install: the query
    ``exa search`` returned ten rows that were all one skill in Japanese,
    Chinese, and five English variants, none sharing a body digest, so
    ``dedupe_by_content`` correctly kept every one of them apart.

    ``vectors`` maps ``entry_key(hit["entry"])`` to a raw float32 embedding
    blob, looked up by the caller (:func:`boost_cli.core.dense.entry_vectors`)
    rather than fetched here — this stays pure so it is cheap to test with
    synthetic vectors, and clustering ``hits`` is O(n * clusters), never
    O(n^2) against the whole store.

    A hit with no vector — no dense store built, or the entry never got one —
    is never merged into anything: two unknowns must not collapse into each
    other, the same rule :func:`dedupe_by_content` follows for a missing
    content hash.
    """
    out: list[Hit] = []
    reps: list[array.array | None] = []   # parallel to `out`
    for hit in hits:
        blob = vectors.get(entry_key(hit["entry"]))
        vec = _decode_vector(blob) if blob else None
        merge_at = None
        if vec is not None:
            for i, rep in enumerate(reps):
                if rep is not None and _cosine(vec, rep) >= threshold:
                    merge_at = i
                    break
        if merge_at is None:
            out.append(hit)
            reps.append(vec)
            continue
        kept = out[merge_at]
        if source_rank(hit["entry"]) < source_rank(kept["entry"]):
            out[merge_at] = cast(Hit, {**kept, "entry": hit["entry"]})
    return out[:limit]


def _windowed(hits: list[Hit], terms: Sequence[str]) -> list[Hit]:
    """Window each hit's raw stored snip onto the query terms.

    Deferred to the hits actually returned: ranking carries the raw ``snip``
    through dedupe, and only the survivors pay ``_passage`` — the eager
    version computed 39,726 windows on a real machine to display 60.
    """
    return [cast(Hit, {**h, "snippet": _passage(h["snippet"], terms)})
            for h in hits]


def _retrieve_from_index(docs: list[dict], scores: dict[int, float],
                         terms: list[str], k: int, kind: str | None,
                         ) -> list[Hit] | None:
    """Rank from the index's own doc metadata — no full-catalogue parse.

    The slow path builds a ``live`` map by parsing every tap cache on the
    machine (458 files, ~100 MB, 0.32 s measured) to serve two needs: filter
    docs whose entry is gone, and hand back real entry dicts. On a fresh index
    both are answerable cheaper: every doc of a still-configured tap is live
    by construction (``ensure()`` rebuilds on staleness), and only the final
    ``k`` survivors need materialising — so only *their* taps' caches load.

    Ranking, dedupe and tie-breaks use index-side values (``n``/``h``/``k``)
    that ``build()`` copied from the same cache entries the slow path reads,
    plus a shadow entry carrying the two fields ``source_rank`` consults
    (``tap``, ``curated``) from one ``registry.list_taps()`` snapshot — never
    a second config read, and never :func:`registry.get`, which raises for a
    concurrently-untapped name.

    Returns ``None`` when any survivor's entry cannot be materialised (a tap
    cache vanished or moved under a stat-fresh index): the caller reruns the
    query through the explicit-entries path, whose output is the contract.
    Byte-identical-or-fall-back, never approximate.
    """
    taps = {t.name: t for t in registry.list_taps()}
    best: dict[tuple[str, str], tuple[float, str, str, str]] = {}
    for doc_id, score in scores.items():
        d = docs[doc_id]
        if kind is not None and d["k"] != kind:
            continue
        if d["t"] not in taps:      # untapped repos stop ranking, stale or not
            continue
        key = (d["t"], d["f"])
        prev = best.get(key)
        if prev is None or score > prev[0]:
            best[key] = (score, d["snip"], d.get("h", ""), d["n"])
    ranked = sorted(best.items(),
                    key=lambda kv: (-kv[1][0], kv[1][3], kv[0]))
    # The shadow entry carries exactly what downstream code reads before
    # materialisation: `source_rank` consults tap + curated, and the loop
    # below reads tap + skill_md. Nothing else — an extra field here would
    # be dead weight pretending to be contract.
    hits: list[Hit] = [
        {"entry": {"tap": key[0], "skill_md": key[1],
                   "curated": taps[key[0]].curated},
         "score": score, "content": digest,
         "snippet": snip}  # type: ignore[typeddict-item]
        for key, (score, snip, digest, _name) in ranked]
    # The FULL ranked list flows through dedupe, exactly as the slow path's
    # does: a curated duplicate at rank 3,000 legally replaces the displayed
    # source of survivor #1, so the promotion scan cannot be truncated.
    survivors = dedupe_by_content(hits, len(hits))
    loaded: dict[str, dict[tuple[str, str], dict]] = {}
    out: list[Hit] = []
    for hit in survivors:
        if len(out) == k:
            break
        tap_name = hit["entry"]["tap"]
        tap = taps.get(tap_name)
        if tap is None:             # promoted source raced an untap
            return None
        if tap_name not in loaded:
            loaded[tap_name] = {entry_key(e): e
                                for e in catalog.load_tap(tap)}
        entry = loaded[tap_name].get((tap_name, hit["entry"]["skill_md"]))
        if entry is None:
            return None
        out.append(cast(Hit, {**hit, "entry": entry,
                              "snippet": _passage(hit["snippet"], terms)}))
    return out


def retrieve(query: str, k: int = 60, kind: str | None = None,
             entries: list[dict] | None = None) -> list[Hit]:
    """Top-k full-content hits for ``query``. ``[]`` if the index is empty."""
    raw = _load_raw()
    if not raw or not raw.get("docs"):
        return []
    terms = tokenize(query)
    if not terms:
        return []
    # Substitute before scoring, not after: the expanded term has to reach the
    # snippet windowing too, or the hit is highlighted on a word it does not
    # contain.
    substitutions = stem_expansions(terms)
    if substitutions:
        terms = [substitutions.get(t, t) for t in terms]
    docs = raw["docs"]
    scores = _bm25(terms, raw, read_postings(terms))
    if entries is None:
        fast = _retrieve_from_index(docs, scores, terms, k, kind)
        if fast is not None:
            return fast
        # An entry vanished between index and cache: answer from the full
        # catalogue exactly as before the fast path existed. One side effect
        # rides along only here now — load_tap's rescan of old-CACHE_FORMAT
        # caches, which otherwise happens on tap operations and build().
        entries = catalog.all_entries()
    live = {entry_key(e): e for e in entries}
    best: dict[tuple[str, str], tuple[float, str, str]] = {}
    for doc_id, score in scores.items():
        d = docs[doc_id]
        if kind is not None and d["k"] != kind:
            continue
        key = (d["t"], d["f"])
        if key not in live:
            continue
        prev = best.get(key)
        if prev is None or score > prev[0]:
            best[key] = (score, d["snip"], d.get("h", ""))
    # Tie-break on the displayed name, not the identity key: the key is now
    # (tap, path), and ordering by it would silently reshuffle equal-scoring
    # results relative to every previous release.
    ranked = sorted(best.items(),
                    key=lambda kv: (-kv[1][0], live[kv[0]]["name"], kv[0]))
    # Over-fetch, then collapse byte-identical copies before taking k — the
    # duplicates have to be removed from the pool, not from the visible page,
    # or they still consume the slots they were removed from.
    hits: list[Hit] = [
        {"entry": live[key], "score": score, "content": digest,
         "snippet": snip}  # type: ignore[typeddict-item]
        for key, (score, snip, digest) in ranked]
    return _windowed(dedupe_by_content(hits, k), terms)


def rerank_cache_path() -> Path:
    """Where cached rerank orders live; in ``paths.INTERNAL_CACHE_FILES``."""
    return paths.cache_dir() / "rerank_cache.json"


#: FIFO cap on cached rerank orders. 200 entries is a few days of real use at
#: a few KB total; the point is bounding the file, not maximising hits.
RERANK_CACHE_CAP = 200


def _rerank_cache_load() -> dict:
    """The cache as a dict, ``{}`` for missing/corrupt — never an error."""
    try:
        data = json.loads(rerank_cache_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _rerank_cache_get(key: str) -> list | None:
    """A cached name order for ``key``, or None on any doubt at all."""
    order = _rerank_cache_load().get(key)
    return order if isinstance(order, list) and order else None


def _rerank_cache_put(key: str, order: list) -> None:
    """Store ``order``, evicting oldest-inserted beyond the cap.

    JSON objects round-trip in insertion order, so the dict itself is the
    FIFO — no timestamps to tie-break. Best-effort on purpose: a read-only
    cache dir loses the cache, never the search, and a concurrent writer
    clobbering this write costs a future miss, not corruption.
    """
    cache = _rerank_cache_load()
    cache.pop(key, None)
    cache[key] = order
    while len(cache) > RERANK_CACHE_CAP:
        cache.pop(next(iter(cache)))
    with contextlib.suppress(OSError):
        paths.ensure_dirs()
        util.atomic_write_text(rerank_cache_path(), json.dumps(cache))


#: The label `rerank` returns when the LLM pass actually ran. Every other value
#: is a retrieval engine's own name, i.e. "the rerank did not happen". Callers
#: that quote what the rerank buys have to be able to tell those apart without
#: string-matching a literal that could drift.
LLM_RANKER = "Claude relevance"


def rerank(query: str, hits: list[Hit], limit: int = 10,
           engine: str = "BM25 full-content") -> tuple[list[Hit], str]:
    """Reorder the shortlist with the LLM bridge; degrade to ``engine`` order.

    ``engine`` is the label from whichever retrieval actually produced ``hits``.
    Both degrade paths below return it rather than a hard-coded string: this
    function does not know how the shortlist was built, and guessing was wrong
    for every user whose dense store worked. Naming a specific wrong engine is
    worse than naming none — the label is the only signal about which engine
    answered, so a confident "BM25 full-content" sent debugging somewhere else.

    The default keeps direct callers unchanged; ``search`` passes the real one.

    Repeat calls answer from a small on-disk cache keyed on a hash of exactly
    what the LLM would see — query, limit, and the candidate listing — so it
    self-invalidates on any reindex, ranking drift, or snippet change without
    ever inspecting why. Only the parsed name order is stored; a hit replays
    through the same deterministic reorder below, and keeps the LLM_RANKER
    label because it *is* the LLM's ordering. ``BOOST_NO_RERANK_CACHE=1``
    bypasses both read and write (the Tier 2a eval sets it, so a graded
    rerank is always live).
    """
    top = hits[:max(limit, 15)]
    if not ai.available():
        return hits[:limit], engine
    listing = "\n".join(
        "- %s [%s]: %s" % (h["entry"]["name"], h["entry"].get("kind", "skill"),
                           (h["snippet"] or h["entry"].get("description", ""))[:180])
        for h in top)
    caching = not os.environ.get("BOOST_NO_RERANK_CACHE")
    cache_key = hashlib.sha256(
        ("%s\n%d\n%s" % (query, limit, listing)).encode("utf-8", "replace")
    ).hexdigest()
    order = _rerank_cache_get(cache_key) if caching else None
    if order is None:
        reply = ai.ask(
            "Task: %s\n\nCandidate skills (name, kind, best matching text):\n%s\n\n"
            "Order the skill names best-match-first for the task. "
            "Reply with ONLY a JSON array of names." % (query, listing),
            system="You rank AI coding skills by how well they fit a task.",
            max_tokens=400)
        order = _json_array(reply)
        if not order:
            # The model answered but not with a JSON array, so the ordering
            # falls back to whatever retrieval produced — and so must the
            # label. Not cached: a degrade reply is a retry, not an answer.
            return hits[:limit], engine
        if caching:
            _rerank_cache_put(cache_key, [str(n) for n in order])
    by_name = {h["entry"]["name"]: h for h in hits}
    picked = [by_name[str(n)] for n in order if str(n) in by_name]
    rest = [h for h in hits if h["entry"]["name"]
            not in {str(n) for n in order}]
    return (picked + rest)[:limit], LLM_RANKER


# The damping constant from the original reciprocal-rank-fusion paper. It is
# why plain RRF needs no tuning: large enough that the top few ranks are close
# together, so one engine's confident #1 cannot bury the other engine's #2.
RRF_K = 60


def rrf_fuse(rankings: list[list[Hit]], limit: int = 60) -> list[Hit]:
    """Fuse ranked hit lists by reciprocal rank: ``sum 1/(RRF_K + rank)``.

    Fuses on **ranks, not scores**, which is the whole point. A BM25 score and
    a cosine similarity are on incomparable scales, so blending them needs a
    calibration step that has to be fitted and re-fitted per corpus; rank
    fusion sidesteps it entirely and is the respected zero-tuning default.

    Entries are identified by ``entry_key`` — the same key both engines dedupe
    on — and the first ranking's hit object wins, so the caller passes BM25
    first and keeps its query-term-highlighted snippet for display.

    The returned ``score`` is the fused rank score, not a BM25 score: it exists
    to order these hits against each other, and comparing it to a raw BM25
    score from elsewhere would be meaningless.
    """
    scores: dict[tuple[str, str], float] = {}
    chosen: dict[tuple[str, str], Hit] = {}
    for hits in rankings:
        for rank, hit in enumerate(hits, start=1):
            entry = hit["entry"]
            key = entry_key(entry)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            chosen.setdefault(key, hit)
    ordered = sorted(scores, key=lambda key: (-scores[key], key[0], key[1]))
    fused: list[Hit] = [
        {"entry": chosen[key]["entry"], "score": scores[key],
         "snippet": chosen[key]["snippet"]}  # type: ignore[typeddict-item]
        for key in ordered[:limit]]
    return fused


def content_hashes() -> dict[tuple[str, str], str]:
    """``entry_key`` -> content hash, read from the BM25 index.

    The dense store does not carry the hash and does not need to: BM25 indexes
    the same entries and auto-builds on first search, so one map serves every
    engine. Keeping it in one place also means the two engines can never
    disagree about which copies are identical.
    """
    raw = _load_raw()
    if not raw:
        return {}
    return {(d["t"], d["f"]): d["h"]
            for d in raw.get("docs", []) if d.get("h")}


def _with_content(hits: list[Hit]) -> list[Hit]:
    """Attach content hashes to hits that lack them (dense, and fused output)."""
    if all(h.get("content") for h in hits):
        return hits
    hashes = content_hashes()
    if not hashes:
        return hits
    filled: list[Hit] = []
    for h in hits:
        if h.get("content"):
            filled.append(h)
            continue
        filled.append(cast(Hit, {
            "entry": h["entry"], "score": h["score"], "snippet": h["snippet"],
            "content": hashes.get(entry_key(h["entry"]), "")}))
    return filled


def retrieve_any(query: str, k: int = 60, kind: str | None = None,
                 entries: list[dict] | None = None,
                 collapse_near_duplicates: bool = False,
                 ) -> tuple[list[Hit] | None, str]:
    """Fuse BM25 and dense when both are available; floor to whichever is.

    Returns ``(hits, engine_label)``; ``hits`` is ``None`` only when no index of
    any kind exists so the caller can fall back to ``catalog.search``.

    Public because every retrieval entry point must make the same engine
    choice: `cmd_search` calling ``retrieve`` directly meant the CLI could
    never use a built dense index, while the MCP path could.

    This used to *prefer* dense whenever it was ready. The golden-set eval
    retired that: over 91 queries BM25 and local dense tie on hit@1, with the
    recall and MRR gaps inside the noise floor, while human-phrased queries
    separate them sharply in opposite directions. Preferring either one hands
    half the queries to the engine that is worse at them, so they are fused.

    Both engines are over-fetched to ``RRF_K`` before fusing. Fusing only the
    top-k of each would discard exactly the candidates the other engine was
    going to promote, which is most of the value.

    ``collapse_near_duplicates`` runs :func:`collapse_near_duplicate_hits` over
    the result, on top of the byte-identical dedup every branch below already
    does — off by default (see :data:`NEAR_DUPLICATE_THRESHOLD` for why) and a
    no-op whenever no dense store is built, since that is the only source of
    the embeddings the collapse needs.
    """
    from . import dense
    pool = max(k, RRF_K)
    dense_hits = dense.retrieve(query, k=pool, kind=kind,
                                entries=entries) if dense.ready() else None
    # An empty list is not the same answer as None. ``dense.retrieve`` returns
    # ``[]`` whenever every KNN neighbour was dropped for a kind mismatch or
    # for no longer being live, which is a *thin index*, not a verdict on the
    # query — and taking it as final short-circuits the documented "everything
    # degrades to BM25" contract, so `boost search` answered "no results" while
    # a perfectly good BM25 index sat unused. Only a non-empty dense result
    # counts as a ranking to fuse.
    bm25_hits = retrieve(query, k=pool, kind=kind,
                         entries=entries) if ready() else None
    # Dedupe at this seam as well as inside `retrieve`, because dense hits carry
    # no hash of their own and fusion can reintroduce a duplicate that BM25
    # already dropped — the copies are distinct `(tap, path)` keys, so RRF has
    # no reason to treat them as one.
    if dense_hits and bm25_hits:
        fused = rrf_fuse([bm25_hits, dense_hits], limit=max(k, RRF_K))
        hits, engine = dedupe_by_content(_with_content(fused), k), \
            "hybrid RRF (BM25 + dense)"
    elif dense_hits:
        hits, engine = dedupe_by_content(_with_content(dense_hits), k), \
            "dense vectors"
    elif bm25_hits is not None:
        hits, engine = bm25_hits[:k], "BM25 full-content"     # already deduped
    else:
        return None, ""
    if collapse_near_duplicates and hits and dense.ready():
        vectors = dense.entry_vectors([entry_key(h["entry"]) for h in hits])
        if vectors:
            hits = collapse_near_duplicate_hits(hits, vectors, k)
    return hits, engine


def search(query: str, limit: int = 10, kind: str | None = None,
           smart: bool = True,
           entries: list[dict] | None = None) -> tuple[list[Hit], str] | None:
    """Two-stage RAG search: dense-or-BM25 retrieve -> optional LLM rerank.

    Returns ``(hits, ranker_label)``, or ``None`` when no index exists yet so
    the caller can fall back to ``catalog.search``.
    """
    hits, engine = retrieve_any(query, max(60, limit * 4), kind, entries)
    if hits is None:
        return None
    if smart:
        # Hand the retrieval label down rather than dropping it: when the
        # rerank degrades, this is the only thing that knows what actually ran.
        return rerank(query, hits, limit, engine=engine)
    return hits[:limit], engine


def _json_array(text):
    m = re.search(r"\[.*\]", text or "", re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None
