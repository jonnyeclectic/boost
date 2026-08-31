# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One pasted paragraph must not own the result page.

Registries vendor boilerplate. Measured on a real 657,587-chunk store, the
largest cluster of **byte-identical** embeddings is 1,464 copies spanning
**1,464 distinct skills across two taps** — a Composio/Rube tool-calling
paragraph pasted into every skill in two registries.

Identical vectors produce an identical cosine distance, so every entry holding
that paragraph arrived with the *same* score and `retrieve`'s tie-break (the
displayed name) decided the page alphabetically. Measured before this change:
a query landing near that paragraph filled **60 of 60 slots** from the cluster.
Not one of those results matched on text its own skill wrote.

`rag.dedupe_by_content` cannot reach it, and is right not to: it keys on the
*entry body* digest, and these are 1,464 genuinely different entries. The
repetition is one chunk *inside* each of them — the axis
`near-duplicate-items-eat-the-result-slots` leaves open.

**Capping the page alone is not enough, and that is the subtle part.** The
candidate pool is built first: the rescore used to take the 480 nearest rows,
and 480 of the cluster's 1,464 copies are nearer than anything else, so the
pool was 100% one vector. Capping the page then yielded three results and
57 empty slots. Measured on the real store, before and after:

    pool distinct vectors     1  ->  242
    rows from the cluster   480  ->    3
    final page       60/60 boilerplate  ->  60 results, 30 distinct vectors

