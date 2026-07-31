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

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

try:  # TypedDict lives in typing on 3.9+, kept optional for safety
    from typing import TypedDict
except ImportError:  # pragma: no cover - 3.9+ always has it
    TypedDict = None  # type: ignore

from . import ai, catalog, frontmatter, gitutil, paths, registry, util

# v2: `snip` stores a larger head of the matched chunk (not just SNIP_WIDTH
# chars) so `retrieve` can window it onto the query terms; bump forces a
# one-time reindex.
INDEX_VERSION = 5
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

def tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and 1-char noise."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower())
            if len(t) >= 2 and t not in _STOPWORDS]


def chunk(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP,
          cap: int = MAX_CHUNKS) -> List[str]:
    """Split a body into passage-sized chunks on paragraph boundaries.

    Paragraphs are packed up to ``size`` chars; an oversized paragraph is
    hard-split with ``overlap`` carried across the cut so a match spanning a
    boundary is not lost. At most ``cap`` chunks are returned.
    """
    text = text.strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
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

def _tap_paths() -> Dict[str, Path]:
    return {t.name: t.path for t in registry.list_taps()}


def _tap_commits() -> Dict[str, str]:
    """Map safe tap name -> the commit its cache was built from."""
    commits: Dict[str, str] = {}
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


def read_body(entry: dict, tap_paths: Optional[Dict[str, Path]] = None) -> str:
    """Return an item's searchable text: name + description + prose body.

    The frontmatter is stripped (reusing ``frontmatter.parse``); the name and
    description are prepended so short items keep keyword parity with the old
    search. Missing files degrade to just the catalog metadata.
    """
    paths_map = _tap_paths() if tap_paths is None else tap_paths
    header = "%s\n%s" % (entry.get("name", ""), entry.get("description", ""))
    base = paths_map.get(entry.get("tap", ""))
    if base is None:
        base = paths.repos_dir() / str(entry.get("tap", "")).replace("/", "__")
    rel = entry.get("skill_md")
    if not rel:
        return header.strip()
    try:
        text = (base / rel).read_text(encoding="utf-8", errors="replace")
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


def _make_docs(entries: List[dict], tap_paths: Dict[str, Path]) -> List[dict]:
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
    docs: List[dict] = []
    for e in entries:
        body = read_body(e, tap_paths)
        # Hashed here because the body is already in hand; doing it at query
        # time would mean re-reading ~30k files to answer one search.
        digest = hashlib.sha256(body.strip().encode("utf-8", "replace")).hexdigest()[:16]
        tf: Dict[str, int] = defaultdict(int)
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


def _postings_to_doc_tf(raw: dict) -> Dict[int, Dict[str, int]]:
    """Invert persisted postings back to per-doc term frequencies."""
    doc_tf: Dict[int, Dict[str, int]] = defaultdict(dict)
    for term, plist in raw.get("postings", {}).items():
        for doc_id, tf in plist:
            doc_tf[doc_id][term] = tf
    return doc_tf


def _kept_docs(raw: dict, keep_safe: set) -> List[dict]:
    """Recover cached docs (with term freqs) for taps that did not change."""
    doc_tf = _postings_to_doc_tf(raw)
    return [{**meta, "tf": doc_tf.get(doc_id, {})}
            for doc_id, meta in enumerate(raw.get("docs", []))
            if meta["t"].replace("/", "__") in keep_safe]


def build(entries: Optional[List[dict]] = None, force: bool = False) -> dict:
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


def _save(docs: List[dict], commits: Dict[str, str]) -> None:
    postings: Dict[str, List[List[int]]] = defaultdict(list)
    meta_docs: List[dict] = []
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
        "postings": dict(postings.items()),
    }
    paths.ensure_dirs()
    p = index_path()
    # Atomic swap: a bare write_text here can leave a truncated/corrupt index
    # on disk if the process dies mid-write or a query reads concurrently.
    util.atomic_write_text(p, json.dumps(payload))
    # Drop the mtime-keyed cache so a reindex is visible to an immediately
    # following query even when the filesystem mtime granularity is coarse.
    _CACHE.pop(str(p), None)


def _now() -> str:
    return util.now_iso()


# ----------------------------------------------------------------- query

_CACHE: Dict[str, object] = {}


def _load_raw() -> Optional[dict]:
    p = index_path()
    key = str(p)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        _CACHE.pop(key, None)
        return None
    cached = _CACHE.get(key)
    if isinstance(cached, tuple) and cached[0] == mtime:
        return cached[1]  # type: ignore[return-value]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("version") != INDEX_VERSION:
        return None
    _CACHE[key] = (mtime, data)
    return data


def ready() -> bool:
    """True when a usable index exists on disk."""
    raw = _load_raw()
    return bool(raw and raw.get("docs"))


def ensure() -> bool:
    """Ensure a usable full-content index exists, building it on first use.

    This makes BM25 search the default for every surface (CLI + MCP) without the
    user having to run ``boost reindex`` first. Returns True when RAG is usable.
    Never raises: with no taps, or if the build fails, it returns False so the
    caller degrades to frontmatter search instead of erroring.
    """
    if ready():
        return True
    if not registry.list_taps():
        return False
    try:
        build()
    except Exception:
        return False
    return ready()


def _bm25(query_terms: List[str], raw: dict) -> Dict[int, float]:
    docs = raw["docs"]
    n = len(docs)
    avg = raw.get("stats", {}).get("avg_len") or 1.0
    postings = raw["postings"]
    scores: Dict[int, float] = defaultdict(float)
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


