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
    monkeypatch.setattr("boost_cli.core.embed.urllib.request.urlopen",
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

    def test_openai_when_only_openai(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.provider() == "openai"
        assert embed.model() == embed.OPENAI_MODEL
        assert embed.dimension() == 1536

    def test_none_when_unconfigured(self, sandbox):
        assert embed.provider() is None
        assert embed.model() is None
        assert embed.dimension() is None
        assert embed.available() is False

    def test_kill_switch_disables_even_with_key(self, sandbox, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        assert embed.enabled() is False
        assert embed.provider() is None
        assert embed.available() is False

    def test_fallback_note_mentions_extra_and_keys(self):
        note = embed.fallback_note()
        assert "rag" in note
        assert "VOYAGE_API_KEY" in note and "OPENAI_API_KEY" in note


class TestEmbed:
    def test_none_without_provider(self, sandbox):
        assert embed.embed(["hi"]) is None

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
        monkeypatch.setattr("boost_cli.core.embed.urllib.request.urlopen",
                            lambda req, timeout=None: BadResp(None))
        assert embed.embed(["a"]) is None

    def test_count_mismatch_is_none(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        _capture(monkeypatch, {"data": [{"embedding": [1.0]}]})
        assert embed.embed(["a", "b"]) is None        # asked 2, got 1

    def test_non_dict_response_is_none(self, sandbox, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        monkeypatch.setattr("boost_cli.core.embed.urllib.request.urlopen",
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
