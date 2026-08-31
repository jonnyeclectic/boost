# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
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

import base64
import hashlib
import json
import sqlite3
from pathlib import Path

from ..errors import BoostError
from . import catalog, embed, paths
from .rag import Hit, chunk, entry_key, read_body

# 3 -- `chunks.digest` carries each row's entry content digest, which is what
#      lets reuse be decided per ENTRY rather than per tap. Bumping this is the
#      migration: a v2 store has no such column, `_ensure_schema` cannot add one
#      to an existing table (CREATE TABLE IF NOT EXISTS), and `build` already
#      wipes on a version change. That costs one full re-embed, once — the same
#      price v2 charged when it landed, and the last one this mechanism needs.
INDEX_VERSION = 3
_BATCH = 128            # texts per embedding request

#: Rows between commits while storing vectors. Small enough that an interrupted
#: build keeps almost everything it embedded, large enough that the commits are
#: not the cost — on a 750k-chunk store this is ~150 commits.
_COMMIT_EVERY = 5000
_POOL = 8              # chunk over-fetch factor for KNN before per-entry reduce


def _load():
    """The sqlite_vec module, or None when the [rag] extra isn't installed."""
    try:
        import sqlite_vec  # type: ignore
    except ImportError:
        return None
    return sqlite_vec


def have_backend() -> bool:
    """True when the ``sqlite-vec`` backend (the ``[rag]`` extra) imports."""
    return _load() is not None


def db_path() -> Path:
    """Path of the vector store: ``rag_vectors.sqlite`` in the cache dir."""
    return paths.cache_dir() / "rag_vectors.sqlite"


def _connect() -> sqlite3.Connection | None:
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


# How many binary candidates the exact rescore re-ranks. `vec0` has no ANN
# index — a `MATCH` is a full scan — so this is the only knob that decides how
# much of the store a query touches.
#
# Measured on a real 750,416-chunk / 1024-d store: 2048 gives recall@60 of
# 1.000 against a full float32 scan, for 0.35 s of rescore. 4096 costs 0.57 s
# and returns the same 60 rows, so the extra candidates are pure overhead.
RESCORE_POOL = 2048

#: How many result entries may share one byte-identical embedding.
#:
#: Registries paste boilerplate. On a real 657,587-chunk store the largest
#: cluster of byte-identical vectors is **1,464 copies spanning 1,464 distinct
#: skills across 2 taps** — one Composio/Rube tool-calling paragraph, vendored
#: into every skill in two registries. Identical vectors score an identical
#: distance, so `retrieve`'s tie-break (the displayed name) decided the page:
#: a query landing near that paragraph returned the alphabetically-first 60 of
#: the 1,464, measured **60 of 60 slots**, and every one of them matched on
#: text its skill did not write.
#:
#: `rag.dedupe_by_content` cannot reach this. It keys on the *entry* body
#: digest, and these are 1,464 genuinely different entries — correctly kept
#: apart. The repetition is one chunk *inside* each of them, which is a
#: different axis and the one `near-duplicate-items-eat-the-result-slots`
#: leaves open.
#:
#: Not 1, because two skills can legitimately share a paragraph that really is
#: the best answer; a handful shows that without letting it own the page.
MAX_PER_VECTOR = 3


def _quantizable(dim: int) -> bool:
    """Whether ``dim`` can be binary-quantized at all.

    `bit[N]` packs eight dimensions per byte, so sqlite-vec rejects any N that
    is not a multiple of 8. Every real embedding width is (384, 768, 1024,
    1536); the toy 3-d vectors in the unit suite are not, which is what keeps
    the float32 path exercised rather than dead.
    """
    return bool(dim) and dim % 8 == 0


def _has_table(con: sqlite3.Connection, name: str) -> bool:
    try:
        return con.execute("SELECT 1 FROM sqlite_master WHERE name = ? LIMIT 1",
                           (name,)).fetchone() is not None
    except sqlite3.DatabaseError:
        return False


def quantized(con: sqlite3.Connection) -> bool:
    """True when this store holds the two-stage (binary + exact) layout.

    Both halves are required and neither is useful alone: `vec_chunks_bin`
    ranks, `vec_raw` re-ranks. A store carrying only one is a half-finished
    migration, and answering True for it would route queries into a rescore
    with nothing to rescore against.
    """
    return _has_table(con, "vec_chunks_bin") and _has_table(con, "vec_raw")


def _ensure_schema(con: sqlite3.Connection, dim: int) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER, snip TEXT,"
        " digest TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS chunks_tap ON chunks(tap)")
    # Keyed by (tap, path) because that is `rag.entry_key` — row identity, the
    # thing an entry's chunks belong to. Keying it on `digest` alone would be
    # the content question, which is a different one: two taps shipping the
    # same file share a digest and must still be deleted independently.
    con.execute("CREATE INDEX IF NOT EXISTS chunks_entry ON chunks(tap, path)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    if _quantizable(dim):
        # Two relations, because one cannot do both jobs. `vec0` is the only
        # thing that can run a KNN, and it cannot fetch a row by rowid: an
        # `id IN (...)` against it plans as `SCAN ... VIRTUAL TABLE`, and 256
        # single-row lookups measured 3.2 s. A plain rowid-keyed table is the
        # opposite — useless for KNN, O(log n) per row — so the coarse pass
        # lives in `vec_chunks_bin` and the exact rescore reads `vec_raw`.
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks_bin USING "
                    "vec0(embedding bit[%d])" % dim)
        con.execute("CREATE TABLE IF NOT EXISTS vec_raw "
                    "(id INTEGER PRIMARY KEY, embedding BLOB)")
    else:
        con.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING "
            "vec0(embedding float[%d] distance_metric=cosine)" % dim)


def _store_vector(con: sqlite3.Connection, rowid: int | None,
                  blob: bytes) -> None:
    """Write one chunk's vector into whichever layout this store uses.

    Quantization happens in SQL rather than in Python: `vec_quantize_binary`
    is the same function the query side calls on the query vector, so the two
    can never disagree about how a float becomes a bit.

    ``rowid`` is a caller's ``cursor.lastrowid``, which sqlite3 types as
    optional. It is None only if the INSERT that produced it did not happen, so
    this refuses rather than storing a vector nothing can join back to — an
    orphan in `vec_raw` outlives every tap deletion, since those are scoped
    through `chunks.tap`.
    """
    if rowid is None:
        raise BoostError("vector store insert produced no row id")
    if quantized(con):
        con.execute("INSERT INTO vec_chunks_bin (rowid, embedding) "
                    "VALUES (?, vec_quantize_binary(vec_f32(?)))", (rowid, blob))
        con.execute("INSERT INTO vec_raw (id, embedding) VALUES (?, ?)",
                    (rowid, blob))
    else:
        con.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                    (rowid, blob))


