"""Unit tests: boost_cli/core/embed.py — the optional embeddings bridge.

Every network call is monkeypatched; provider selection, the exact request
shape (URL, auth header, model, input_type), and every degradation path are
pinned so the mutation gate has teeth.
"""
from __future__ import annotations

import json

from boost_cli.core import embed


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _capture(monkeypatch, payload=None, exc=None):
    """Patch urlopen; return a dict that captures the Request + timeout."""
    cap = {}

    def fake_urlopen(req, timeout=None):
        cap["url"] = req.full_url
        cap["headers"] = dict(req.headers)
        cap["body"] = json.loads(req.data.decode())
        cap["timeout"] = timeout
        if exc is not None:
            raise exc
        return FakeResp(payload)
    monkeypatch.setattr("boost_cli.core.nethttp.urlopen",
                        fake_urlopen)
    return cap


class TestProviderSelection:
    def test_prefers_voyage_over_openai(self, sandbox, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.provider() == "voyage"
        assert embed.model() == embed.VOYAGE_MODEL
        assert embed.dimension() == 1024
        assert embed.available() is True

    def test_every_selectable_model_has_a_dimension(self, sandbox, monkeypatch):
        """A model bump that forgets ``_DIMS`` would hand ``dense`` a None dim.

        ``dense.build`` bails out on a None dimension, so the vector store would
        silently never build rather than fail loudly.
        """
        for env in ("VOYAGE_API_KEY", "OPENAI_API_KEY"):
            monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
            monkeypatch.delenv("OPENAI_API_KEY", raising=False)
            monkeypatch.setenv(env, "k")
            assert embed.model() in embed._DIMS
            assert isinstance(embed.dimension(), int)

    def test_openai_when_only_openai(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.provider() == "openai"
        assert embed.model() == embed.OPENAI_MODEL
        assert embed.dimension() == 1536

    def test_none_when_nothing_is_available(self, sandbox, monkeypatch):
        """Unconfigured now means no key AND no local backend.

        Forcing `local_available` off matters: since the [rag] extra started
        bundling a local model, "no key" alone no longer implies "no provider".
        Left ambient this asserted the opposite of the truth on any machine with
        the extra installed, and stayed green on CI only because CI does not
        install it.
        """
        monkeypatch.setattr(embed, "local_available", lambda: False)
        assert embed.provider() is None
        assert embed.model() is None
        assert embed.dimension() is None
        assert embed.available() is False

    def test_local_is_the_provider_when_only_the_extra_is_present(self, sandbox,
                                                                  monkeypatch):
        """The keyless tier: the bundled model is a real provider, not a stub."""
        monkeypatch.setattr(embed, "local_available", lambda: True)
        assert embed.provider() == "local"
        assert embed.model() == embed.LOCAL_MODEL
        assert embed.dimension() == embed.LOCAL_DIM
        assert embed.available() is True

    def test_a_key_still_outranks_the_local_backend(self, sandbox, monkeypatch):
        """A fallback that preempted a paid key would silently downgrade every
        existing keyed install to a smaller model."""
        monkeypatch.setattr(embed, "local_available", lambda: True)
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        assert embed.provider() == "voyage"

    def test_kill_switch_disables_even_with_key(self, sandbox, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        assert embed.enabled() is False
        assert embed.provider() is None
        assert embed.available() is False

    def test_fallback_note_names_the_extra_and_not_a_key(self):
        # This assertion used to require the note name VOYAGE_API_KEY and
        # OPENAI_API_KEY. That encoded the old contract — dense search needs an
        # account — which a local provider makes false. Telling a user to go get
        # an API key when the extra alone would do is wrong advice, so the note
        # names the extra and the test pins the new contract.
        note = embed.fallback_note()
        assert "rag" in note
        assert "VOYAGE_API_KEY" not in note and "OPENAI_API_KEY" not in note


class TestEmbed:
    def test_none_without_provider(self, sandbox, monkeypatch):
        # `local_available` is forced off for the same reason as the tests in
        # TestProviderSelection: since the [rag] extra bundles a local model,
        # "no key" no longer implies "no provider", and `embed` returns real
        # vectors rather than None once anything has warmed that backend. Left
        # ambient this passed or failed depending on test ORDER, which made it
        # a latent flake rather than an assertion about the code.
        monkeypatch.setattr(embed, "local_available", lambda: False)
        assert embed.embed(["hi"]) is None

    def test_the_local_backend_alone_still_embeds(self, sandbox, monkeypatch):
        # The other half: with no key but the extra present, embedding works.
        # That is the keyless tier, and nothing else in this file covers it.
        monkeypatch.setattr(embed, "local_available", lambda: True)
        monkeypatch.setattr(embed, "_embed_local", lambda texts, **kw: [[0.1]])
        assert embed.embed(["hi"]) == [[0.1]]

    def test_empty_batch_is_empty_list(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.embed([]) == []

    def test_voyage_request_shape(self, sandbox, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "vkey")
        cap = _capture(monkeypatch,
                       {"data": [{"embedding": [0.1, 0.2]},
                                 {"embedding": [0.3, 0.4]}]})
        out = embed.embed(["a", "b"], input_type="document", timeout=17)
        assert out == [[0.1, 0.2], [0.3, 0.4]]
        assert cap["url"] == embed.VOYAGE_URL
        assert cap["headers"]["Authorization"] == "Bearer vkey"
        assert cap["headers"]["Content-type"] == "application/json"
        assert cap["body"] == {"input": ["a", "b"], "model": embed.VOYAGE_MODEL,
                               "input_type": "document"}
        assert cap["timeout"] == 17

    def test_voyage_omits_input_type_when_unset(self, sandbox, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "vkey")
        cap = _capture(monkeypatch, {"data": [{"embedding": [1.0]}]})
        embed.embed(["a"])
        assert "input_type" not in cap["body"]

    def test_openai_request_shape(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "okey")
        cap = _capture(monkeypatch, {"data": [{"embedding": [0.5, 0.6]}]})
        out = embed.embed(["a"], input_type="document")
        assert out == [[0.5, 0.6]]
        assert cap["url"] == embed.OPENAI_URL
        assert cap["headers"]["Authorization"] == "Bearer okey"
        assert cap["body"] == {"input": ["a"], "model": embed.OPENAI_MODEL}
        assert "input_type" not in cap["body"]        # OpenAI ignores it

    def test_network_error_degrades_to_none(self, sandbox, monkeypatch):
        import urllib.error
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        _capture(monkeypatch, exc=urllib.error.URLError("down"))
        assert embed.embed(["a"]) is None

    def test_bad_json_degrades_to_none(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")

        class BadResp(FakeResp):
            def read(self):
                return b"not json"
        monkeypatch.setattr("boost_cli.core.nethttp.urlopen",
                            lambda req, timeout=None: BadResp(None))
        assert embed.embed(["a"]) is None

    def test_count_mismatch_is_none(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        _capture(monkeypatch, {"data": [{"embedding": [1.0]}]})
        assert embed.embed(["a", "b"]) is None        # asked 2, got 1

    def test_non_dict_response_is_none(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        monkeypatch.setattr("boost_cli.core.nethttp.urlopen",
                            lambda req, timeout=None: FakeResp([1, 2, 3]))
        assert embed.embed(["a"]) is None

    def test_missing_embedding_field_is_none(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        _capture(monkeypatch, {"data": [{"nope": [1.0]}]})
        assert embed.embed(["a"]) is None

    def test_empty_vector_is_none(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        _capture(monkeypatch, {"data": [{"embedding": []}]})
        assert embed.embed(["a"]) is None

    def test_values_coerced_to_float(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        _capture(monkeypatch, {"data": [{"embedding": [1, 2]}]})
        out = embed.embed(["a"])
        assert out == [[1.0, 2.0]]
        assert all(isinstance(x, float) for x in out[0])
