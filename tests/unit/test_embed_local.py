# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: the keyless local embedding provider.

Dense semantic search was reachable only with a Voyage or OpenAI key, so every
keyless user got BM25 — and BM25 answers ``"my app is slow"`` with
bioinformatics packages. The vector store was never the gated part: vectors
already live locally in sqlite-vec, keyed on each tap's commit. The *only*
API-bound step is turning text into vectors, and a query has to be embedded
too, which is why a prebuilt index cannot substitute for this.

``local`` is therefore a third link in the existing chain: Voyage -> OpenAI ->
local -> (None, meaning BM25). Two properties matter most and are asserted
here rather than reasoned about:

* **A configured key still wins.** Adding a fallback must not change what a
  keyed user gets, or this "improvement" silently downgrades every existing
  install from voyage-4 to a 384-dim local model.
* **Everything still degrades.** A missing extra, a failed model load, a bad
  batch — each returns None so the caller floors to BM25, exactly as it does
  today when no key is set.

The tests stub the backend rather than importing onnxruntime: the extra is
optional, so the unit suite must pass without it installed. The real model is
exercised by the integration test at the bottom, which skips when absent.
"""
from __future__ import annotations

import pytest

from boost_cli.core import embed


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No inherited keys, no kill-switch, no cached backend or model."""
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)
    embed.reset_local_cache()
    yield
    embed.reset_local_cache()


class _StubBackend:
    """Stands in for core.localembed: .encode() returns one vector per text."""

    def __init__(self):
        self.calls = []

    def encode(self, texts):
        texts = list(texts)
        self.calls.append(texts)
        return [[float(i)] * embed.LOCAL_DIM for i, _t in enumerate(texts)]


def _with_backend(monkeypatch, backend=None):
    obj = backend if backend is not None else _StubBackend()
    monkeypatch.setattr(embed, "_load_backend", lambda: obj)
    embed.reset_local_cache()
    return obj


def _without_backend(monkeypatch):
    monkeypatch.setattr(embed, "_load_backend", lambda: None)
    embed.reset_local_cache()


class TestProviderChain:
    def test_local_is_used_when_no_key_is_set(self, monkeypatch):
        _with_backend(monkeypatch)
        assert embed.provider() == "local"

    def test_voyage_still_wins_over_local(self, monkeypatch):
        # THE REGRESSION TO AVOID: a keyed user must keep voyage-4. Falling
        # back to a 384-dim local model for someone who is paying for better
        # embeddings would be a silent downgrade.
        _with_backend(monkeypatch)
        monkeypatch.setenv("VOYAGE_API_KEY", "k")
        assert embed.provider() == "voyage"

    def test_openai_still_wins_over_local(self, monkeypatch):
        _with_backend(monkeypatch)
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        assert embed.provider() == "openai"

    def test_no_backend_and_no_key_is_still_none(self, monkeypatch):
        # Without the extra installed nothing changes: callers floor to BM25.
        _without_backend(monkeypatch)
        assert embed.provider() is None
        assert embed.available() is False

    def test_the_kill_switch_disables_local_too(self, monkeypatch):
        # BOOST_NO_EMBED is documented as a hard kill-switch; a provider that
        # ignored it would make it a lie.
        _with_backend(monkeypatch)
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        assert embed.provider() is None

    def test_available_is_true_with_only_the_local_backend(self, monkeypatch):
        _with_backend(monkeypatch)
        assert embed.available() is True


class TestModelIdentity:
    def test_local_reports_its_own_model_name(self, monkeypatch):
        _with_backend(monkeypatch)
        assert embed.model() == embed.LOCAL_MODEL

    def test_local_dimension_is_declared(self, monkeypatch):
        _with_backend(monkeypatch)
        assert embed.dimension() == embed.LOCAL_DIM

    def test_local_dimension_differs_from_the_api_models(self):
        # dense.py rebuilds the index when `model` or `dim` changes, so these
        # differing is what stops a local vector landing in a voyage index.
        assert embed._DIMS[embed.VOYAGE_MODEL] != embed.LOCAL_DIM
        assert embed._DIMS[embed.OPENAI_MODEL] != embed.LOCAL_DIM

    def test_every_known_model_has_a_dimension(self):
        for name in (embed.VOYAGE_MODEL, embed.OPENAI_MODEL, embed.LOCAL_MODEL):
            assert embed._DIMS.get(name), name


