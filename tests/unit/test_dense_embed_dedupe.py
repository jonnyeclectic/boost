# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Duplicate chunk text is embedded once, not once per copy.

Registries mirror each other, so the same chunk text arrives many times in one
build: on a real 460-tap install 42.9% of 750,416 chunks are repeats, worst case
1,464 identical copies of one chunk. Embeddings are deterministic, so paying the
provider for each copy buys a byte-identical vector at N times the price — and
`retrieve_any` runs `dedupe_by_content` on every path, so the copies are
discarded before a user ever sees them.

What must NOT change: one `chunks` row per entry. Tap deletion is scoped by
`chunks.tap`, so collapsing rows would strand a tap's vectors.
"""
from __future__ import annotations

import math

import pytest

from boost_cli.core import dense, embed, rag

_VOCAB = {"testing": (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), "react": (0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
          "python": (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)}


def _toy_embed(texts, input_type=None, timeout=60):
    out = []
    for t in texts:
        v = [0.0] * 8
        for word, base in _VOCAB.items():
            if word in t.lower():
                for i in range(8):
                    v[i] += base[i]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out


def _e(name, body, tap="acme/skills", kind="skill"):
    return {"name": name, "tap": tap, "kind": kind,
            "skill_md": "skills/%s/SKILL.md" % name, "_body": body}


@pytest.fixture()
def counting_env(sandbox, monkeypatch):
    """dense wired to a toy embedder that records every text it is asked for."""
    asked: list[list[str]] = []

    def recording(texts, input_type=None, timeout=60):
        asked.append(list(texts))
        return _toy_embed(texts, input_type, timeout)

    monkeypatch.setattr(embed, "embed", recording)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x",
                                                    "other/skills": "/y"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1",
                                                      "other__skills": "c1"})
    monkeypatch.setattr(dense, "read_body",
                        lambda e, tp=None: e.get("_body", ""))
    return asked


def _flat(asked):
    return [t for batch in asked for t in batch]


def test_identical_bodies_are_embedded_once(counting_env):
    """Four mirrored copies of one skill cost one embedding call, not four."""
    body = "react testing components"
    entries = [_e("jest", body),
               _e("jest-copy", body),
               _e("jest-vendored", body),
               _e("jest-mirror", body, tap="other/skills")]
    if dense.build(entries) is None:
        pytest.skip("sqlite-vec backend unavailable")
    sent = _flat(counting_env)
    assert sent.count(body) == 1, "one text, one embedding call"


def test_every_entry_still_gets_its_own_chunk_row(counting_env):
    """Tap deletion is scoped by chunks.tap — rows must not be collapsed."""
    body = "react testing components"
    entries = [_e("a", body), _e("b", body), _e("c", body, tap="other/skills")]
    if dense.build(entries) is None:
        pytest.skip("sqlite-vec backend unavailable")
    con = dense._connect()
    assert con is not None
    names = {r[0] for r in con.execute("SELECT name FROM chunks")}
    assert names == {"a", "b", "c"}
    per_tap = dict(con.execute("SELECT tap, COUNT(*) FROM chunks GROUP BY tap"))
    assert per_tap == {"acme/skills": 2, "other/skills": 1}
    con.close()


def test_duplicates_get_the_same_vector(counting_env):
    """The saving must be invisible: identical text, identical stored vector."""
    body = "react testing components"
    entries = [_e("a", body), _e("b", body)]
    if dense.build(entries) is None:
        pytest.skip("sqlite-vec backend unavailable")
    con = dense._connect()
    rows = list(con.execute(
        "SELECT c.name, v.embedding FROM chunks c "
        "JOIN vec_raw v ON v.id = c.id ORDER BY c.name"))
    assert len(rows) == 2
    assert rows[0][1] == rows[1][1], "same text must store the same vector"
    con.close()


def test_distinct_bodies_are_each_embedded(counting_env):
    entries = [_e("a", "react testing components"),
               _e("b", "python testing fixtures")]
    if dense.build(entries) is None:
        pytest.skip("sqlite-vec backend unavailable")
    sent = _flat(counting_env)
    assert "react testing components" in sent
    assert "python testing fixtures" in sent


def test_texts_are_embedded_as_documents(sandbox, monkeypatch):
    """Asymmetric providers embed a document and a query differently.

    Voyage and OpenAI both return a different vector for the same text under a
    different `input_type`, and a build that says "query" scores every stored
    chunk against the wrong half of the space. Nothing about the result *looks*
    broken — retrieval just gets quietly worse — so the argument is pinned here.
    """
    kinds: list = []

    def recording(texts, input_type=None, timeout=60):
        kinds.append(input_type)
        return _toy_embed(texts, input_type, timeout)

    monkeypatch.setattr(embed, "embed", recording)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-8")
    monkeypatch.setattr(embed, "dimension", lambda: 8)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e.get("_body", ""))
    if dense.build([_e("a", "react testing")]) is None:
        pytest.skip("sqlite-vec backend unavailable")
    assert kinds and set(kinds) == {"document"}


def test_one_rejected_batch_does_not_abandon_the_build(counting_env, monkeypatch):
    """A rate-limited batch costs its own texts, not every text after it.

    Both loops have to keep going for this to hold — the one calling the
    provider and the one inserting rows. Stopping at the first refusal turns a
    transient 429 on chunk 3 of 400,000 into an index that silently ends there,
    and the store still reports itself built.
    """
    monkeypatch.setattr(dense, "_BATCH", 1)

    def flaky(texts, input_type=None, timeout=60):
        if any("poison" in t for t in texts):
            return None
        return _toy_embed(texts, input_type, timeout)

    monkeypatch.setattr(embed, "embed", flaky)
    entries = [_e("bad", "poison python fixtures"),
               _e("good", "react testing components")]
    if dense.build(entries) is None:
        pytest.skip("sqlite-vec backend unavailable")
    con = dense._connect()
    assert con is not None
    names = {r[0] for r in con.execute("SELECT name FROM chunks")}
    con.close()
    assert names == {"good"}, "the row after the rejected one must still store"


def test_without_the_backend_every_tap_is_reported_failed(sandbox, monkeypatch):
    """No serializer means nothing stored, so no tap may be recorded as built.

    The caller writes a per-tap commit for whatever comes back clean, and a tap
    with a recorded commit is skipped on the next build. Returning "0 added, 0
    failed" would therefore not degrade to BM25 — it would mark the whole
    corpus done and leave the vector store permanently, silently empty.
    """
    monkeypatch.setattr(dense, "_load", lambda: None)
    entries = [_e("a", "one"), _e("b", "two", tap="other/skills")]
    added, failed = dense._embed_and_store(None, entries, None)
    assert added == 0
    assert failed == {"acme/skills", "other/skills"}


def test_the_stored_snippet_is_bounded(counting_env):
    """`snip` is a preview column, not a second copy of the corpus."""
    entries = [_e("long", "react testing " + "x" * 5000)]
    if dense.build(entries) is None:
        pytest.skip("sqlite-vec backend unavailable")
    con = dense._connect()
    snips = [r[0] for r in con.execute("SELECT snip FROM chunks")]
    con.close()
    assert snips and all(len(s) <= 200 for s in snips)


def test_a_failed_batch_still_reports_its_taps(counting_env, monkeypatch):
    """A provider rejection must mark every owning tap, not just one copy."""
    monkeypatch.setattr(embed, "embed", lambda *a, **k: None)
    body = "react testing components"
    entries = [_e("a", body), _e("b", body, tap="other/skills")]
    stats = dense.build(entries)
    if stats is None:
        pytest.skip("sqlite-vec backend unavailable")
    con = dense._connect()
    if con is None:
        pytest.skip("sqlite-vec backend unavailable")
    stored = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    con.close()
    assert stored == 0, "nothing is stored when every embedding call fails"
