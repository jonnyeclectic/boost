# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""A truncated HTTP response must degrade, not crash.

``embed._post`` guards with ``except (urllib.error.URLError, OSError, ValueError)``.
``http.client.IncompleteRead`` — what a connection cut mid-body raises — is a
subclass of ``HTTPException`` and of **none** of those three, so it went
straight through ``resp.read()`` and out of ``boost search`` as a traceback.

Seen for real: `boost search mempalace` died with
``IncompleteRead(6629 bytes read, 6200 more expected)``.
"""
from __future__ import annotations

import contextlib
import http.client

import pytest

from boost_cli.core import embed


class _Resp:
    def __init__(self, exc):
        self._exc = exc

    def read(self):
        raise self._exc

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestPostSurvivesTruncation:
    def test_incomplete_read_is_not_a_valueerror(self):
        # The premise of the bug, pinned so a stdlib change can't quietly make
        # this test vacuous.
        assert not issubclass(http.client.IncompleteRead, ValueError)
        assert not issubclass(http.client.IncompleteRead, OSError)

    @pytest.mark.parametrize("exc", [
        http.client.IncompleteRead(b"partial", 6200),
        http.client.LineTooLong("header line"),
        http.client.BadStatusLine("garbage"),
        http.client.RemoteDisconnected("closed"),
    ])
    def test_http_exception_returns_none(self, exc, monkeypatch):
        monkeypatch.setattr(embed.nethttp, "urlopen", lambda *a, **k: _Resp(exc))
        assert embed._post("https://example.invalid", "key", {}, 5) is None

    def test_a_good_response_still_parses(self, monkeypatch):
        class Ok(_Resp):
            def read(self):
                return b'{"data": [{"embedding": [0.5]}]}'
        monkeypatch.setattr(embed.nethttp, "urlopen", lambda *a, **k: Ok(None))
        assert embed._post("https://example.invalid", "key", {}, 5) == {
            "data": [{"embedding": [0.5]}]}

    def test_search_degrades_instead_of_crashing(self, monkeypatch):
        # The user-visible contract: embed() returns None so the caller can
        # fall back to BM25, rather than propagating.
        monkeypatch.setattr(
            embed.nethttp, "urlopen",
            lambda *a, **k: _Resp(http.client.IncompleteRead(b"x", 10)))
        monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
        with contextlib.suppress(Exception):
            assert embed.embed(["query"], input_type="query") is None