def _drop_vectors(con: sqlite3.Connection, ids: list[int]) -> None:
    """Remove these chunk ids from every vector relation the store has."""
    for i in ids:
        # vec0 deletes one rowid at a time; the plain table takes a set.
        for tbl in ("vec_chunks", "vec_chunks_bin"):
            if _has_table(con, tbl):
                con.execute("DELETE FROM %s WHERE rowid = ?" % tbl, (i,))  # noqa: S608  table name from a literal tuple
    if ids and _has_table(con, "vec_raw"):
        con.execute("DELETE FROM vec_raw WHERE id IN (%s)"  # noqa: S608  interpolates only `?` placeholders
                    % ",".join("?" * len(ids)), ids)


def _read_meta(con: sqlite3.Connection) -> dict[str, object]:
    try:
        rows = con.execute("SELECT k, v FROM meta").fetchall()
    except sqlite3.OperationalError:
        return {}
    out: dict[str, object] = {}
    for k, v in rows:
        try:
            out[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            out[k] = v
    return out


def _write_meta(con: sqlite3.Connection, meta: dict[str, object]) -> None:
    con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                    [(k, json.dumps(v)) for k, v in meta.items()])


def _wipe(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS chunks")
    con.execute("DROP TABLE IF EXISTS vec_chunks")
    # Both halves of the quantized layout, or a --force rebuild leaves the old
    # vectors behind to be merged with the new ones under reused rowids.
    con.execute("DROP TABLE IF EXISTS vec_chunks_bin")
    con.execute("DROP TABLE IF EXISTS vec_raw")


def _chunk_texts(entry: dict, tap_paths: dict[str, Path] | None
                 ) -> list[str]:
    body = read_body(entry, tap_paths)
    return chunk(body) or [body]


def _chunk_total(con: sqlite3.Connection, meta: dict,
                 *, exact: bool) -> tuple[int | None, bool]:
    """``(count-or-None, has-any-rows)`` — O(1) unless ``exact`` is asked for.

    Counting `chunks` was the single most expensive thing a `boost search` did.
    Every BM25-only search ends in a hint that calls :func:`status`, and
    `SELECT COUNT(*) FROM chunks` scans the whole `chunks_tap` covering index:
    measured on a real 445-tap store, 8,419 pages / 34.5 MB inside a 3.4 GB
    file, 1.94 s with those pages already warm and the dominant term in a
    33.9 s cold search — about 79% of a warm one, to choose the wording of a
    single muted line.

    The hot path never actually needed the number. It needs to know whether the
    store has *any* rows, which is one indexed probe, and one `fix_hint` branch
    wants the total, which a store built after this change records in `meta` —
    9 pages, read anyway.

    Three sources, cheapest first:

    * ``meta["chunks"]``, stamped by :func:`build` and :func:`import_shard`;
    * a ``LIMIT 1`` existence probe, which answers the `empty` reason exactly
      and leaves the total unknown;
    * the full scan, only when a caller says it can afford one (`boost doctor`).

    Returning ``None`` for "not recorded" rather than ``0`` is the load-bearing
    part: a legacy store has vectors the user paid to embed, and reporting zero
    would route it to advice that re-embeds all of them.
    """
    recorded = meta.get("chunks")
    if isinstance(recorded, int) and not isinstance(recorded, bool) and recorded >= 0:
        return recorded, recorded > 0
    try:
        if exact:
            n = int(con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            return n, n > 0
        # Stops at the first row: a b-tree descent, not a walk.
        row = con.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
    except sqlite3.DatabaseError:
        # No `chunks` table at all — nothing built, which is the ordinary
        # empty case rather than the corrupt one. Exact by definition.
        return 0, False
    return None, row is not None


def _recorded_meta(*, count: bool = False) -> dict:
    """What an existing store says it was built with, read WITHOUT sqlite-vec.

    Deliberately not routed through :func:`_connect`, which loads the extension
    and returns ``None`` without it: the most useful diagnostic line ("your
    store was built with voyage-3") would then vanish in exactly the case that
    needs it — a user who dropped the ``[rag]`` extra and wants to know why
    dense went quiet. ``meta`` is a plain table, so plain sqlite3 can read it.
    """
    p = db_path()
    if not p.exists():
        return {}
    try:
        con = sqlite3.connect(str(p))
    except sqlite3.Error:
        return {}
    try:
        meta = _read_meta(con)
        meta["_chunks"], meta["_nonempty"] = _chunk_total(con, meta, exact=count)
        meta["_quantized"] = quantized(con)
        return meta
    except sqlite3.DatabaseError:
        # A truncated or non-sqlite file: report "no store", never raise into
        # a health check whose whole job is to survive a broken install.
        return {}
    finally:
        con.close()


def tap_commits() -> dict[str, str]:
    """Which registry commit this store holds vectors for, per tap safe-name.

    The store already records this — ``build`` writes it and ``import_shard``
    updates it — but only as a private meta field, so every caller that wanted
    to ask "are these vectors for the commit I have?" had to re-open the
    database. That question is the whole basis of skipping work: a weekly shard
    refresh is a no-op exactly when the answer is yes, and without an accessor
    the refresh would download and re-import a store's own rows every week.

    Read without sqlite-vec (see :func:`_recorded_meta`) so a machine that lost
    the extra still gets a truthful answer rather than an empty one.
    """
    meta = _recorded_meta()
    if meta.get("version") != INDEX_VERSION:
        # A store from an older boost is about to be discarded — `build` wipes
        # it and so does `import_shard` — so it holds no vectors anyone can
        # reuse, and saying otherwise is worse than saying nothing. The caller
        # asking this question is deciding which taps to SKIP: answering with a
        # stale store's commits let `ingest` skip 417 taps as "already current"
        # and then wipe their vectors on the first import, leaving a store that
        # was silently missing them while the output said they were fine.
        return {}
    commits = meta.get("commits")
    if not isinstance(commits, dict):
        return {}
    return {str(k): str(v) for k, v in commits.items() if v}


# Why dense retrieval isn't serving, keyed by the `reason` status() returns.
# Each names the ONE next action; the reason order in status() guarantees only
# the first missing link is ever reported, so these never chain.
#
# Lives here rather than in a command module because two surfaces need the same
# answer — `boost doctor` and `boost search` — and two copies would drift, which
# is how a surface ends up telling a user to set an API key that the [rag]
# extra's local model already made unnecessary.
_FIX = {
    "no-backend": "install the extra: `pip install 'boost-skill-cli[rag]'`",
    # Names the keyless remedy first: since the [rag] extra carries a local
    # embedding model, an API key is the quality ceiling, not the entry fee.
    # This reason means "no key AND no local backend", which in practice is a
    # partial install or BOOST_NO_EMBED.
    "no-key": ("reinstall the extra: `pip install 'boost-skill-cli[rag]'` "
               "(or set VOYAGE_API_KEY / OPENAI_API_KEY for a larger model)"),
    "no-store": "build it: `boost reindex --dense`",
    "version-changed": "rebuild it: `boost reindex --dense --force`",
    "provider-changed": "rebuild it: `boost reindex --dense --force`",
    "model-changed": "rebuild it: `boost reindex --dense --force`",
    "dim-changed": "rebuild it: `boost reindex --dense --force`",
    "empty": "rebuild it: `boost reindex --dense --force`",
}


def fix_hint(reason: str, status: dict | None = None) -> str:
    """The single next action for a `status()` reason, or a safe default.

    Pass the whole ``status()`` dict when you have one. The reason alone is
    ambiguous for ``no-key``, and getting it wrong there is expensive rather
    than merely unhelpful: the table's generic answer is "reinstall the extra",
    which for a user whose store was built against an API provider installs the
    *local* model, flips ``provider()`` to ``local``, and turns their next
    status into ``provider-changed`` — a full re-embed of every vector they
    already paid for. Seen in the wild at 750,416 chunks.

    The reason ladder cannot distinguish these two states on its own, because
    ``no-key`` is checked before the store is even looked at: an unfinished
    install with no store and a complete install whose key merely went missing
    both land here. ``built_provider`` is what separates them, and it lives in
    the status dict.

    Backwards compatible on purpose — every existing single-argument call keeps
    the table's answer, so a caller with no status in hand is never worse off.
    """
    if reason == "no-key" and status:
        env = embed.KEY_ENV.get(status.get("built_provider") or "")
        # `chunks` guards the unfinished-install case: without vectors on disk
        # there is nothing a key would revive, and "build it" is the real next
        # step. A store built by the local model has no env var and correctly
        # falls through — that user does need the package back.
        count = status.get("chunks")
        # `None` is "a store is here and never recorded its total" — a legacy
        # store, not an unfinished one. Only a *known* zero means there are no
        # vectors to revive; reading unknown as zero would send exactly the
        # user this branch exists to protect to the re-embed-everything answer.
        if env and (count is None or count > 0):
            n = f"{int(count):,} vectors" if count else "vectors"
            return ("set the key it was built with: `export %s=...` — "
                    "reinstalling the extra swaps in the local model and "
                    "forces all %s to be re-embedded" % (env, n))
    return _FIX.get(reason, "see `boost reindex --dense`")


def status(*, count: bool = False) -> dict:
    """Why dense retrieval is, or is not, serving queries.

    ``count`` buys an exact ``chunks`` total at the price of scanning the store
    (see :func:`_chunk_total`). It is off by default because the caller that
    runs on every single search — `boost search`'s one-line hint — does not use
    the number, while paying for it made that scan ~79% of a warm search and
    the bulk of a cold one. `boost doctor` prints the total, so it asks.

    With ``count=True`` the total is always an int. Without it, ``chunks`` is
    ``None`` whenever a pre-existing store never recorded its own total;
    ``chunks_exact`` says which you got, and ``reason`` is still exact either
    way — emptiness comes from a cheap probe, not from the count.

    Pure inspection — never builds, never embeds, never needs the extra. Three
    independent things must line up (the ``[rag]`` extra, an embeddings key, a
    built store whose space matches the live one) and every one of them fails
    *silently* today, because :func:`rag.retrieve_any` floors to BM25 and
    returns. ``reason`` names which link is missing so a caller can say so.

    ``degraded`` is the load-bearing distinction: a user who never configured
    dense search is *healthy* (BM25 is the documented default), while a user
    who did all three steps and is still on BM25 has a real problem no other
    surface reports. Only the latter should move an exit code.
    """
    have_be = have_backend()
    prov, mdl, dim = embed.provider(), embed.model(), embed.dimension()
    meta = _recorded_meta(count=count)
    b_prov = meta.get("provider")
    b_mdl = meta.get("model")
    b_dim = meta.get("dim")
    b_ver = meta.get("version")
    commits = meta.get("commits")
    raw_chunks = meta.get("_chunks")
    chunks = int(raw_chunks) if isinstance(raw_chunks, int) else None
    # Emptiness is answered by the probe, never by the count — that is what
    # lets the count stay unknown without any reason becoming a guess.
    nonempty = bool(meta.get("_nonempty"))
    store_exists = bool(meta)

    # Order matters: report the *first* missing link, so the message names the
    # next action rather than a downstream symptom of the same gap.
    if not have_be:
        reason: str | None = "no-backend"
    elif prov is None:
        reason = "no-key"
    elif not store_exists:
        reason = "no-store"
    elif b_ver != INDEX_VERSION:
        reason = "version-changed"
    elif b_prov != prov:
        reason = "provider-changed"
    elif b_mdl != mdl:
        reason = "model-changed"
    elif b_dim != dim:
        reason = "dim-changed"
    elif not nonempty:
        reason = "empty"
    else:
        reason = None

    # Unconfigured is not degraded; a built-but-unusable store is. Vectors on
    # disk are the proof of intent — the user paid to embed them, so anything
    # that stops them serving (a dropped extra, an unset key, a changed model)
    # is a real fault. Without a store there is nothing to have regressed:
    # "no-store" is an unfinished setup, and it is the one reason that implies
    # store_exists is False, so this single clause covers every case.
    degraded = store_exists and reason is not None

    return {
        "backend": have_be,
        "provider": prov, "model": mdl, "dim": dim,
        "store_exists": store_exists,
        "built_provider": b_prov, "built_model": b_mdl,
        "built_dim": b_dim, "built_version": b_ver,
        "chunks": chunks,
        "chunks_exact": chunks is not None,
        # Ready-but-unquantized is a real state and the only one that is fast
        # to fix and expensive to leave: correct answers, at a full scan per
        # query. Nothing else in this dict distinguishes it.
        "quantized": bool(meta.get("_quantized")),
        "taps": len(commits) if isinstance(commits, dict) else 0,
        "ready": reason is None,
        "reason": reason,
        "degraded": degraded,
    }


def ready() -> bool:
    """True when a usable, provider-matched vector index exists on disk.

    The stat comes first, deliberately: on a machine with no vector store —
    every BM25-only install — this must answer False without importing the
    backend, because ``have_backend()`` drags in numpy via sqlite_vec
    (~120 ms measured) and every cold ``boost search`` asks.
    """
    if not db_path().exists():
        return False
    if not have_backend() or not embed.available():
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
        # Model, not just provider+dim: two models from one provider can share
        # a dimension and still be different embedding spaces (voyage-3 and
        # voyage-4 are both 1024-d), so serving stale vectors would silently
        # mix spaces rather than fail loudly.
        if meta.get("model") != embed.model():
            return False
        if meta.get("dim") != embed.dimension():
            return False
        # Existence, not a total: this runs on every search that has a store to
        # consult, and counting `chunks` walks its whole covering index — 34.5
        # MB on a real 445-tap store — to answer a yes/no question. `LIMIT 1`
        # stops at the first row. See `_chunk_total` for the measurements.
        return _chunk_total(con, meta, exact=False)[1]
    finally:
        con.close()


def build(entries: list[dict] | None = None, force: bool = False,
          on_progress=None) -> dict | None:
    """(Re)embed and store chunk vectors, reusing unchanged taps.

    Returns stats, or ``None`` if the backend or an embeddings provider is
    unavailable (nothing is written in that case).

    ``on_progress(done, total)`` is called before the first batch and after
    each one. It exists because this is the longest-running thing boost does —
    a full catalogue is tens of thousands of distinct chunks at roughly a
    second each — and it used to run under a bare spinner that said "embedding
    chunks into the dense store" for hours without a number. A user cannot
    tell that apart from a hang, and the honest fix is to say how many there
    are and how far in we got.
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
        # The stored INDEX_VERSION has to be part of this. `_ensure_schema` uses
        # CREATE TABLE IF NOT EXISTS, so it cannot add a column to a store built
        # by an older boost — leaving the build to fail on the first INSERT with
        # "table chunks has no column named path". `status()` already treated a
        # version change as a reason to rebuild; only the build path did not.
        same_version = meta.get("version") == INDEX_VERSION
        same_backend = (same_version
                        and meta.get("provider") == prov
                        and meta.get("model") == mdl
                        and meta.get("dim") == dim)
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

        candidates = [e for e in entries
                      if e["tap"].replace("/", "__") not in reused]
        changed_taps = sorted({e["tap"] for e in candidates})
        # Prune taps that are gone entirely, not only the ones that changed.
        # `boost untap` removes a tap's entries, so it can never appear in
        # `candidates` and its vectors survived every later incremental build —
        # crowding the KNN pool on every query with rows `retrieve` then
        # discards for not being live, which is how a dense search quietly
        # returns fewer hits the longer an index has been in use.
        removed_taps = sorted(_indexed_taps(con) - {e["tap"] for e in entries})
        _delete_taps(con, removed_taps)

        # Second-level reuse, and the reason it is worth the column. A tap's
        # commit moving says *something* in that clone changed — not that
        # anything boost indexes did. Measured on a real 464-tap install: 19
        # taps drifted in 6.85 h, and 10 of them changed nothing indexed at all
        # (badge JSON, star-history SVGs, CI YAML, e2e TypeScript), yet cost
        # 44,866 chunks — 40.0% of the incremental bill. Across all 19, 967
        # changed files mapped to 39 indexed entries owning 659 chunks, against
        # 112,081 re-embedded: 170x the actual change.
        #
        # The digest is not new identity machinery. `catalog._content_digest`
        # already stamps every entry with a hash of exactly what `read_body`
        # assembles, and `tests/unit/test_content_identity.py` pins that parity
        # — so an entry whose digest matches the one stored beside its chunks
        # is one whose embedded text is byte-identical.
        fresh, kept = _split_by_digest(con, candidates)
        _delete_entries(con, [entry_key(e) for e in fresh])
        # An entry deleted upstream keeps answering queries otherwise: whole-tap
        # deletion used to sweep it for free, and reuse is exactly what stops
        # that happening.
        _prune_stale_entries(con, changed_taps, {entry_key(e) for e in entries})

        added, failed_taps = _embed_and_store(con, fresh, tap_paths,
                                             on_progress=on_progress)
        # Only record a commit for a tap whose chunks actually landed. Recording
        # one for a tap that stored nothing makes every later non-forced run
        # treat it as already built and skip it — one transient rate limit would
        # otherwise leave the store permanently empty until `--force`.
        failed_safe = {t.replace("/", "__") for t in failed_taps}
        recorded = {safe: c for safe, c in commits.items()
                    if safe not in failed_safe}
        # Counted before the meta write, not after, so the total can be stamped
        # into `meta` — that is what lets every later `status()` skip the scan
        # (see `_chunk_total`). The build already paid for this count.
        total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        _write_meta(con, {"version": INDEX_VERSION, "provider": prov,
                          "model": mdl, "dim": dim, "commits": recorded,
                          "chunks": total})
        con.commit()
        return {
            "entries": len({entry_key(e) for e in entries}),
            "chunks": total,
            "added": added,
            "taps": len(commits),
            "reindexed": changed_taps,
            "pruned": removed_taps,
            "reused": sorted(reused),
            # Entries inside a moved tap whose content had not changed. This is
            # the number the tap-level `reused` cannot show — a tap appears in
            # `reindexed` the moment its commit moves, and on real data most of
            # its entries are still untouched.
            "reused_entries": len(kept),
            "embedded_entries": len(fresh),
            "failed": sorted(failed_taps),
            "provider": prov,
            "model": mdl,
        }
    finally:
        con.close()


def export_shard(tap: str) -> dict:
    """One tap's vectors plus the provenance needed to validate them later.

    Embedding is the expensive half of the keyless tier — measured at ~1.2 s per
    chunk on CPU, so 74 minutes for 743 entries — while querying is milliseconds.
    A shard lets that cost be paid once in CI and downloaded by everyone else.

    The provenance fields are not decoration: vectors are only comparable inside
    the embedding space that produced them, so provider/model/dim have to travel
    with the rows, and the registry commit has to travel too or a stale shard
    would be indistinguishable from a current one.

    Raises :class:`BoostError` when the rows are present and unreadable, which is
    a different problem from having none — see below.
    """
    if not db_path().exists():
        return {"tap": tap, "chunks": []}
    # `vec_chunks` is a vec0 VIRTUAL table, so reading an embedding needs the
    # extension loaded: on a plain connection the join below raises `no such
    # module: vec0`, every time, for every tap. An earlier revision opened
    # plainly on the theory that export "reads ordinary tables" — true of
    # `chunks` and `meta`, false of the one relation holding the vectors — and
    # the resulting failure was swallowed into an empty shard. That is why no
    # scheduled `shards` run has ever produced an artifact. Fall back to a plain
    # connection anyway: it still serves a store whose vectors live in an
    # ordinary table, and it is what makes the distinction below observable
    # rather than an exception from the connect call.
    con = _connect()
    if con is None:
        try:
            con = sqlite3.connect(str(db_path()))
        except sqlite3.Error:
            return {"tap": tap, "chunks": []}
    try:
        meta = _read_meta(con)
        commits = meta.get("commits")
        commit = ""
        if isinstance(commits, dict):
            commit = str(commits.get(tap.replace("/", "__")) or "")
        # `chunks` alone, first, because it is an ordinary table and therefore
        # always readable. It answers the question the caller's error message
        # depends on: are there rows for this tap at all?
        expected = _tap_chunk_count(con, tap)
        chunks = []
        try:
            # `vec_raw` on a quantized store is an ordinary table, so this
            # join needs no extension at all — which is the failure this
            # function's docstring describes, gone rather than worked around.
            vt = "vec_raw v ON v.id = c.id" if quantized(con) \
                else "vec_chunks v ON v.rowid = c.id"
            rows = con.execute(
                "SELECT c.name, c.tap, c.path, c.kind, c.cix, c.snip, "  # noqa: S608  relation name from a literal pair
                "c.digest, v.embedding "
                "FROM chunks c JOIN %s WHERE c.tap = ? ORDER BY c.id" % vt,
                (tap,)).fetchall()
        except sqlite3.Error as exc:
            # Only a tap that HAS chunks can have unreadable ones. With none,
            # the vector relation not resolving says nothing about this tap —
            # it is the ordinary "nothing built here" case, and the caller's
            # "build them first" is the right answer.
            if not expected:
                return {"tap": tap, "chunks": []}
            raise _unreadable_vectors(tap, expected, exc) from exc
        if expected and not rows:
            # The join resolved but produced nothing for a tap that has chunks:
            # the vector rows are gone or unlinked. Still not "never built".
            raise _unreadable_vectors(tap, expected, None)
        for row in rows:
            name, ctap, path, kind, cix, snip, digest, emb = row
            chunks.append({
                "name": name, "tap": ctap, "path": path, "kind": kind,
                "cix": cix, "snip": snip,
                # The digest travels with the vector or the shard defeats its
                # own purpose: `_split_by_digest` reuses an entry only when the
                # stored digest matches the catalog's, so an imported chunk
                # without one is re-embedded on the very next build — paying
                # in CPU exactly what downloading the shard was meant to save.
                "digest": digest,
                # base64 so the shard is plain JSON and can be published as a
                # release artifact without a binary format of its own.
                "embedding": base64.b64encode(bytes(emb)).decode("ascii"),
            })
        return {"tap": tap, "commit": commit,
                "provider": meta.get("provider"), "model": meta.get("model"),
                "dim": meta.get("dim"), "version": INDEX_VERSION,
                "chunks": chunks}
    finally:
        con.close()


def _tap_chunk_count(con: sqlite3.Connection, tap: str) -> int:
    """How many chunk rows this tap has, or 0 when `chunks` is unreadable.

    Deliberately forgiving: a store with no `chunks` table has nothing built,
    which is the ordinary empty case rather than the corrupt one.
    """
    try:
        row = con.execute("SELECT COUNT(*) FROM chunks WHERE tap = ?",
                          (tap,)).fetchone()
    except sqlite3.Error:
        return 0
    return int(row[0]) if row else 0


def _unreadable_vectors(tap: str, expected: int,
                        exc: sqlite3.Error | None) -> BoostError:
    """The error for "the rows are there, and this process cannot read them".

    Kept apart from the empty case on purpose. Both used to surface as `no
    vectors for <tap>` with the hint `build them first with reindex --dense` —
    advice that is correct for an unbuilt store and a dead end for this one,
    because `reindex --dense` is what wrote the rows the message says are
    missing. Two scheduled `shards` runs died against that loop.
    """
    detail = ": %s" % exc if exc is not None else ""
    return BoostError(
        "%s has %d embedded chunk%s but its vectors cannot be read%s"
        % (tap, expected, "" if expected == 1 else "s", detail),
        hint="reading vectors needs the sqlite-vec extension — install the "
             "`rag` extra (`pip install 'boost-skill-cli[rag]'`); the rows "
             "themselves are intact, so no re-embedding is required")


def import_shard(shard: dict, commit: str) -> tuple[bool, str]:
    """Merge a prebuilt shard into this machine's store. ``(ok, reason)``.

    Refuses rather than degrades. A vector is only meaningful against others
    from the same embedding space, so a shard from a different provider, model
    or dimension cannot be mixed in: doing so would not raise, it would quietly
    return nonsense rankings, which is the worse failure. A shard whose commit
    does not match the tap as it stands now is refused for a different reason —
    accepting it would let `build()` mark that tap "reused" and never re-embed
    it, pinning the user to stale vectors indefinitely.
    """
    for field in ("provider", "model", "dim"):
        if shard.get(field) in (None, ""):
            return False, "shard is missing %s" % field
    if str(shard.get("commit") or "") != commit:
        return False, ("commit mismatch: shard %r, tap %r"
                       % (shard.get("commit"), commit))
    con = _connect()
    if con is None:
        return False, "no vector backend available"
    try:
        meta = _read_meta(con)
        if meta.get("version") not in (None, INDEX_VERSION):
            # The same wipe `build` does, for the same reason: `_ensure_schema`
            # is CREATE TABLE IF NOT EXISTS, so it cannot add v3's `digest`
            # column to a table built by an older boost, and the INSERT below
            # would fail per row with "table chunks has no column named
            # digest". On a real machine that is 449 shards reporting a sqlite
            # message about a column, where the honest answer is that the store
            # predates this format. Wiping loses nothing that was in use — a
            # stale-version store is already dead weight, refused by `ready()`
            # and wiped by `build()` on its next run.
            _wipe(con)
            meta = {}
        # An empty store has no opinion yet, so it adopts the shard's backend.
        if meta.get("provider"):
            for field in ("provider", "model", "dim"):
                if meta.get(field) != shard.get(field):
                    return False, ("%s mismatch: store %r, shard %r"
                                   % (field, meta.get(field), shard.get(field)))
        dim = int(shard["dim"])
        _ensure_schema(con, dim)
        # Replace, never append: re-importing must not double a tap's rows.
        _delete_taps(con, [str(shard.get("tap") or "")])
        mod = _load()
        for c in shard.get("chunks") or []:
            cur = con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, snip, digest) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (c.get("name"), c.get("tap"), c.get("path"), c.get("kind"),
                 c.get("cix"), c.get("snip"),
                 # A shard published before the digest travelled has none, and
                 # None is the honest value: that tap re-embeds once, which is
                 # what it did before this existed. Never a placeholder — a
                 # wrong digest would suppress a real re-embed forever.
                 c.get("digest")))
            blob = base64.b64decode(c["embedding"])
            _store_vector(con, cur.lastrowid, blob)
        commits = meta.get("commits")
        commits = dict(commits) if isinstance(commits, dict) else {}
        commits[str(shard.get("tap") or "").replace("/", "__")] = commit
        _write_meta(con, {"version": INDEX_VERSION,
                          "provider": shard.get("provider"),
                          "model": shard.get("model"), "dim": dim,
                          "commits": commits,
                          # Keep the recorded total true after a merge, or the
                          # next `status()` serves a stale number forever.
                          "chunks": con.execute(
                              "SELECT COUNT(*) FROM chunks").fetchone()[0]})
        con.commit()
        _ = mod          # extension loaded by _connect; kept for symmetry
        return True, "imported %d chunks" % len(shard.get("chunks") or [])
    except sqlite3.Error as exc:
        return False, "store error: %s" % exc
    finally:
        con.close()


def _indexed_taps(con: sqlite3.Connection) -> set:
    """Every tap name the vector index currently holds chunks for."""
    try:
        return {r[0] for r in con.execute("SELECT DISTINCT tap FROM chunks")}
    except sqlite3.OperationalError:
        return set()          # no chunks table yet — nothing indexed, nothing stale


def _delete_matching(con: sqlite3.Connection, where: str,
                     params: tuple) -> int:
    """Drop the chunk rows matching ``where``, and their vectors. Rows hit.

    Deleting a chunk is two statements that must not drift apart: the vectors
    go through :func:`_drop_vectors` (which knows both store layouts) and only
    then does the row go. Tap-level and entry-level deletion had that pair
    written out twice, which is one copy too many for a rule this easy to half-
    apply — an orphan vector outlives every later deletion, because those are
    all scoped through ``chunks``.

    ``where`` is a literal from this module, never caller data; the parameters
    are bound.
    """
    # `%` rather than `+`, to match every other interpolated statement in this
    # module: those are the shapes ruff's S608 is known to flag here, so the
    # suppression is one ruff actually consumes rather than an unused `noqa`
    # that RUF100 would then reject.
    ids = [r[0] for r in con.execute(
        "SELECT id FROM chunks WHERE %s" % where, params)]  # noqa: S608  literal clause
    if not ids:
        return 0
    _drop_vectors(con, ids)
    con.execute("DELETE FROM chunks WHERE %s" % where, params)  # noqa: S608  same literal
    return len(ids)


def _delete_entries(con: sqlite3.Connection,
                    keys: list[tuple[str, str]]) -> int:
    """Drop every chunk row for these ``(tap, path)`` entries. Returns rows hit.

    The entry-level counterpart to :func:`_delete_taps`, and it must stay
    row-scoped rather than content-scoped: two taps can ship a byte-identical
    file, so deleting by digest would take another tap's rows with it.
    """
    return sum(_delete_matching(con, "tap = ? AND path = ?", (tap, path))
               for tap, path in keys)


def _prune_stale_entries(con: sqlite3.Connection, taps: list[str],
                         live: set[tuple[str, str]]) -> int:
    """Drop rows in ``taps`` for entries the catalog no longer has.

    Whole-tap deletion used to do this for free: a changed tap was emptied and
    rebuilt, so an entry deleted upstream simply never came back. Reuse keeps
    the rows instead, which means a file removed from a registry would answer
    queries forever — the same silent-stale-row failure `_delete_taps`'s
    `removed_taps` sweep exists to prevent, one level down.
    """
    stale = [(tap, path) for tap in taps
             for (path,) in con.execute(
                 "SELECT DISTINCT path FROM chunks WHERE tap = ?", (tap,))
             if (tap, path) not in live]
    return _delete_entries(con, stale)


def _split_by_digest(con: sqlite3.Connection,
                     entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Partition ``entries`` into ``(to_embed, already_stored)``.

    An entry is already stored when the store holds chunks for its
    ``(tap, path)`` **and every one of them** carries its current content
    digest. Every one, not any: a partially-written entry — an interrupted
    build, or one whose digest changed mid-run — would otherwise be reused
    with a mixture of two versions' vectors, which is worse than re-embedding
    because nothing later notices.

    An entry with no digest is never reused. `catalog._content_digest` stamps
    them at scan time, but a cache written before ``CACHE_FORMAT`` has none,
    and CLAUDE.md's rule is explicit: consumers degrade cleanly when ``content``
    is absent and **must never treat two absences as a match**. Two entries
    with no digest are not the same entry; they are two unknowns.
    """
    # Nothing to decide, and the early return is the common case rather than a
    # guard: on a build where no tap moved, `candidates` is empty, and without
    # this the store gets scanned end to end to answer a question nobody asked.
    if not entries:
        return [], []
    # Scoped to the taps actually in play, via the `chunks_tap` index. Reading
    # the whole table instead measured 3.75 s cold (0.17 s warm) against 0.08 s
    # for the nineteen largest taps and under 0.01 s for nineteen typical ones,
    # on a real 657,587-chunk store. The full read was also the wrong shape: it
    # grows with the store while the work grows with the drift.
    stored: dict[tuple[str, str], set] = {}
    for tap in sorted({e["tap"] for e in entries}):
        for path, digest in con.execute(
                "SELECT path, digest FROM chunks WHERE tap = ?", (tap,)):
            stored.setdefault((tap, path), set()).add(digest)
    to_embed, kept = [], []
    for e in entries:
        digest = e.get("content")
        have = stored.get(entry_key(e))
        if digest and have == {digest}:
            kept.append(e)
        else:
            to_embed.append(e)
    return to_embed, kept


def _delete_taps(con: sqlite3.Connection, taps: list[str]) -> None:
    """Drop every chunk row belonging to these taps, and their vectors."""
    for tap in taps:
        _delete_matching(con, "tap = ?", (tap,))


def _embed_and_store(con: sqlite3.Connection, entries: list[dict],
                     tap_paths: dict[str, Path] | None,
                     on_progress=None) -> tuple[int, set]:
    """Embed every chunk of ``entries``; returns ``(added, failed_taps)``.

    A batch the provider rejects (rate limit, quota, oversized input) yields no
    vectors. Its taps are reported back rather than silently dropped, so the
    caller can avoid recording a commit for a tap that stored nothing.
    """
    mod = _load()
    if mod is None:          # [rag] extra absent — nothing to serialize into
        # Report every tap as failed so the caller records no commits: marking
        # them built with zero vectors stored is what leaves the store
        # permanently empty. (callers fall back to BM25; see module docstring)
        return 0, {e["tap"] for e in entries}
    rows: list[tuple[dict, int, str]] = []   # (entry, chunk_ix, text)
    for e in entries:
        for ci, text in enumerate(_chunk_texts(e, tap_paths)):
            rows.append((e, ci, text))

    # Embed each DISTINCT text once. Registries mirror each other, so one text
    # arrives many times in a single build: 42.9% of 750,416 chunks on a real
    # 460-tap install are repeats, worst case 1,464 identical copies. The
    # provider is deterministic, so the copies were being bought at full price
    # for a byte-identical vector — and `retrieve_any` runs `dedupe_by_content`
    # on every retrieval path, so they were discarded before reaching a result
    # slot. Insertion below is still per row, because `chunks.tap` is what
    # scopes tap deletion and collapsing rows would strand a tap's vectors.
    order: list[str] = []
    seen: set[str] = set()
    for _e, _ci, text in rows:
        if text not in seen:
            seen.add(text)
            order.append(text)

    vec_of: dict[str, object] = {}
    if on_progress is not None:
        # Reported before the first request, so the size of the job is known
        # up front rather than inferred from how long it has already taken.
        on_progress(0, len(order))
    for start in range(0, len(order), _BATCH):
        batch = order[start:start + _BATCH]
        vecs = embed.embed(batch, input_type="document")
        if vecs and len(vecs) == len(batch):
            vec_of.update(zip(batch, vecs, strict=True))
        # else: taps are attributed per row below, not per batch — but the
        # progress count still advances, or a run with a few rejected batches
        # would appear to stall.
        if on_progress is not None:
            on_progress(min(start + _BATCH, len(order)), len(order))

    added = 0
    failed_taps: set = set()
    # Durability, not speed. Every row used to land in one transaction that
    # committed only after the last one, so interrupting a three-hour build —
    # or losing the machine to a sleep or an OOM — threw away every vector it
    # had paid for. Committing as the rows accumulate keeps the work, and
    # re-running is still correct because `_delete_taps` has already removed
    # each changed tap's old rows, so a partial store is replaced rather than
    # doubled.
    since_commit = 0
    for e, ci, text in rows:
        vec = vec_of.get(text)
        if vec is None:
            # Every tap owning a copy of a text the provider rejected, not just
            # whichever copy happened to sit in the failed batch.
            failed_taps.add(e["tap"])
            continue
        cur = con.execute(
            "INSERT INTO chunks (name, tap, path, kind, cix, snip, digest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (e["name"], e["tap"], e["skill_md"],
             e.get("kind", "skill"), ci, text[:200].strip(),
             # None where the catalog has no digest, which `_split_by_digest`
             # then refuses to reuse — the honest answer for a cache written
             # before CACHE_FORMAT stamped one.
             e.get("content")))
        _store_vector(con, cur.lastrowid, mod.serialize_float32(vec))
        added += 1
        since_commit += 1
        if since_commit >= _COMMIT_EVERY:
            con.commit()
            since_commit = 0
    con.commit()
    return added, failed_taps


def quantize() -> dict | None:
    """Convert an existing float32 store to the two-stage layout, in place.

    Offline and free: it re-reads vectors the user already paid to embed and
    re-encodes them locally. No provider is called, no text is re-chunked, and
    nothing is lost — `vec_raw` receives the *same* float32 blobs `vec_chunks`
    held, so dropping `vec_chunks` relocates the data rather than discarding it.

    It costs disk, in two ways worth stating plainly. While it runs the copy
    sits beside the original, so the file grows to roughly twice the store
    before the ``DROP`` and ``VACUUM``. And it does not come all the way back:
    an ordinary table pays overflow-page overhead on 4 KB blobs that vec0's
    packed storage does not, so `vec_raw` lands ~12% larger than the
    `vec_chunks` it replaces, and the binary index adds its own 114 MB.
    Measured end to end on a real 750,416-chunk store: **3.40 GB -> 3.87 GB**,
    a 14% permanent increase, in 1360 s. That is the price of the 19-27x query
    speedup, and it is a trade rather than a free win.

    Returns None when there is nothing to do (no store, no backend, a
    non-quantizable width, or a store already converted).
    """
    if not db_path().exists():
        return None
    con = _connect()
    if con is None:
        return None
    try:
        meta = _read_meta(con)
        dim = meta.get("dim")
        if not isinstance(dim, int) or not _quantizable(dim):
            return None
        if quantized(con) or not _has_table(con, "vec_chunks"):
            return None
        before = _chunk_total(con, {}, exact=True)[0] or 0
        _ensure_schema(con, dim)
        con.execute("INSERT INTO vec_raw (id, embedding) "
                    "SELECT rowid, embedding FROM vec_chunks")
        con.execute("INSERT INTO vec_chunks_bin (rowid, embedding) "
                    "SELECT rowid, vec_quantize_binary(vec_f32(embedding)) "
                    "FROM vec_chunks")
        moved = con.execute("SELECT COUNT(*) FROM vec_raw").fetchone()[0]
        # Verify before destroying. A short copy means the drop below would be
        # the one step in this function that loses vectors, and re-embedding
        # 750,416 chunks is a bill, not an inconvenience.
        if moved != before:
            con.rollback()
            raise BoostError(
                "quantize copied %d of %d vectors — store left unchanged"
                % (moved, before),
                hint="rebuild instead: `boost reindex --dense --force`")
        con.execute("DROP TABLE IF EXISTS vec_chunks")
        _write_meta(con, {"chunks": before})
        con.commit()
    finally:
        con.close()
    # Outside the transaction: VACUUM cannot run inside one, and without it the
    # freed float32 pages stay allocated to the file.
    con2 = _connect()
    if con2 is not None:
        try:
            con2.execute("VACUUM")
        except sqlite3.DatabaseError:
            pass            # a bigger file is a cosmetic loss, not a failure
        finally:
            con2.close()
    return {"chunks": before, "bytes": db_path().stat().st_size}


def _knn(con: sqlite3.Connection, qblob: bytes,
         pool: int) -> list[tuple[int, float, bytes]]:
    """``(chunk_id, cosine_distance, vector_key)`` for the nearest chunks.

    ``vector_key`` identifies the *embedding*, not the row: byte-identical
    vectors share one key, which is what :data:`MAX_PER_VECTOR` caps on.

    Two-stage on a quantized store, one stage on a legacy one, and the answer
    is the same either way — which is the whole point. `vec0` has no ANN index,
    so a float32 `MATCH` computes a distance against every vector in the store:
    on a real 750,416-chunk / 1024-d install that is 3.08 GB read and 28.2 s of
    arithmetic **per query**, and it was ~85% of a 33.9 s `boost search`.

    Binary quantization makes the same comparison 32x smaller — one bit per
    dimension, 128 bytes instead of 4096, 114 MB instead of 3.08 GB — and
    Hamming distance over it is a popcount. That pass alone takes 0.70 s, but
    it is an *approximation*: measured against a full float32 scan it recovers
    only 0.667 of the true top 60, which is a quality regression no amount of
    speed pays for.

    So it is a filter, not an answer. The 2048 nearest binary candidates are
    re-ranked on their exact float32 vectors, which restores the true ordering
    — measured recall@60 of **1.000**, the same rows in the same order — for
    0.35 s more. Together: 28.2 s -> 1.05 s, 27x, with identical results.
    """
    if quantized(con):
        cand = [r[0] for r in con.execute(
            "SELECT rowid FROM vec_chunks_bin "
            "WHERE embedding MATCH vec_quantize_binary(vec_f32(?)) "
            "ORDER BY distance LIMIT ?", (qblob, max(pool, RESCORE_POOL)))]
        if not cand:
            return []
        # Exact cosine over the candidates only. `vec_raw` is an ordinary
        # rowid-keyed table precisely so this `IN` is an index lookup; the same
        # clause against a vec0 table plans as a full scan (see _ensure_schema).
        #
        # The embedding comes back too, and it is not waste: hashing it is what
        # lets `retrieve` tell "60 entries that each matched something" from
        # "60 copies of one paragraph". The bytes were already read to compute
        # the distance, so the only new cost is one sha256 per candidate.
        # No LIMIT, and that is the point: sqlite computes a distance for all
        # `cand` rows either way — a LIMIT only truncates what it hands back.
        # Truncating here is what let one cluster own the pool. The largest on
        # a real store is 1,464 copies of one pasted paragraph, so a 480-row
        # cut was 480 copies of it and the page had nothing else to rank.
        rows = con.execute(
            "SELECT id, vec_distance_cosine(embedding, ?) AS d, embedding "  # noqa: S608  interpolates only `?` placeholders
            "FROM vec_raw WHERE id IN (%s) ORDER BY d"
            % ",".join("?" * len(cand)), (qblob, *cand)).fetchall()
        # Thin to `pool` while letting no single embedding take more than
        # MAX_PER_VECTOR of it. Rows arrive sorted, so the copies that survive
        # are the nearest ones and the slots freed go to the next *distinct*
        # vector rather than to the next copy of this one.
        out: list[tuple[int, float, bytes]] = []
        per: dict[bytes, int] = {}
        for rid, dist, blob in rows:
            if len(out) >= pool:
                break
            vkey = hashlib.sha256(blob).digest()[:16]
            if per.get(vkey, 0) >= MAX_PER_VECTOR:
                continue
            per[vkey] = per.get(vkey, 0) + 1
            out.append((rid, dist, vkey))
        return out
    # Legacy float32 layout: one row per chunk with no separate blob table, so
    # there is nothing cheap to hash. Each row becomes its own group, which
    # makes the cap a no-op — correct rather than clever, because this path
    # exists for widths `bit[N]` cannot take and no real store is on it.
    return [(rid, dist, b"%d" % rid) for rid, dist in con.execute(
        "SELECT rowid, distance FROM vec_chunks "
        "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (qblob, pool)).fetchall()]


def retrieve(query: str, k: int = 60, kind: str | None = None,
             entries: list[dict] | None = None) -> list[Hit] | None:
    """Top-k dense hits for ``query``, or None to signal 'fall back to BM25'."""
    if not ready():
        return None
    qv = embed.embed([query], input_type="query")
    if not qv:
        return None
    mod = _load()
    con = _connect()
    if con is None or mod is None:
        return None
    try:
        pool = max(k * _POOL, 200)
        try:
            knn = _knn(con, mod.serialize_float32(qv[0]), pool)
        except sqlite3.OperationalError:
            # Some sqlite3/sqlite-vec combinations (observed on Windows)
            # reject this exact query shape ("a LIMIT or 'k = ?' constraint
            # is required") despite the bound LIMIT above — dense retrieval
            # is genuinely unusable here, so fall back to BM25 rather than
            # crash the search command.
            return None
        if not knn:
            return []
        by_id = {r[0]: (r[1], r[2], r[3], r[4]) for r in con.execute(
            "SELECT id, tap, path, kind, snip FROM chunks WHERE id IN (%s)"  # noqa: S608  interpolates only `?` placeholders; ids are bound params
            % ",".join("?" * len(knn)), [rid for rid, _d, _v in knn])}
    finally:
        con.close()

    entries = catalog.all_entries() if entries is None else entries
    live = {entry_key(e): e for e in entries}
    best: dict[tuple[str, str], tuple[float, str]] = {}
    # Which embedding won each entry its score. An entry that also matched on
    # a chunk of its own keeps *that* pairing, because `best` only records the
    # winner — so capping below never costs an entry a hit it earned itself.
    won_by: dict[tuple[str, str], bytes] = {}
    for rid, dist, vkey in knn:
        meta = by_id.get(rid)
        if meta is None:
            continue
        tap, path, ckind, snip = meta
        if kind is not None and ckind != kind:
            continue
        key = (tap, path)
        if key not in live:
            continue
        score = 1.0 - dist                       # cosine distance -> similarity
        prev = best.get(key)
        if prev is None or score > prev[0]:
            best[key] = (score, snip)
            won_by[key] = vkey
    # Tie-break on the displayed name (see rag.retrieve for why).
    ranked = sorted(best.items(),
                    key=lambda kv: (-kv[1][0], live[kv[0]]["name"], kv[0]))
    hits: list[Hit] = []
    seen_vec: dict[bytes, int] = {}
    for key, (score, snip) in ranked:
        if len(hits) >= k:
            break
        # The cap, and the reason the sort above is not enough on its own:
        # byte-identical vectors produce a byte-identical distance, so every
        # entry sharing one arrives with the *same* score and the tie-break
        # decides the page alphabetically. Measured on a real store, one
        # 1,464-copy cluster took 60 of 60 slots that way. Skipping past the
        # cap rather than truncating keeps the page full: the freed slots go
        # to the next entries that matched on something else.
        vkey = won_by[key]
        if seen_vec.get(vkey, 0) >= MAX_PER_VECTOR:
            continue
        seen_vec[vkey] = seen_vec.get(vkey, 0) + 1
        hits.append({"entry": live[key], "score": score,
                     "snippet": snip})  # type: ignore[typeddict-item]
    return hits