So the cap has to run **while the pool is being assembled**, where the rows
that lose a slot can be replaced by the next distinct vector rather than by
the next copy. `_knn` thins; `retrieve` caps entries. Different units, both
needed: one chunk can serve many entries, and one entry can hold many chunks.
"""
import math
import sqlite3

import pytest

from boost_cli.core import dense, embed, rag


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


pytestmark = pytest.mark.skipif(
    not _vec_loadable(), reason="sqlite-vec extension not loadable here")

#: Twelve skills paste the SAME paragraph; four have bodies of their own. The
#: shape of the real finding at a size a unit test can hold.
_SHARED = "shared-boilerplate-paragraph"
_PASTERS = ["paster-%02d" % i for i in range(12)]
_ORIGINALS = ["original-%02d" % i for i in range(4)]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _vec_for(seed: int):
    return _unit([math.sin(seed * 1.7 + i * 0.9) for i in range(8)])


_BOILERPLATE_VEC = _vec_for(0)
_ORIGINAL_VEC = {n: _vec_for(i + 1) for i, n in enumerate(_ORIGINALS)}


def _toy_embed(texts, input_type=None, timeout=60):
    out = []
    for t in texts:
        head = t.split("\n", 1)[0].strip()
        # Every paster embeds to the IDENTICAL vector — that is the premise.
        out.append(_ORIGINAL_VEC.get(head, _BOILERPLATE_VEC))
    return out


def _e(name):
    return {"name": name, "tap": "acme/skills", "kind": "skill",
            "skill_md": "skills/%s/SKILL.md" % name}


_ENTRIES = [_e(n) for n in _PASTERS + _ORIGINALS]


@pytest.fixture()
def cluster_env(sandbox, monkeypatch):
    monkeypatch.setattr(embed, "embed", _toy_embed)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    # A paster's body IS the boilerplate; an original's body is its own name.
    monkeypatch.setattr(
        dense, "read_body",
        lambda e, tp=None: (e["name"] if e["name"] in _ORIGINAL_VEC
                            else _SHARED))
    dense.build(entries=_ENTRIES, force=True)
    return monkeypatch


def _open():
    con = sqlite3.connect(str(dense.db_path()))
    import sqlite_vec
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    return con


def _qblob(con, vec):
    mod = dense._load()
    return mod.serialize_float32(vec)


class TestThePremiseHolds:
    """Without this the rest could pass by the cluster not existing."""

    def test_the_pasters_really_do_share_one_embedding(self, cluster_env):
        con = _open()
        try:
            blobs = {r[0] for r in con.execute("SELECT embedding FROM vec_raw")}
            rows = con.execute("SELECT COUNT(*) FROM vec_raw").fetchone()[0]
        finally:
            con.close()
        assert rows == len(_ENTRIES)
        # 12 pasters collapse to one distinct blob; 4 originals keep their own.
        assert len(blobs) == 1 + len(_ORIGINALS), len(blobs)


class TestThePoolIsThinnedByVector:
    def test_one_vector_cannot_take_the_whole_pool(self, cluster_env):
        con = _open()
        try:
            knn = dense._knn(con, _qblob(con, _BOILERPLATE_VEC), pool=16)
        finally:
            con.close()
        from collections import Counter
        per = Counter(v for _i, _d, v in knn)
        assert max(per.values()) <= dense.MAX_PER_VECTOR, per
        # and the freed slots went to real, different vectors
        assert len(per) > 1, per

    def test_the_originals_are_still_reachable(self, cluster_env):
        # The whole point of freeing the slots: entries that matched on
        # something of their own must survive the cluster's neighbours.
        con = _open()
        try:
            knn = dense._knn(con, _qblob(con, _BOILERPLATE_VEC), pool=16)
            ids = [r[0] for r in knn]
            names = {r[0] for r in con.execute(
                "SELECT name FROM chunks WHERE id IN (%s)"  # noqa: S608  ids are bound params
                % ",".join("?" * len(ids)), ids)}
        finally:
            con.close()
        assert names & set(_ORIGINALS), names

    def test_every_row_carries_its_vector_key(self, cluster_env):
        con = _open()
        try:
            knn = dense._knn(con, _qblob(con, _BOILERPLATE_VEC), pool=8)
        finally:
            con.close()
        assert knn and all(isinstance(v, bytes) and v for _i, _d, v in knn)


class TestThePageIsCapped:
    def test_the_cluster_does_not_own_the_results(self, cluster_env):
        hits = dense.retrieve(_SHARED, k=12, entries=_ENTRIES)
        assert hits is not None
        pasters = [h for h in hits if h["entry"]["name"] in _PASTERS]
        assert len(pasters) <= dense.MAX_PER_VECTOR, [
            h["entry"]["name"] for h in hits]

    def test_the_page_is_not_left_short_by_the_cap(self, cluster_env):
        # Skipping past the cap rather than truncating is what keeps the page
        # full — the bug the first draft of this fix had.
        hits = dense.retrieve(_SHARED, k=6, entries=_ENTRIES)
        assert hits is not None and len(hits) == 6, hits

    def test_an_entry_that_matched_on_its_own_body_is_not_capped_away(
            self, cluster_env):
        name = _ORIGINALS[0]
        hits = dense.retrieve(name, k=6, entries=_ENTRIES)
        assert hits is not None
        assert hits[0]["entry"]["name"] == name, [
            h["entry"]["name"] for h in hits]

    def test_a_query_with_no_cluster_is_unaffected(self, cluster_env):
        # The cap must be invisible when nothing repeats: four originals, four
        # distinct vectors, all four returned.
        hits = dense.retrieve(_ORIGINALS[1], k=16, entries=_ENTRIES)
        assert hits is not None
        got = {h["entry"]["name"] for h in hits}
        assert set(_ORIGINALS) <= got, got


class TestTheCapIsAConstantNotAMagicNumber:
    def test_it_is_declared_and_positive(self):
        assert isinstance(dense.MAX_PER_VECTOR, int)
        assert dense.MAX_PER_VECTOR >= 1

    def test_raising_it_admits_more_copies(self, cluster_env, monkeypatch):
        # Pins that the constant is what does the work — a mutant that ignores
        # it, or hardcodes 3 elsewhere, fails here.
        monkeypatch.setattr(dense, "MAX_PER_VECTOR", 8)
        con = _open()
        try:
            knn = dense._knn(con, _qblob(con, _BOILERPLATE_VEC), pool=16)
        finally:
            con.close()
        from collections import Counter
        per = Counter(v for _i, _d, v in knn)
        assert max(per.values()) > 3, per