class TestEmbedding:
    def test_returns_one_vector_per_text(self, monkeypatch):
        _with_backend(monkeypatch)
        out = embed.embed(["a", "b", "c"])
        assert out is not None and len(out) == 3
        assert all(len(v) == embed.LOCAL_DIM for v in out)

    def test_an_empty_batch_short_circuits(self, monkeypatch):
        _with_backend(monkeypatch)
        assert embed.embed([]) == []

    def test_input_type_is_accepted_and_ignored(self, monkeypatch):
        # Voyage honours it, OpenAI ignores it, and so does the local model —
        # the signature must stay uniform for callers.
        _with_backend(monkeypatch)
        assert embed.embed(["q"], input_type="query") is not None

    def test_the_backend_is_resolved_once_and_reused(self, monkeypatch):
        # Loading an ONNX session is expensive; re-resolving per query would
        # make the local path unusably slow.
        looked_up = []
        backend = _StubBackend()

        def counting():
            looked_up.append(1)
            return backend

        monkeypatch.setattr(embed, "_load_backend", counting)
        embed.reset_local_cache()
        embed.embed(["a"])
        embed.embed(["b"])
        assert len(looked_up) == 1

    def test_a_backend_that_cannot_load_its_model_degrades_to_none(self, monkeypatch):
        # localembed.encode returns None when the weights cannot be downloaded
        # or the session cannot be built. Observed for real: the model fetch
        # fails behind a TLS-intercepting proxy and this is the path that runs.
        class NoModel(_StubBackend):
            def encode(self, texts):
                return None

        _with_backend(monkeypatch, NoModel())
        assert embed.embed(["a"]) is None, "must degrade to BM25, not raise"

    def test_a_raising_backend_degrades_to_none(self, monkeypatch):
        class Broken(_StubBackend):
            def encode(self, texts):
                raise RuntimeError("inference failed")

        _with_backend(monkeypatch, Broken())
        assert embed.embed(["a"]) is None

    def test_a_short_result_is_rejected(self, monkeypatch):
        # A silently truncated batch would misalign vectors against chunks —
        # every hit after the gap would point at the wrong skill.
        class Short(_StubBackend):
            def encode(self, texts):
                return [[0.0] * embed.LOCAL_DIM]

        _with_backend(monkeypatch, Short())
        assert embed.embed(["a", "b"]) is None

    def test_a_wrong_width_vector_is_rejected(self, monkeypatch):
        # The index is created with a fixed dim; a mismatched row would either
        # error deep inside sqlite-vec or corrupt the space.
        class Narrow(_StubBackend):
            def encode(self, texts):
                return [[0.0, 1.0] for _t in texts]

        _with_backend(monkeypatch, Narrow())
        assert embed.embed(["a"]) is None

    def test_numpy_style_rows_are_accepted(self, monkeypatch):
        # fastembed yields numpy arrays, not lists. Anything iterable of floats
        # must come back as plain lists of float for the JSON/sqlite layer.
        class Numpyish(_StubBackend):
            def encode(self, texts):
                return [tuple(0.5 for _ in range(embed.LOCAL_DIM))
                        for _t in texts]

        _with_backend(monkeypatch, Numpyish())
        out = embed.embed(["a"])
        assert out is not None
        assert isinstance(out[0], list) and isinstance(out[0][0], float)


class TestFallbackNote:
    def test_it_no_longer_demands_a_key(self, monkeypatch):
        # The note is the user-facing explanation of why search is BM25. Once a
        # keyless path exists, "you need an API key" is wrong advice.
        _without_backend(monkeypatch)
        note = embed.fallback_note().lower()
        assert "rag" in note
        assert "voyage_api_key or openai_api_key" not in note

    def test_it_names_the_extra_that_unlocks_it(self, monkeypatch):
        _without_backend(monkeypatch)
        assert "[rag]" in embed.fallback_note() or "rag" in embed.fallback_note()


class TestImportIsLazy:
    def test_fastembed_is_not_imported_at_module_import(self):
        # scripts/import_budget.py gates CLI startup time. Importing an ONNX
        # runtime at `import boost_cli.core.embed` would blow it for every
        # command, including `boost --help`.
        from boost_cli.core import localembed
        for mod in (embed, localembed):
            with open(mod.__file__, encoding="utf-8") as fh:
                head = fh.read().split("def ")[0]
            assert "import onnxruntime" not in head, mod.__name__
            assert "import tokenizers" not in head, mod.__name__


@pytest.mark.skipif(embed._load_backend() is None,
                    reason="the [rag] extra's local embedding backend is absent")
class TestAgainstTheRealModel:
    """Runs only where the extra is installed; downloads the model on first use."""

    def test_it_embeds_and_the_width_matches_the_declaration(self, monkeypatch):
        embed.reset_local_cache()
        out = embed.embed(["a skill for reviewing pull requests"])
        assert out is not None, "real backend present but embedding failed"
        assert len(out) == 1
        assert len(out[0]) == embed.LOCAL_DIM, \
            "LOCAL_DIM must match what the model actually emits, or the index " \
            "is created at the wrong width"

    def test_similar_text_scores_closer_than_unrelated_text(self):
        embed.reset_local_cache()
        out = embed.embed(["making my application faster",
                           "application performance tuning",
                           "quantum computing circuit simulation"])
        assert out is not None and len(out) == 3

        def dot(a, b):
            return sum(x * y for x, y in zip(a, b, strict=True))

        near = dot(out[0], out[1])
        far = dot(out[0], out[2])
        assert near > far, \
            "the whole point: semantically close text must rank above " \
            "unrelated text, which is what BM25 fails at"