def entry_key(entry: dict) -> Tuple[str, str]:
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


def dedupe_by_content(hits: List[Hit], limit: int) -> List[Hit]:
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
    best: Dict[str, int] = {}          # content hash -> index into `out`
    out: List[Hit] = []
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
        # Same body already shown. Keep its rank, but prefer a curated source.
        kept = out[seen]
        if hit["entry"].get("curated") and not kept["entry"].get("curated"):
            # cast, not a literal annotation: `Hit` is total=False for the
            # optional `content` key, and NotRequired needs 3.11 while boost
            # targets 3.9.
            out[seen] = cast(Hit, {"entry": hit["entry"],
                                   "score": kept["score"],
                                   "snippet": kept["snippet"],
                                   "content": digest})
    return out[:limit]


def retrieve(query: str, k: int = 60, kind: Optional[str] = None,
             entries: Optional[List[dict]] = None) -> List[Hit]:
    """Top-k full-content hits for ``query``. ``[]`` if the index is empty."""
    raw = _load_raw()
    if not raw or not raw.get("docs"):
        return []
    terms = tokenize(query)
    if not terms:
        return []
    entries = catalog.all_entries() if entries is None else entries
    live = {entry_key(e): e for e in entries}
    docs = raw["docs"]
    best: Dict[Tuple[str, str], Tuple[float, str, str]] = {}
    for doc_id, score in _bm25(terms, raw).items():
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
    hits: List[Hit] = [
        {"entry": live[key], "score": score, "content": digest,
         "snippet": _passage(snip, terms)}  # type: ignore[typeddict-item]
        for key, (score, snip, digest) in ranked]
    return dedupe_by_content(hits, k)


def rerank(query: str, hits: List[Hit], limit: int = 10) -> Tuple[List[Hit], str]:
    """Reorder the shortlist with the LLM bridge; degrade to BM25 order."""
    top = hits[:max(limit, 15)]
    if not ai.available():
        return hits[:limit], "BM25 full-content"
    listing = "\n".join(
        "- %s [%s]: %s" % (h["entry"]["name"], h["entry"].get("kind", "skill"),
                           (h["snippet"] or h["entry"].get("description", ""))[:180])
        for h in top)
    reply = ai.ask(
        "Task: %s\n\nCandidate skills (name, kind, best matching text):\n%s\n\n"
        "Order the skill names best-match-first for the task. "
        "Reply with ONLY a JSON array of names." % (query, listing),
        system="You rank AI coding skills by how well they fit a task.",
        max_tokens=400)
    order = _json_array(reply)
    if not order:
        return hits[:limit], "BM25 full-content"
    by_name = {h["entry"]["name"]: h for h in hits}
    picked = [by_name[str(n)] for n in order if str(n) in by_name]
    rest = [h for h in hits if h["entry"]["name"]
            not in {str(n) for n in order}]
    return (picked + rest)[:limit], "Claude relevance"


# The damping constant from the original reciprocal-rank-fusion paper. It is
# why plain RRF needs no tuning: large enough that the top few ranks are close
# together, so one engine's confident #1 cannot bury the other engine's #2.
RRF_K = 60


def rrf_fuse(rankings: List[List[Hit]], limit: int = 60) -> List[Hit]:
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
    scores: Dict[Tuple[str, str], float] = {}
    chosen: Dict[Tuple[str, str], Hit] = {}
    for hits in rankings:
        for rank, hit in enumerate(hits, start=1):
            entry = hit["entry"]
            key = entry_key(entry)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            chosen.setdefault(key, hit)
    ordered = sorted(scores, key=lambda key: (-scores[key], key[0], key[1]))
    fused: List[Hit] = [
        {"entry": chosen[key]["entry"], "score": scores[key],
         "snippet": chosen[key]["snippet"]}  # type: ignore[typeddict-item]
        for key in ordered[:limit]]
    return fused


def content_hashes() -> Dict[Tuple[str, str], str]:
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


def _with_content(hits: List[Hit]) -> List[Hit]:
    """Attach content hashes to hits that lack them (dense, and fused output)."""
    if all(h.get("content") for h in hits):
        return hits
    hashes = content_hashes()
    if not hashes:
        return hits
    filled: List[Hit] = []
    for h in hits:
        if h.get("content"):
            filled.append(h)
            continue
        filled.append(cast(Hit, {
            "entry": h["entry"], "score": h["score"], "snippet": h["snippet"],
            "content": hashes.get(entry_key(h["entry"]), "")}))
    return filled


def retrieve_any(query: str, k: int = 60, kind: Optional[str] = None,
                 entries: Optional[List[dict]] = None
                 ) -> Tuple[Optional[List[Hit]], str]:
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
        return (dedupe_by_content(_with_content(fused), k),
                "hybrid RRF (BM25 + dense)")
    if dense_hits:
        return dedupe_by_content(_with_content(dense_hits), k), "dense vectors"
    if bm25_hits is not None:
        return bm25_hits[:k], "BM25 full-content"     # already deduped
    return None, ""


def search(query: str, limit: int = 10, kind: Optional[str] = None,
           smart: bool = True,
           entries: Optional[List[dict]] = None) -> Optional[Tuple[List[Hit], str]]:
    """Two-stage RAG search: dense-or-BM25 retrieve -> optional LLM rerank.

    Returns ``(hits, ranker_label)``, or ``None`` when no index exists yet so
    the caller can fall back to ``catalog.search``.
    """
    hits, engine = retrieve_any(query, max(60, limit * 4), kind, entries)
    if hits is None:
        return None
    if smart:
        return rerank(query, hits, limit)
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
