# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Reuse is decided per ENTRY, not per tap — a moved commit is not a changed skill.

Dense reuse was keyed on a tap's git commit alone, and `_delete_taps` is
``DELETE FROM chunks WHERE tap = ?``, so anything below tap granularity was
redone from scratch. A tap's commit moving says *something* in that clone
changed. It does not say anything boost indexes did.

Measured on a real 464-tap / 63,003-entry / 657,587-chunk install:

- 19 taps drifted in 6.85 h — 4.1% of taps, but **17.0% of chunks**, costing
  61-68 min against a 5 h 28 m cold build.
- Those 19 held 967 changed files, of which **39** map to an indexed entry
  owning **659** chunks. Boost re-embedded **112,081** — **170x** the change.
- **10 of the 19 changed nothing boost indexes at all** (badge JSON,
  star-history SVGs, CI YAML, e2e TypeScript) and cost **44,866 chunks =
  40.0%** of the incremental bill. `davila7/claude-code-templates` re-embedded
  all 18,566 of its chunks over four dashboard JSON files.

The fix needs no new identity machinery. `catalog._content_digest` already
stamps each entry with a hash of exactly what `rag.read_body` assembles, and
`tests/unit/test_content_identity.py` pins that parity byte-for-byte — so an
entry whose stored digest matches its catalog digest is one whose embedded text
is unchanged.

What must NOT regress, and each has a test below: an entry deleted upstream has
to stop answering queries (whole-tap deletion used to sweep it for free), a
changed entry has to be replaced rather than doubled, and an entry with no
digest must never be reused — two absences are not a match.
"""
from __future__ import annotations

import math

import pytest

from boost_cli.core import dense, embed, rag

TAP = "acme/skills"


def _toy_embed(texts, input_type=None, timeout=60):
    """8-d so `_quantizable` holds, deterministic so reuse is observable."""
    out = []
    for t in texts:
        v = [float(sum(t.encode()[i::8]) % 97) for i in range(8)]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out


def _e(name, body, *, tap=TAP, digest=None):
    """A catalog entry whose `content` is a stand-in for _content_digest.

    The real digest hashes ``name + description + body``; what matters to
    reuse is only that it changes when the body does, so the tests set it
    explicitly and a test that means to omit it passes ``digest=""``.
    """
    entry = {"name": name, "tap": tap, "kind": "skill",
             "skill_md": "skills/%s/SKILL.md" % name, "_body": body}
    if digest is None:
        digest = "d-%s" % abs(hash(body))
    if digest:
        entry["content"] = digest
    return entry


class _Recorder(list):
    """The recorded embed calls, plus a handle on the tap's current commit.

    A plain ``list`` cannot carry an attribute (no ``__dict__``), so the
    fixture needs a real type — and the tests treat the value as a list
    (``clear()``, iteration through ``_flat``), so a subclass keeps every call
    site unchanged.
    """

    commit: dict


@pytest.fixture()
def counting_env(sandbox, monkeypatch):
    """dense wired to a toy embedder that records every text it is asked for."""
    asked = _Recorder()
    commit = {"v": "c1"}

    def recording(texts, input_type=None, timeout=60):
        asked.append(list(texts))
        return _toy_embed(texts, input_type, timeout)

    monkeypatch.setattr(embed, "embed", recording)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {TAP: "/x"})
    monkeypatch.setattr(rag, "_tap_commits",
                        lambda: {TAP.replace("/", "__"): commit["v"]})
    monkeypatch.setattr(dense, "read_body",
                        lambda e, tp=None: e.get("_body", ""))
    asked.commit = commit
    return asked


def _flat(asked):
    return [t for batch in asked for t in batch]


def _build(entries):
    res = dense.build(entries)
    if res is None:
        pytest.skip("sqlite-vec backend unavailable")
    return res


def _move_commit(env, to):
    """Advance the tap's commit — what makes the tap look changed."""
    env.commit["v"] = to


def _chunk_paths(con):
    return sorted(r[0] for r in con.execute("SELECT path FROM chunks"))


