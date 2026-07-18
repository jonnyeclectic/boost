"""Optional dense vector backend for RAG Phase 2 (the ``[rag]`` extra).

Embeds every chunk (via :mod:`embed`) into a ``sqlite-vec`` virtual table and
answers queries by cosine KNN. It needs *both* the ``[rag]`` extra (``sqlite-vec``)
*and* an embeddings provider; when either is missing, or the persisted vectors
were built with a different provider/model, :func:`ready` is ``False`` and
callers fall back to the always-on BM25 engine in :mod:`rag`.

The vector store lives beside the BM25 index at ``~/.boost/cache/rag_vectors.sqlite``
and is refreshed per-tap on the git commit each tap was built from — embeddings
are the expensive step, so an unchanged tap is never re-embedded.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import catalog, embed, paths
from .rag import Hit, chunk, read_body

INDEX_VERSION = 1
_BATCH = 128            # texts per embedding request
_POOL = 8              # chunk over-fetch factor for KNN before per-entry reduce


def _load():
    """The sqlite_vec module, or None when the [rag] extra isn't installed."""
    try:
        import sqlite_vec  # type: ignore
    except ImportError:
        return None
    return sqlite_vec


def have_backend() -> bool:
    return _load() is not None


def db_path() -> Path:
    return paths.cache_dir() / "rag_vectors.sqlite"


def _connect() -> Optional[sqlite3.Connection]:
    """Open the vector DB with the sqlite-vec extension loaded, or None."""
    mod = _load()
    if mod is None:
        return None
    paths.ensure_dirs()
    con = sqlite3.connect(str(db_path()))
    try:
        con.enable_load_extension(True)
        mod.load(con)
        con.enable_load_extension(False)
    except (AttributeError, sqlite3.OperationalError):
        con.close()
        return None
    return con


def _ensure_schema(con: sqlite3.Connection, dim: int) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " name TEXT, tap TEXT, kind TEXT, cix INTEGER, snip TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS chunks_tap ON chunks(tap)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING "
        "vec0(embedding float[%d] distance_metric=cosine)" % dim)


def _read_meta(con: sqlite3.Connection) -> Dict[str, object]:
    try:
        rows = con.execute("SELECT k, v FROM meta").fetchall()
    except sqlite3.OperationalError:
        return {}
    out: Dict[str, object] = {}
    for k, v in rows:
        try:
            out[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            out[k] = v
    return out


def _write_meta(con: sqlite3.Connection, meta: Dict[str, object]) -> None:
    con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                    [(k, json.dumps(v)) for k, v in meta.items()])


