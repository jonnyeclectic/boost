# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`dense.entry_vectors`: one representative embedding per entry.

Feeds `rag.collapse_near_duplicate_hits`, which needs a vector per *entry*
(keyed by ``(tap, path)``) rather than per chunk. The lowest-``cix`` chunk —
the name+description chunk `rag.chunk` always emits first — is the
representative, fetched from `vec_raw` through `chunks_entry`, the same index
`_ensure_schema` documents as the reason that table is a plain rowid-keyed
table rather than a `vec0` one: an ``id IN (...)`` against `vec0` plans as a
full scan (see `dense._knn`).

The 8-d toy fixture is shared with `test_dense_quantized.py`'s premise: 8 is
the smallest width `bit[N]` accepts, so this is the quantized layout — the
only one `entry_vectors` supports (a legacy float32 store has no cheap way to
look up an arbitrary vector by id, and returns `{}` there, same as the rest of
this module degrades on that path).
"""
from __future__ import annotations

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


def _vec_for(seed: int) -> list[float]:
    v = [math.sin(seed * 1.7 + i * 0.9) for i in range(8)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


_BODIES = {"skill-%02d" % i: "body of skill %02d" % i for i in range(4)}
_VEC = {name: _vec_for(i) for i, name in enumerate(sorted(_BODIES))}


def _toy_embed(texts, input_type=None, timeout=60):
    return [_VEC.get(t.split("\n", 1)[0].strip(), _vec_for(999)) for t in texts]


def _e(name, tap="acme/skills"):
    return {"name": name, "tap": tap, "kind": "skill",
            "skill_md": "skills/%s/SKILL.md" % name}


_ENTRIES = [_e(n) for n in sorted(_BODIES)]


@pytest.fixture()
def dense_env(sandbox, monkeypatch):
    monkeypatch.setattr(embed, "embed", _toy_embed)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e["name"])
    return monkeypatch


class TestEntryVectors:
    def test_returns_the_stored_vector_for_each_entry(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        keys = [("acme/skills", e["skill_md"]) for e in _ENTRIES]
        got = dense.entry_vectors(keys)
        assert set(got) == set(keys)

    def test_the_vector_decodes_to_the_embedding_that_was_stored(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        key = ("acme/skills", "skills/skill-00/SKILL.md")
        got = dense.entry_vectors([key])
        decoded = rag._decode_vector(got[key])
        expected = _VEC["skill-00"]
        assert all(math.isclose(a, b, abs_tol=1e-5)
                  for a, b in zip(decoded, expected, strict=True))

    def test_an_unknown_entry_is_absent_from_the_result(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        got = dense.entry_vectors([("acme/skills", "skills/nope/SKILL.md")])
        assert got == {}

    def test_empty_input_is_empty_output(self, dense_env):
        dense.build(entries=_ENTRIES, force=True)
        assert dense.entry_vectors([]) == {}

    def test_no_store_at_all_degrades_to_empty(self, sandbox):
        assert dense.entry_vectors([("t", "p")]) == {}

    def test_a_non_quantized_store_degrades_to_empty(self, sandbox, monkeypatch):
        # `dim=3` keeps the legacy float32 layout (see `_quantizable`); that
        # layout has no cheap per-id lookup, so this must not attempt one.
        monkeypatch.setattr(embed, "dimension", lambda: 3)
        con = dense._connect()
        try:
            dense._ensure_schema(con, 3)
            con.commit()
        finally:
            con.close()
        assert dense.entry_vectors([("t", "p")]) == {}