class TestAMovedCommitIsNotAChangedSkill:
    """The 40% case: ten of nineteen drifted taps changed nothing indexed."""

    def test_identical_content_costs_no_embeddings(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two"), _e("gamma", "three")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build(entries)
        assert _flat(counting_env) == [], (
            "a moved commit re-embedded content that had not changed")

    def test_the_stats_say_what_was_reused(self, counting_env):
        # `reused` is tap-level and reports [] here — the tap DID move. Without
        # a separate counter the reply would say "reindexed everything" while
        # embedding nothing, which is the confusing half of the old behaviour.
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build(entries)
        assert res["reused_entries"] == 2
        assert res["embedded_entries"] == 0
        assert res["reindexed"] == [TAP]      # the tap genuinely moved

    def test_the_chunk_total_does_not_drift(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        first = _build(entries)
        _move_commit(counting_env, "c2")
        again = _build(entries)
        assert again["chunks"] == first["chunks"]


class TestOnlyTheChangedEntryIsReEmbedded:
    """The 170x case: 659 chunks of real change cost 112,081 re-embeds."""

    def test_one_changed_body_embeds_one_entry(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two"), _e("gamma", "three")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        changed = [entries[0], _e("beta", "two REWRITTEN"), entries[2]]
        res = _build(changed)
        assert _flat(counting_env) == ["two REWRITTEN"]
        assert res["embedded_entries"] == 1
        assert res["reused_entries"] == 2

    def test_the_changed_entry_is_replaced_not_doubled(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build([entries[0], _e("beta", "two REWRITTEN")])
        con = dense._connect()
        rows = list(con.execute(
            "SELECT COUNT(*) FROM chunks WHERE name = 'beta'"))
        con.close()
        assert rows[0][0] == 1, "the old vectors survived alongside the new"
        assert res["chunks"] == 2

    def test_the_new_digest_is_what_gets_stored(self, counting_env):
        # Storing the old digest would reuse stale vectors forever — the
        # failure mode that looks right and is invisible.
        entries = [_e("alpha", "one")]
        _build(entries)
        _move_commit(counting_env, "c2")
        rewritten = _e("alpha", "one REWRITTEN")
        _build([rewritten])
        con = dense._connect()
        stored = {r[0] for r in con.execute(
            "SELECT digest FROM chunks WHERE name = 'alpha'")}
        con.close()
        assert stored == {rewritten["content"]}

    def test_a_second_rebuild_after_a_change_reuses_again(self, counting_env):
        # Proves the new digest was actually persisted, not merely computed.
        entries = [_e("alpha", "one")]
        _build(entries)
        _move_commit(counting_env, "c2")
        rewritten = [_e("alpha", "one REWRITTEN")]
        _build(rewritten)
        counting_env.clear()
        _move_commit(counting_env, "c3")
        _build(rewritten)
        assert _flat(counting_env) == []


class TestNothingStaleSurvivesReuse:
    """Whole-tap deletion swept deleted entries for free. Reuse must not lose that."""

    def test_an_entry_deleted_upstream_stops_answering(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two"), _e("gamma", "three")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build([entries[0], entries[2]])
        con = dense._connect()
        paths = _chunk_paths(con)
        con.close()
        assert paths == ["skills/alpha/SKILL.md", "skills/gamma/SKILL.md"]
        assert res["chunks"] == 2

    def test_pruning_a_deleted_entry_costs_no_embeddings(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build([entries[0]])
        assert _flat(counting_env) == []

    def test_a_whole_tap_going_away_still_prunes(self, counting_env):
        # The tap-level sweep this sits under must keep working.
        entries = [_e("alpha", "one")]
        _build(entries)
        _move_commit(counting_env, "c2")
        res = _build([_e("alpha", "one", tap="other/skills")])
        assert TAP in res["pruned"]


class TestAMissingDigestIsNeverAMatch:
    """CLAUDE.md: consumers degrade cleanly when `content` is absent, and must
    never treat two absences as a match. Two unknowns are not one thing."""

    def test_an_entry_without_a_digest_is_re_embedded(self, counting_env):
        entries = [_e("alpha", "one", digest="")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build(entries)
        assert _flat(counting_env) == ["one"], (
            "an entry with no digest was reused — two absences matched")

    def test_it_does_not_poison_its_neighbours(self, counting_env):
        entries = [_e("alpha", "one", digest=""), _e("beta", "two")]
        _build(entries)
        counting_env.clear()
        _move_commit(counting_env, "c2")
        _build(entries)
        assert _flat(counting_env) == ["one"]


class TestTheStoreFormatMovedWithIt:
    def test_index_version_was_bumped(self):
        # A v2 store has no `digest` column and `_ensure_schema` cannot add one
        # (CREATE TABLE IF NOT EXISTS), so the version bump IS the migration —
        # `build` wipes on a version change. Pinned because forgetting it makes
        # every existing store fail its next build on "no column named digest".
        assert dense.INDEX_VERSION >= 3

    def test_the_schema_carries_the_digest(self, sandbox):
        con = dense._connect()
        if con is None:
            pytest.skip("sqlite-vec backend unavailable")
        dense._ensure_schema(con, 8)
        cols = {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
        con.close()
        assert "digest" in cols

    def test_a_shard_carries_the_digest_too(self, counting_env):
        # Without this an imported shard's entries have no digest, so the very
        # next build re-embeds them — paying in CPU exactly what downloading
        # the shard was meant to save.
        _build([_e("alpha", "one")])
        shard = dense.export_shard(TAP)
        assert shard["chunks"], "nothing exported"
        assert all("digest" in c for c in shard["chunks"])
        assert any(c["digest"] for c in shard["chunks"])


class TestTheReplySaysWhatThisRunActuallyDid:
    """`chunks` is the store total, not this run's work.

    "embedded 657,587 passages" on an incremental run described an afternoon of
    CPU that did not happen — the number is every vector in the store, and an
    incremental run may have embedded none of them. The fix is to report
    `added`, and to name the entry-level saving that the tap-level `reused`
    line structurally cannot: a tap appears in `reindexed` the moment its
    commit moves, so a run that reused every entry inside three moved taps
    otherwise reads as three taps fully re-embedded.
    """

    def test_added_counts_this_run_not_the_store(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        first = _build(entries)
        assert first["added"] == 2
        _move_commit(counting_env, "c2")
        again = _build(entries)
        assert again["added"] == 0, "reported work that did not happen"
        assert again["chunks"] == 2, "the store total is still the total"

    def test_the_command_reports_added_rather_than_the_total(self):
        # Pinned as source because the emitter needs a TTY and a spinner to
        # exercise; what must not come back is `chunks` in the success line.
        import inspect

        from boost_cli.commands import discovery
        src = inspect.getsource(discovery.cmd_reindex)
        line = [ln for ln in src.splitlines()
                if "into the dense vector store" in ln or "the dense store holds" in ln]
        assert line, "the dense success line moved — re-point this test"
        assert "added" in src.split("the dense store holds")[0][-400:], (
            "the success line reports the store total as if it were this "
            "run's work")


class TestVectorsAndChunksStayInStep:
    """The failure reuse could introduce that no count would reveal.

    Entry-level deletion removes *some* rows from a tap rather than all of
    them, which is a shape `_drop_vectors` never saw before. If it missed one,
    the store would carry a vector whose chunk is gone — an orphan that
    `retrieve` still ranks, and which no chunk total would show, because the
    chunk side is correct. The reverse is worse: a chunk with no vector is a
    row the KNN can never return, so the entry silently stops being findable.

    This used to be a two-way ``chunks.id`` <-> ``vec_raw.id`` bijection, and
    that is the wrong shape now: one vector may back many chunks by design, so
    half of it would fail on every store that saves anything. It is REWRITTEN
    rather than relaxed, because the invariant it protected is still real —
    only its arithmetic changed. Both directions survive as counts of zero:

    * every ``chunks.vid`` resolves to a vector that exists, and
    * every stored vector has at least one chunk naming it.
    """

    def _unresolved(self, con) -> int:
        return con.execute(
            "SELECT COUNT(*) FROM chunks c WHERE NOT EXISTS "
            "(SELECT 1 FROM vec_raw v WHERE v.id = c.vid)").fetchone()[0]

    def _orphans(self, con) -> int:
        return con.execute(
            "SELECT COUNT(*) FROM vec_raw v WHERE NOT EXISTS "
            "(SELECT 1 FROM chunks c WHERE c.vid = v.id)").fetchone()[0]

    def test_a_changed_entry_leaves_no_orphan_vector(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        _move_commit(counting_env, "c2")
        _build([entries[0], _e("beta", "two REWRITTEN")])
        con = dense._connect()
        try:
            assert self._orphans(con) == 0, "a vector outlived every chunk"
            assert self._unresolved(con) == 0, \
                "a chunk has no vector and can never rank"
        finally:
            con.close()

    def test_a_deleted_entry_leaves_no_orphan_vector(self, counting_env):
        entries = [_e("alpha", "one"), _e("beta", "two"), _e("gamma", "three")]
        _build(entries)
        _move_commit(counting_env, "c2")
        _build([entries[0], entries[2]])
        con = dense._connect()
        try:
            assert self._orphans(con) == 0
            assert self._unresolved(con) == 0
        finally:
            con.close()

    def test_a_shared_vector_survives_losing_one_of_its_chunks(self,
                                                              counting_env):
        """The half of the bijection dedup breaks, asserted from the other side.

        Two entries with the same body share one vector row. Deleting one must
        leave the row standing — the refcount is derived from `chunks`, so a
        sweep that dropped it would take the surviving entry's vector with it
        and that entry would stop being findable with nothing reporting why.
        """
        entries = [_e("alpha", "shared"), _e("beta", "shared")]
        _build(entries)
        con = dense._connect()
        try:
            assert con.execute(
                "SELECT COUNT(*) FROM vec_raw").fetchone()[0] == 1
        finally:
            con.close()
        _move_commit(counting_env, "c2")
        _build([entries[0]])
        con = dense._connect()
        try:
            assert con.execute(
                "SELECT COUNT(*) FROM vec_raw").fetchone()[0] == 1
            assert self._unresolved(con) == 0
            assert self._orphans(con) == 0
        finally:
            con.close()

    def test_the_last_referent_going_takes_the_vector_with_it(self,
                                                              counting_env):
        entries = [_e("alpha", "shared"), _e("beta", "shared")]
        _build(entries)
        _move_commit(counting_env, "c2")
        _build([])
        con = dense._connect()
        try:
            assert con.execute(
                "SELECT COUNT(*) FROM vec_raw").fetchone()[0] == 0
            assert con.execute(
                "SELECT COUNT(*) FROM vectors").fetchone()[0] == 0
        finally:
            con.close()

    def test_a_replaced_entry_does_not_inherit_the_old_rowid(self, counting_env):
        # `chunks.id` is AUTOINCREMENT, which never reuses a rowid. If it ever
        # became a plain INTEGER PRIMARY KEY, a re-inserted chunk could land on
        # a freed rowid and join a stale vector — right-looking, and wrong.
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        con = dense._connect()
        before = dict(con.execute("SELECT name, id FROM chunks"))
        con.close()
        _move_commit(counting_env, "c2")
        _build([entries[0], _e("beta", "two REWRITTEN")])
        con = dense._connect()
        after = dict(con.execute("SELECT name, id FROM chunks"))
        con.close()
        assert after["alpha"] == before["alpha"], "an untouched entry moved"
        assert after["beta"] != before["beta"], "a freed rowid was reused"


class TestReuseDoesNotPayForTheWholeStore:
    """The lookup has to scale with the drift, not with the store.

    The first draft read `SELECT tap, path, digest FROM chunks` — every row —
    to answer a question about a handful of taps. On a real 657,587-chunk store
    that measured 3.75 s cold (0.17 s warm) against 0.08 s for the nineteen
    largest taps scoped through the `chunks_tap` index. Worse, it ran on the
    build where nothing had changed at all: `candidates` is empty there, so the
    whole store was scanned to answer a question nobody asked, and that is the
    most common build there is.
    """

    def test_an_unchanged_build_hands_the_digest_pass_nothing(
            self, counting_env, monkeypatch):
        """Where the whole-table read hurt most: the build with no work in it.

        Tap-level reuse already skips every tap, so `candidates` is empty. The
        old query still read all 657,587 rows to answer a question nobody had
        asked — on the most common build there is.
        """
        entries = [_e("alpha", "one"), _e("beta", "two")]
        _build(entries)
        from boost_cli.core import dense as d

        real = d._split_by_digest
        seen = {}

        def spy(con, ents):
            seen["n"] = len(ents)
            return real(con, ents)

        monkeypatch.setattr(d, "_split_by_digest", spy)
        res = _build(entries)          # same commit -> tap-level reuse
        assert res["reused"], "expected tap-level reuse to have fired"
        assert seen["n"] == 0, "the digest pass was handed work to do"

    def test_the_digest_lookup_is_scoped_by_tap(self):
        """Pinned as query SHAPE, deliberately.

        A row-count assertion would depend on the fixture's size and pass for
        the wrong reason as soon as that changed; the defect here was the query
        reading the whole table, so the query is the thing to pin.
        """
        import inspect

        src = inspect.getsource(dense._split_by_digest)
        assert "FROM chunks WHERE tap = ?" in src, (
            "the digest lookup must go through the chunks_tap index")
        assert "SELECT tap, path, digest FROM chunks" not in src, (
            "the whole-table read is back — it grows with the store while the "
            "work grows with the drift")

    def test_an_empty_candidate_list_returns_two_empty_lists(self, sandbox):
        # The early return is behaviour, not an optimisation detail: callers
        # unpack two lists and `kept` feeds `reused_entries`.
        con = dense._connect()
        if con is None:
            pytest.skip("sqlite-vec backend unavailable")
        try:
            fresh, kept = dense._split_by_digest(con, [])
        finally:
            con.close()
        assert (fresh, kept) == ([], [])


class TestTheStandInSchemaMatchesTheReal:
    """`test_dense_fallback` replaces `_ensure_schema` with a hand-written one.

    It does that for a good reason — the real one creates a `vec0` virtual
    table, which needs an extension those tests deliberately run without. But
    the `chunks` shape in the stand-in is a COPY, and a copy drifts: adding
    `digest` to the real schema left the stand-in building the previous version
    while its `meta` still claimed to be the current one, so `build()` skipped
    the wipe and every insert failed with "table chunks has no column named
    digest". Eight tests, on every platform.

    Pinning the column set here is what makes the next column addition fail in
    one obvious place instead of eight confusing ones — the same trick
    `test_gitutil_sparse.py` uses to hold `gitutil`'s patterns against
    `catalog`'s.
    """

    @staticmethod
    def _columns(sql_runner) -> set:
        import sqlite3
        con = sqlite3.connect(":memory:")
        try:
            sql_runner(con)
            return {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
        finally:
            con.close()

    # Every module holding a hand-written `chunks` schema. Parametrised rather
    # than hard-coded to one, because the second stand-in
    # (`test_dense_vector_dedupe`) drifts exactly as easily as the first did
    # and would fail eight tests away from its cause.
    @pytest.mark.parametrize("module", ["test_dense_fallback",
                                        "test_dense_vector_dedupe"])
    def test_the_stand_in_schemas_have_the_real_columns(self, module):
        import importlib
        import inspect
        import re

        fb = importlib.import_module("tests.unit.%s" % module)

        # The stand-in may be a closure inside a test; read its source rather
        # than exporting it, so the fixture stays where it is used.
        src = inspect.getsource(fb)
        m = re.search(r'CREATE TABLE IF NOT EXISTS chunks \((.*?)\)"\)',
                      src, re.S)
        assert m, "the stand-in schema moved — re-point this test"
        stand_in = {p.strip().split()[0].strip('" ')
                    for p in m.group(1).replace('"', " ").split(",")}
        stand_in = {c for c in stand_in if c and c.isidentifier()}

        real = self._columns(lambda con: con.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " name TEXT, tap TEXT, path TEXT, kind TEXT, cix INTEGER,"
            " snip TEXT, digest TEXT, vid INTEGER)"))
        missing = real - stand_in
        assert not missing, (
            "the hand-written schema in %s is missing %s — it will claim to be "
            "the current INDEX_VERSION while building the previous one"
            % (module, sorted(missing)))

    def test_the_real_schema_is_what_this_test_pins(self, sandbox):
        # The other half: if `_ensure_schema` gains a column, the literal above
        # goes stale too. Compare against the real thing where it can run.
        con = dense._connect()
        if con is None:
            pytest.skip("sqlite-vec backend unavailable")
        try:
            dense._ensure_schema(con, 8)
            cols = {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
            vec = {r[1] for r in con.execute("PRAGMA table_info(vectors)")}
        finally:
            con.close()
        assert {"id", "name", "tap", "path", "kind", "cix", "snip",
                "digest", "vid"} <= cols
        # `vid` without the relation it points into is a dangling column, so
        # the second table is part of the same pin.
        assert {"vid", "hash"} <= vec
