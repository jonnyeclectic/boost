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
import json
import sqlite3
from pathlib import Path

from ..errors import BoostError
from . import catalog, embed, paths
from .rag import Hit, chunk, entry_key, read_body

INDEX_VERSION = 2
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


def _ensure_schema(con: sqlite3.Connection, dim: int) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER, snip TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS chunks_tap ON chunks(tap)")
    con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING "
        "vec0(embedding float[%d] distance_metric=cosine)" % dim)


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


def _chunk_texts(entry: dict, tap_paths: dict[str, Path] | None
                 ) -> list[str]:
    body = read_body(entry, tap_paths)
    return chunk(body) or [body]


def _recorded_meta() -> dict:
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
        try:
            meta["_chunks"] = con.execute(
                "SELECT COUNT(*) FROM chunks").fetchone()[0]
        except sqlite3.DatabaseError:
            meta["_chunks"] = 0
        return meta
    except sqlite3.DatabaseError:
        # A truncated or non-sqlite file: report "no store", never raise into
        # a health check whose whole job is to survive a broken install.
        return {}
    finally:
        con.close()


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
        if env and status.get("chunks"):
            return ("set the key it was built with: `export %s=...` — "
                    "reinstalling the extra swaps in the local model and "
                    "forces all %s vectors to be re-embedded"
                    % (env, "{:,}".format(int(status["chunks"]))))
    return _FIX.get(reason, "see `boost reindex --dense`")


def status() -> dict:
    """Why dense retrieval is, or is not, serving queries.

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
    meta = _recorded_meta()
    b_prov = meta.get("provider")
    b_mdl = meta.get("model")
    b_dim = meta.get("dim")
    b_ver = meta.get("version")
    commits = meta.get("commits")
    chunks = int(meta.get("_chunks") or 0)
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
    elif chunks <= 0:
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
        "taps": len(commits) if isinstance(commits, dict) else 0,
        "ready": reason is None,
        "reason": reason,
        "degraded": degraded,
    }


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
        # Model, not just provider+dim: two models from one provider can share
        # a dimension and still be different embedding spaces (voyage-3 and
        # voyage-4 are both 1024-d), so serving stale vectors would silently
        # mix spaces rather than fail loudly.
        if meta.get("model") != embed.model():
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


def build(entries: list[dict] | None = None,
          force: bool = False) -> dict | None:
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

        fresh = [e for e in entries
                 if e["tap"].replace("/", "__") not in reused]
        changed_taps = sorted({e["tap"] for e in fresh})
        # Prune taps that are gone entirely, not only the ones that changed.
        # `boost untap` removes a tap's entries, so it can never appear in
        # `fresh` and its vectors survived every later incremental build —
        # crowding the KNN pool on every query with rows `retrieve` then
        # discards for not being live, which is how a dense search quietly
        # returns fewer hits the longer an index has been in use.
        removed_taps = sorted(_indexed_taps(con) - {e["tap"] for e in entries})
        _delete_taps(con, changed_taps + removed_taps)

        added, failed_taps = _embed_and_store(con, fresh, tap_paths)
        # Only record a commit for a tap whose chunks actually landed. Recording
        # one for a tap that stored nothing makes every later non-forced run
        # treat it as already built and skip it — one transient rate limit would
        # otherwise leave the store permanently empty until `--force`.
        failed_safe = {t.replace("/", "__") for t in failed_taps}
        recorded = {safe: c for safe, c in commits.items()
                    if safe not in failed_safe}
        _write_meta(con, {"version": INDEX_VERSION, "provider": prov,
                          "model": mdl, "dim": dim, "commits": recorded})
        con.commit()
        total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {
            "entries": len({entry_key(e) for e in entries}),
            "chunks": total,
            "added": added,
            "taps": len(commits),
            "reindexed": changed_taps,
            "pruned": removed_taps,
            "reused": sorted(reused),
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
            rows = con.execute(
                "SELECT c.name, c.tap, c.path, c.kind, c.cix, c.snip, v.embedding "
                "FROM chunks c JOIN vec_chunks v ON v.rowid = c.id "
                "WHERE c.tap = ? ORDER BY c.id", (tap,)).fetchall()
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
            name, ctap, path, kind, cix, snip, emb = row
            chunks.append({
                "name": name, "tap": ctap, "path": path, "kind": kind,
                "cix": cix, "snip": snip,
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
                "INSERT INTO chunks (name, tap, path, kind, cix, snip) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (c.get("name"), c.get("tap"), c.get("path"), c.get("kind"),
                 c.get("cix"), c.get("snip")))
            blob = base64.b64decode(c["embedding"])
            con.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                        (cur.lastrowid, blob))
        commits = meta.get("commits")
        commits = dict(commits) if isinstance(commits, dict) else {}
        commits[str(shard.get("tap") or "").replace("/", "__")] = commit
        _write_meta(con, {"version": INDEX_VERSION,
                          "provider": shard.get("provider"),
                          "model": shard.get("model"), "dim": dim,
                          "commits": commits})
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


def _delete_taps(con: sqlite3.Connection, taps: list[str]) -> None:
    for tap in taps:
        ids = [r[0] for r in
               con.execute("SELECT id FROM chunks WHERE tap = ?", (tap,))]
        for i in ids:
            con.execute("DELETE FROM vec_chunks WHERE rowid = ?", (i,))
        con.execute("DELETE FROM chunks WHERE tap = ?", (tap,))


def _embed_and_store(con: sqlite3.Connection, entries: list[dict],
                     tap_paths: dict[str, Path] | None
                     ) -> tuple[int, set]:
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
    added = 0
    failed_taps: set = set()
    for start in range(0, len(rows), _BATCH):
        batch = rows[start:start + _BATCH]
        vecs = embed.embed([t for _e, _c, t in batch], input_type="document")
        if not vecs or len(vecs) != len(batch):
            failed_taps.update(e["tap"] for e, _c, _t in batch)
            continue
        for (e, ci, text), vec in zip(batch, vecs, strict=True):
            cur = con.execute(
                "INSERT INTO chunks (name, tap, path, kind, cix, snip) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (e["name"], e["tap"], e["skill_md"],
                 e.get("kind", "skill"), ci, text[:200].strip()))
            con.execute("INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                        (cur.lastrowid, mod.serialize_float32(vec)))
            added += 1
    return added, failed_taps


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
            knn = con.execute(
                "SELECT rowid, distance FROM vec_chunks "
                "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                (mod.serialize_float32(qv[0]), pool)).fetchall()
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
            % ",".join("?" * len(knn)), [rid for rid, _d in knn])}
    finally:
        con.close()

    entries = catalog.all_entries() if entries is None else entries
    live = {entry_key(e): e for e in entries}
    best: dict[tuple[str, str], tuple[float, str]] = {}
    for rid, dist in knn:
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
    # Tie-break on the displayed name (see rag.retrieve for why).
    ranked = sorted(best.items(),
                    key=lambda kv: (-kv[1][0], live[kv[0]]["name"], kv[0]))
    hits: list[Hit] = [
        {"entry": live[key], "score": score,
         "snippet": snip}  # type: ignore[typeddict-item]
        for key, (score, snip) in ranked[:k]]
    return hits
