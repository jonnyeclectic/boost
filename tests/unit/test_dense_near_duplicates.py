# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""``dense.collapse_near_duplicates``: the same skill, a different language.

`rag.dedupe_by_content` collapses byte-identical copies and leaves the rest
alone by design — two entries with different bodies must stay separate,
because a shared name can legitimately hide two different rules (#366).
Measured on a real 466-tap install with hybrid RRF serving, that correctness
has a cost: every one of the top ten results for the query ``exa search`` was
``exa-search``, distinguished only by description language — one Japanese, two
Chinese, five English phrasings, plus two more English variants. Every one of
those ten passed byte-identical dedup correctly; the whole page was still one
skill.

This collapses that residual using embeddings already on disk rather than
re-embedding anything: `rag.chunk` packs `rag.read_body`'s prepended
``name\\ndescription`` into chunk 0 of every entry, so chunk 0's stored vector
already carries the language signal a translation changes, and comparing it
against other surviving hits costs one lookup per entry rather than a new
embedding call.

Most of this file never touches the real ``sqlite-vec`` extension: `vec_raw`
is an ordinary rowid-keyed table (dense.py's own design — a vec0 table cannot
answer ``id IN (...)`` without a full scan) and `quantized()` only checks
table *existence*, so a hand-built plain-sqlite3 connection exercises the
real SQL this module runs. ``TestEndToEnd`` is the exception — it goes through
a real `dense.build()` and is skipped where the extension cannot load, mirroring
`test_dense_quantized.py`.
"""
from __future__ import annotations

import array
import math
import sqlite3

import pytest

from boost_cli.core import dense, embed, rag


def _blob(vec: list[float]) -> bytes:
    return array.array("f", vec).tobytes()


def _e(name: str, tap: str = "acme/skills", path: str | None = None,
      curated: bool = False) -> dict:
    return {"name": name, "tap": tap, "kind": "skill",
            "skill_md": path or ("skills/%s/SKILL.md" % name),
            "curated": curated}


def _hit(entry: dict, score: float = 1.0) -> dict:
    return {"entry": entry, "score": score, "snippet": ""}


def _names(hits) -> list:
    return [h["entry"]["name"] for h in hits]


def _store_with(rows: list[tuple[str, str, int, list[float] | None]]
               ) -> sqlite3.Connection:
    """A plain sqlite3 store carrying chunk-0 rows and their raw vectors.

    ``rows`` is ``(tap, path, vid, vector)``; a ``None`` vector inserts the
    chunk row without a matching `vec_raw` row, modelling a store where the
    vector write never landed. `vec_chunks_bin` is created empty — nothing
    here queries its contents, only `quantized()`'s table-existence check.
    """
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT,"
                " path TEXT, cix INTEGER, vid INTEGER)")
    con.execute("CREATE TABLE vec_raw (id INTEGER PRIMARY KEY, embedding BLOB)")
    con.execute("CREATE TABLE vec_chunks_bin (id INTEGER)")
    for tap, path, vid, vec in rows:
        con.execute("INSERT INTO chunks (tap, path, cix, vid) VALUES (?, ?, 0, ?)",
                    (tap, path, vid))
        if vec is not None:
            con.execute("INSERT INTO vec_raw (id, embedding) VALUES (?, ?)",
                        (vid, _blob(vec)))
    con.commit()
    return con


@pytest.fixture()
def wired(monkeypatch):
    """Route `dense.ready`/`dense._connect` at a hand-built store — no
    sqlite-vec extension involved. Set ``box["con"]`` before calling.
    """
    box: dict = {}
    monkeypatch.setattr(dense, "ready", lambda: True)
    monkeypatch.setattr(dense, "_connect", lambda: box["con"])
    return box


class TestCosine:
    def test_identical_vectors_score_one(self):
        v = array.array("f", [1.0, 2.0, 3.0])
        assert dense._cosine(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        a = array.array("f", [1.0, 0.0])
        b = array.array("f", [0.0, 1.0])
        assert dense._cosine(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_score_negative_one(self):
        a = array.array("f", [1.0, 0.0])
        b = array.array("f", [-1.0, 0.0])
        assert dense._cosine(a, b) == pytest.approx(-1.0)

    def test_a_zero_vector_never_matches(self):
        # Guards the divide-by-zero rather than raising — an all-zero vector
        # is a degenerate input, not grounds to crash a search.
        a = array.array("f", [0.0, 0.0])
        b = array.array("f", [1.0, 1.0])
        assert dense._cosine(a, b) == 0.0


class TestCollapseNearDuplicates:
    """The clustering itself, against a hand-built store (see module docstring)."""

    def test_near_identical_vectors_collapse_to_one(self, wired):
        en = _e("exa-search", tap="acme/skills", path="a/SKILL.md")
        ja = _e("exa-search", tap="mirror/exa", path="b/SKILL.md")
        wired["con"] = _store_with([
            (en["tap"], en["skill_md"], 1, [1.0, 0.0, 0.0, 0.0]),
            (ja["tap"], ja["skill_md"], 2, [0.999, 0.001, 0.0, 0.0]),
        ])
        out = dense.collapse_near_duplicates([_hit(en), _hit(ja)])
        assert len(out) == 1

    def test_the_first_ranked_copy_is_kept_by_default(self, wired):
        # Equal source_rank on both sides (neither curated) — the earlier,
        # better-ranked hit's slot survives, matching `dedupe_by_content`'s
        # tie behaviour for byte-identical copies.
        en = _e("exa-search", tap="acme/skills", path="a/SKILL.md")
        ja = _e("exa-search", tap="mirror/exa", path="b/SKILL.md")
        wired["con"] = _store_with([
            (en["tap"], en["skill_md"], 1, [1.0, 0.0]),
            (ja["tap"], ja["skill_md"], 2, [0.999, 0.001]),
        ])
        out = dense.collapse_near_duplicates([_hit(en), _hit(ja)])
        assert out[0]["entry"] is en

    def test_a_curated_source_wins_the_merge_even_ranked_second(self, wired):
        # Same source_rank preference `dedupe_by_content` applies to
        # byte-identical copies: choosing among near-identical copies is the
        # same question — where should the user install from.
        plain = _e("exa-search", tap="mirror/exa", path="a/SKILL.md", curated=False)
        curated = _e("exa-search", tap="acme/skills", path="b/SKILL.md", curated=True)
        wired["con"] = _store_with([
            (plain["tap"], plain["skill_md"], 1, [1.0, 0.0]),
            (curated["tap"], curated["skill_md"], 2, [0.999, 0.001]),
        ])
        out = dense.collapse_near_duplicates([_hit(plain), _hit(curated)])
        assert len(out) == 1
        assert out[0]["entry"] is curated

    def test_distinct_vectors_both_survive(self, wired):
        a = _e("skill-a", path="a/SKILL.md")
        b = _e("skill-b", path="b/SKILL.md")
        wired["con"] = _store_with([
            (a["tap"], a["skill_md"], 1, [1.0, 0.0]),
            (b["tap"], b["skill_md"], 2, [0.0, 1.0]),
        ])
        out = dense.collapse_near_duplicates([_hit(a), _hit(b)])
        assert _names(out) == ["skill-a", "skill-b"]

    def test_a_chain_collapses_onto_its_first_member(self, wired):
        # Three near-identical copies, best-ranked first: all three merge into
        # one slot, not into a pair plus a singleton.
        a = _e("skill-a", path="a/SKILL.md")
        b = _e("skill-a", tap="mirror/one", path="b/SKILL.md")
        c = _e("skill-a", tap="mirror/two", path="c/SKILL.md")
        wired["con"] = _store_with([
            (a["tap"], a["skill_md"], 1, [1.0, 0.0, 0.0]),
            (b["tap"], b["skill_md"], 2, [0.999, 0.001, 0.0]),
            (c["tap"], c["skill_md"], 3, [0.998, 0.0, 0.001]),
        ])
        out = dense.collapse_near_duplicates([_hit(a), _hit(b), _hit(c)])
        assert len(out) == 1

    def test_a_hit_with_no_chunk_row_is_never_merged(self, wired):
        known = _e("skill-a", path="a/SKILL.md")
        unknown = _e("skill-b", path="b/SKILL.md")
        wired["con"] = _store_with([
            (known["tap"], known["skill_md"], 1, [1.0, 0.0]),
        ])  # `unknown` has no chunk-0 row in this store at all
        out = dense.collapse_near_duplicates([_hit(known), _hit(unknown)])
        assert _names(out) == ["skill-a", "skill-b"]

    def test_a_dangling_vid_with_no_vec_raw_row_is_never_merged(self, wired):
        # A chunk row exists but its vector write never landed — two unknowns
        # must not be treated as a match any more than a missing content
        # digest is, per CLAUDE.md.
        a = _e("skill-a", path="a/SKILL.md")
        wired["con"] = _store_with([(a["tap"], a["skill_md"], 1, None)])
        hits = [_hit(a)]
        assert dense.collapse_near_duplicates(hits) == hits

    def test_a_pool_past_the_pair_batch_size_is_still_answered(self, wired):
        # `_opening_vectors` batches its lookups (`dense._PAIR_BATCH`) so a
        # caller's pool never trips SQLite's ~999-bound-parameter ceiling.
        # This exercises more than one batch end to end rather than trusting
        # the batching loop by inspection.
        #
        # One-hot vectors, exactly orthogonal by construction rather than
        # merely unlikely to collide: entry 0's near-duplicate (index 1) sets
        # a small extra component on axis 0, and every other entry owns its
        # own axis outright, so no accidental cosine can cross the threshold.
        n = dense._PAIR_BATCH + 5
        entries = [_e("skill-%03d" % i, path="s%03d/SKILL.md" % i)
                  for i in range(n)]

        def onehot(axis: int, extra: int | None = None) -> list[float]:
            v = [0.0] * n
            v[axis] = 1.0
            if extra is not None:
                v[extra] = 0.05
            return v

        rows = [(e["tap"], e["skill_md"], i + 1,
                onehot(0) if i == 0 else onehot(0, extra=1) if i == 1
                else onehot(i))
               for i, e in enumerate(entries)]
        wired["con"] = _store_with(rows)
        out = dense.collapse_near_duplicates([_hit(e) for e in entries])
        assert len(out) == n - 1

    def test_below_threshold_similarity_does_not_merge(self, wired):
        a = _e("skill-a", path="a/SKILL.md")
        b = _e("skill-b", path="b/SKILL.md")
        wired["con"] = _store_with([
            (a["tap"], a["skill_md"], 1, [1.0, 0.0]),
            (b["tap"], b["skill_md"], 2, [0.9, math.sqrt(1 - 0.9 ** 2)]),
        ])
        out = dense.collapse_near_duplicates([_hit(a), _hit(b)],
                                              threshold=dense.NEAR_DUP_THRESHOLD)
        assert len(out) == 2

    def test_an_explicit_lower_threshold_does_merge_the_same_pair(self, wired):
        a = _e("skill-a", path="a/SKILL.md")
        b = _e("skill-b", path="b/SKILL.md")
        wired["con"] = _store_with([
            (a["tap"], a["skill_md"], 1, [1.0, 0.0]),
            (b["tap"], b["skill_md"], 2, [0.9, math.sqrt(1 - 0.9 ** 2)]),
        ])
        out = dense.collapse_near_duplicates([_hit(a), _hit(b)], threshold=0.8)
        assert len(out) == 1


class TestDegradesToNoOp:
    """Every way the pass can be unavailable must return the hits unchanged."""

    def test_not_ready_never_opens_a_connection(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: False)

        def boom():
            raise AssertionError("must not connect when dense is not ready")

        monkeypatch.setattr(dense, "_connect", boom)
        hits = [_hit(_e("skill-a"))]
        assert dense.collapse_near_duplicates(hits) == hits

    def test_empty_hits_never_opens_a_connection(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)

        def boom():
            raise AssertionError("must not connect for an empty hit list")

        monkeypatch.setattr(dense, "_connect", boom)
        assert dense.collapse_near_duplicates([]) == []

    def test_no_connection_is_a_no_op(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(dense, "_connect", lambda: None)
        hits = [_hit(_e("skill-a"))]
        assert dense.collapse_near_duplicates(hits) == hits

    def test_a_non_quantized_store_is_a_no_op(self, monkeypatch):
        monkeypatch.setattr(dense, "ready", lambda: True)
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT,"
                    " path TEXT, cix INTEGER, vid INTEGER)")
        # No vec_raw / vec_chunks_bin — quantized() is False, so the store is
        # never even queried for chunk-0 rows.
        monkeypatch.setattr(dense, "_connect", lambda: con)
        hits = [_hit(_e("skill-a"))]
        try:
            assert dense.collapse_near_duplicates(hits) == hits
        finally:
            con.close()

    def test_the_connection_is_always_closed(self, monkeypatch):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, tap TEXT,"
                    " path TEXT, cix INTEGER, vid INTEGER)")
        monkeypatch.setattr(dense, "ready", lambda: True)
        monkeypatch.setattr(dense, "_connect", lambda: con)
        dense.collapse_near_duplicates([_hit(_e("skill-a"))])
        with pytest.raises(sqlite3.ProgrammingError):
            con.execute("SELECT 1")


def _vec_loadable() -> bool:
    con = sqlite3.connect(":memory:")
    try:
        import sqlite_vec
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.enable_load_extension(False)
        con.execute("create virtual table t using vec0(embedding bit[8])")
        return True
    except Exception:
        return False
    finally:
        con.close()


def _vec_for(seed: int) -> list[float]:
    v = [math.sin(seed * 1.7 + i * 0.9) for i in range(8)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class TestEndToEnd:
    """The full `dense.build()` pipeline, real `vid`s and real `vec_raw` rows.

    8-d toy vectors, same shape as `test_dense_quantized.py`: `bit[N]`
    requires a multiple of 8, and this is what keeps the quantized path
    exercised. ``exa-search-en``/``-ja``/``-zh`` share one base direction with
    a small per-entry perturbation, standing in for one skill translated
    three ways; ``other-skill`` is orthogonal to it.
    """

    _BASE = _vec_for(0)
    _NAMES = ("exa-search-en", "exa-search-ja", "exa-search-zh", "other-skill")

    @classmethod
    def _vec(cls, name: str) -> list[float]:
        if name == "other-skill":
            return _vec_for(99)
        # A tiny, name-seeded perturbation of the shared base direction —
        # distinct bytes (so byte-identical dedup does not fire) but well
        # inside the near-duplicate threshold once re-normalized.
        seed = sum(name.encode())
        noise = [math.sin(seed * 0.01 + i) * 0.01 for i in range(8)]
        v = [b + n for b, n in zip(cls._BASE, noise, strict=True)]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    @staticmethod
    def _toy_embed(texts, input_type=None, timeout=60):
        out = []
        for t in texts:
            name = t.split("\n", 1)[0].strip()
            out.append(TestEndToEnd._vec(name))
        return out

    @staticmethod
    def _entry(name):
        return {"name": name, "tap": "acme/skills", "kind": "skill",
                "skill_md": "skills/%s/SKILL.md" % name}

    @pytest.fixture()
    def dense_env(self, sandbox, monkeypatch):
        monkeypatch.setattr(embed, "embed", self._toy_embed)
        monkeypatch.setattr(embed, "provider", lambda: "openai")
        monkeypatch.setattr(embed, "model", lambda: "toy-8")
        monkeypatch.setattr(embed, "dimension", lambda: 8)
        monkeypatch.setattr(embed, "available", lambda: True)
        monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
        monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e["name"])
        return monkeypatch

    @pytest.mark.skipif(not _vec_loadable(),
                        reason="sqlite-vec extension not loadable here")
    def test_translations_collapse_the_distinct_skill_survives(self, dense_env):
        entries = [self._entry(n) for n in self._NAMES]
        dense.build(entries=entries, force=True)
        hits = [_hit(e) for e in entries]  # already best-ranked: en, ja, zh, other
        out = dense.collapse_near_duplicates(hits)
        assert _names(out) == ["exa-search-en", "other-skill"]