def _wipe(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS chunks")
    con.execute("DROP TABLE IF EXISTS vec_chunks")


def _chunk_texts(entry: dict, tap_paths: Optional[Dict[str, Path]]
                 ) -> List[str]:
    body = read_body(entry, tap_paths)
    return chunk(body) or [body]


def ready() -> bool:
    """True when a usable, provider-matched vector index exists on disk."""
    if not have_backend() or not embed.available() or not db_path().exists():
        return False
    con = _connect()
    if con is None:
        return False
    try:
        meta = _read_meta(con)
        if meta.get("version") != INDEX_VERSION:
            return False
        if meta.get("provider") != embed.provider():
            return False
        if meta.get("dim") != embed.dimension():
            return False
        try:
            rows = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        except sqlite3.OperationalError:
            return False
        return rows > 0
    finally:
        con.close()


def build(entries: Optional[List[dict]] = None,
          force: bool = False) -> Optional[dict]:
    """(Re)embed and store chunk vectors, reusing unchanged taps.

    Returns stats, or ``None`` if the backend or an embeddings provider is
    unavailable (nothing is written in that case).
    """
    from .rag import _tap_commits, _tap_paths
    if not have_backend() or not embed.available():
        return None
    entries = catalog.all_entries() if entries is None else entries
    tap_paths = _tap_paths()
    commits = _tap_commits()
    dim = embed.dimension()
    prov = embed.provider()
    mdl = embed.model()
    con = _connect()
    if con is None or dim is None:
        return None
    try:
        meta = _read_meta(con)
        same_backend = (meta.get("provider") == prov and meta.get("dim") == dim)
        if force or not same_backend:
            _wipe(con)
        _ensure_schema(con, dim)

        reused: set = set()
        if same_backend and not force:
            old_commits = meta.get("commits", {})
            if isinstance(old_commits, dict):
                for safe, commit in commits.items():
                    if commit and old_commits.get(safe) == commit:
                        reused.add(safe)

        fresh = [e for e in entries
                 if e["tap"].replace("/", "__") not in reused]
        changed_taps = sorted({e["tap"] for e in fresh})
        _delete_taps(con, changed_taps)

        added = _embed_and_store(con, fresh, tap_paths)
        _write_meta(con, {"version": INDEX_VERSION, "provider": prov,
                          "model": mdl, "dim": dim, "commits": commits})
        con.commit()
        total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {
            "entries": len({(e["name"], e["tap"]) for e in entries}),
            "chunks": total,
            "added": added,
            "taps": len(commits),
            "reindexed": changed_taps,
            "reused": sorted(reused),
            "provider": prov,
            "model": mdl,
        }
    finally:
        con.close()


def _delete_taps(con: sqlite3.Connection, taps: List[str]) -> None:
    for tap in taps:
        ids = [r[0] for r in
               con.execute("SELECT id FROM chunks WHERE tap = ?", (tap,))]
        for i in ids:
            con.execute("DELETE FROM vec_chunks WHERE rowid = ?", (i,))
        con.execute("DELETE FROM chunks WHERE tap = ?", (tap,))


def _embed_and_store(con: sqlite3.Connection, entries: List[dict],
                     tap_paths: Optional[Dict[str, Path]]) -> int:
    mod = _load()
    rows: List[Tuple[dict, int, str]] = []   # (entry, chunk_ix, text)
    for e in entries:
        for ci, text in enumerate(_chunk_texts(e, tap_paths)):
            rows.append((e, ci, text))
    added = 0
    for start in range(0, len(rows), _BATCH):
        batch = rows[start:start + _BATCH]
        vecs = embed.embed([t for _e, _c, t in batch], input_type="document")
        if not vecs or len(vecs) != len(batch):
            continue
        for (e, ci, text), vec in zip(batch, vecs):
            cur = con.execute(
                "INSERT INTO chunks (name, tap, kind, cix, snip) "
                "VALUES (?, ?, ?, ?, ?)",
                (e["name"], e["tap"], e.get("kind", "skill"), ci,
                 text[:200].strip()))
            con.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                        (cur.lastrowid, mod.serialize_float32(vec)))
            added += 1
    return added


def retrieve(query: str, k: int = 60, kind: Optional[str] = None,
             entries: Optional[List[dict]] = None) -> Optional[List[Hit]]:
    """Top-k dense hits for ``query``, or None to signal 'fall back to BM25'."""
    if not ready():
        return None
    qv = embed.embed([query], input_type="query")
    if not qv:
        return None
    mod = _load()
    con = _connect()
    if con is None:
        return None
    try:
        pool = max(k * _POOL, 200)
        knn = con.execute(
            "SELECT rowid, distance FROM vec_chunks "
            "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (mod.serialize_float32(qv[0]), pool)).fetchall()
        if not knn:
            return []
        by_id = {r[0]: (r[1], r[2], r[3], r[4]) for r in con.execute(
            "SELECT id, name, tap, kind, snip FROM chunks WHERE id IN (%s)"
            % ",".join("?" * len(knn)), [rid for rid, _d in knn])}
    finally:
        con.close()

    entries = catalog.all_entries() if entries is None else entries
    live = {(e["name"], e["tap"]): e for e in entries}
    best: Dict[Tuple[str, str], Tuple[float, str]] = {}
    for rid, dist in knn:
        meta = by_id.get(rid)
        if meta is None:
            continue
        name, tap, ckind, snip = meta
        if kind is not None and ckind != kind:
            continue
        key = (name, tap)
        if key not in live:
            continue
        score = 1.0 - dist                       # cosine distance -> similarity
        prev = best.get(key)
        if prev is None or score > prev[0]:
            best[key] = (score, snip)
    ranked = sorted(best.items(), key=lambda kv: (-kv[1][0], kv[0][0]))
    hits: List[Hit] = []
    for (name, tap), (score, snip) in ranked[:k]:
        hits.append({"entry": live[(name, tap)], "score": score,
                     "snippet": snip})  # type: ignore[typeddict-item]
    return hits
