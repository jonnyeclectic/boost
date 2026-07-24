"""Unit tests: boost_cli/core/serve.py — the `boost serve` HTTP catalog server.

`route` is the pure request→response core (no socket), so every endpoint and
status code is pinned here. The store/tap lookups (`skill_text`, `serve_page`)
are exercised against monkeypatched core modules so the mutation gate has teeth
without binding a port.
"""
from __future__ import annotations

import errno
import json

import pytest

from boost_cli.core import serve
from boost_cli.errors import BoostError


class _Tap:
    def __init__(self, path):
        self.path = path


def _patch_catalog(monkeypatch, *, installed=None, entries=None, find=None,
                   taps=None):
    monkeypatch.setattr(serve.lockfile, "installed", lambda: installed or {})
    monkeypatch.setattr(serve.lockfile, "read",
                        lambda: {"version": 3, "skills": installed or {}})
    monkeypatch.setattr(serve.catalog, "all_entries", lambda: entries or [])
    monkeypatch.setattr(serve.catalog, "find", lambda n: (find or {}).get(n, []))
    monkeypatch.setattr(serve.registry, "list_taps", lambda: taps or [])


class TestRoute:
    def test_root_serves_html(self, monkeypatch):
        _patch_catalog(monkeypatch, installed={"a": {"version": "1", "tap": "t"}})
        status, ctype, body = serve.route("/")
        assert status == 200
        assert ctype == "text/html; charset=utf-8"
        assert b"boost" in body and b"<table>" in body

    def test_index_html_alias(self, monkeypatch):
        _patch_catalog(monkeypatch)
        assert serve.route("/index.html")[0] == 200

    def test_catalog_json(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[{"name": "x"}])
        status, ctype, body = serve.route("/catalog.json")
        assert status == 200 and ctype == "application/json"
        assert json.loads(body) == [{"name": "x"}]

    def test_installed_json(self, monkeypatch):
        _patch_catalog(monkeypatch, installed={"a": {"version": "1"}})
        status, _ctype, body = serve.route("/installed.json")
        assert status == 200
        data = json.loads(body)
        assert data["version"] == 3 and "a" in data["skills"]

    def test_query_string_stripped(self, monkeypatch):
        _patch_catalog(monkeypatch)
        assert serve.route("/catalog.json?foo=bar")[0] == 200

    def test_skill_valid_installed(self, monkeypatch, tmp_path):
        sd = tmp_path / "mine"
        sd.mkdir()
        (sd / "SKILL.md").write_text("---\nname: mine\n---\nbody", encoding="utf-8")
        _patch_catalog(monkeypatch)
        monkeypatch.setattr(serve.store, "skill_store_dir", lambda n: sd)
        status, ctype, body = serve.route("/skill/mine")
        assert status == 200 and ctype == "text/plain; charset=utf-8"
        assert b"name: mine" in body

    def test_skill_invalid_name_404(self, monkeypatch):
        _patch_catalog(monkeypatch)
        status, _ctype, body = serve.route("/skill/bad name!")
        assert status == 404
        assert "no skill named" in json.loads(body)["error"]

    def test_skill_unknown_404(self, monkeypatch, tmp_path):
        _patch_catalog(monkeypatch)
        monkeypatch.setattr(serve.store, "skill_store_dir",
                            lambda n: tmp_path / "missing")
        status, _ctype, body = serve.route("/skill/ghost")
        assert status == 404
        assert json.loads(body)["error"] == "no skill named 'ghost'"

    def test_unknown_path_404(self, monkeypatch):
        _patch_catalog(monkeypatch)
        status, _ctype, body = serve.route("/nope")
        assert status == 404
        assert json.loads(body) == {"error": "not found"}


class TestSkillText:
    def test_invalid_name_is_none(self, monkeypatch):
        assert serve.skill_text("bad/name") is None

    def test_from_tap_when_not_in_store(self, monkeypatch, tmp_path):
        # store copy absent -> fall back to the tap clone
        store_dir = tmp_path / "store"
        store_dir.mkdir()
        tap_dir = tmp_path / "tap"
        tap_dir.mkdir()
        (tap_dir / "SKILL.md").write_text("tap-body", encoding="utf-8")
        monkeypatch.setattr(serve.store, "skill_store_dir", lambda n: store_dir)
        monkeypatch.setattr(serve.catalog, "find",
                            lambda n: [{"tap": "t", "skill_md": "SKILL.md"}])
        monkeypatch.setattr(serve.registry, "get", lambda t: _Tap(tap_dir))
        assert serve.skill_text("thing") == "tap-body"

    def test_tap_lookup_error_skipped(self, monkeypatch, tmp_path):
        store_dir = tmp_path / "store"
        store_dir.mkdir()
        monkeypatch.setattr(serve.store, "skill_store_dir", lambda n: store_dir)
        monkeypatch.setattr(serve.catalog, "find",
                            lambda n: [{"tap": "gone", "skill_md": "SKILL.md"}])

        def boom(_t):
            raise BoostError("no such tap")
        monkeypatch.setattr(serve.registry, "get", boom)
        assert serve.skill_text("thing") is None


class TestServePage:
    def test_empty_state_message(self, monkeypatch):
        _patch_catalog(monkeypatch, installed={}, entries=[], taps=[])
        page = serve.serve_page()
        assert "nothing installed" in page
        assert "0 installed · 0 available across 0 taps" in page

    def test_counts_and_rows(self, monkeypatch):
        _patch_catalog(
            monkeypatch,
            installed={"brainstorming": {"version": "1.4.0", "tap": "core"}},
            entries=[{"name": "brainstorming"}, {"name": "other"}],
            taps=[_Tap("a")])
        page = serve.serve_page()
        assert "1 installed · 2 available across 1 taps" in page
        assert 'href="/skill/brainstorming"' in page
        assert "1.4.0" in page


class TestServeHttp:
    """serve_http's OSError -> BoostError translation (no real socket bound)."""

    def _boom(self, exc):
        def raiser(*_a, **_kw):
            raise exc
        return raiser

    def test_addrinuse_is_friendly(self, monkeypatch):
        e = OSError()
        e.errno = errno.EADDRINUSE
        monkeypatch.setattr(serve, "ThreadingHTTPServer", self._boom(e))
        with pytest.raises(BoostError) as ei:
            serve.serve_http("127.0.0.1", 1234)
        assert ei.value.message == "port 1234 is already in use"
        assert ei.value.hint == "pick another with --port"

    def test_windows_winerror_10013_is_friendly(self, monkeypatch):
        e = OSError()
        e.errno = None
        e.winerror = 10013
        monkeypatch.setattr(serve, "ThreadingHTTPServer", self._boom(e))
        monkeypatch.setattr(serve.sys, "platform", "win32")
        with pytest.raises(BoostError) as ei:
            serve.serve_http("127.0.0.1", 1234)
        assert ei.value.message == "port 1234 is already in use"

    def test_winerror_10013_on_non_windows_is_generic(self, monkeypatch):
        # The 10013 special-case is Windows-only: on any other platform a
        # winerror attribute would be a genuinely different failure.
        e = OSError()
        e.errno = None
        e.winerror = 10013
        monkeypatch.setattr(serve, "ThreadingHTTPServer", self._boom(e))
        monkeypatch.setattr(serve.sys, "platform", "linux")
        with pytest.raises(BoostError) as ei:
            serve.serve_http("127.0.0.1", 1234)
        assert "cannot bind 127.0.0.1:1234" in ei.value.message

    def test_other_oserror_is_generic(self, monkeypatch):
        e = OSError(13, "Permission denied")
        monkeypatch.setattr(serve, "ThreadingHTTPServer", self._boom(e))
        with pytest.raises(BoostError) as ei:
            serve.serve_http("127.0.0.1", 1234)
        assert "cannot bind 127.0.0.1:1234" in ei.value.message
        assert ei.value.hint == "check --host and --port"


class TestDoGetErrorHandling:
    def test_success_path_forwards_routed_response(self, monkeypatch):
        # do_GET must route THIS request's path and send the routed triple
        # verbatim — pins route(self.path) and _send(status, ctype, body).
        handler = serve._CatalogHandler.__new__(serve._CatalogHandler)
        handler.command = "GET"
        handler.path = "/catalog.json"
        sent = {}
        monkeypatch.setattr(handler, "_send", lambda status, ctype, body:
                            sent.update(status=status, ctype=ctype, body=body))
        # echo the path back so a route(None) mutant crashes instead of matching
        monkeypatch.setattr(serve, "route",
                            lambda p: (200, "text/plain", p.encode()))
        handler.do_GET()
        assert (sent["status"], sent["ctype"]) == (200, "text/plain")
        assert sent["body"] == b"/catalog.json"

    def test_unexpected_error_body_is_generic_detail_logged(self, monkeypatch):
        # A crash in routing must NOT ship the exception text (which can carry
        # filesystem paths / internal state) to the HTTP client — the client
        # gets a generic body, the specifics go to the server-side log.
        handler = serve._CatalogHandler.__new__(serve._CatalogHandler)
        handler.command = "GET"
        handler.path = "/catalog.json"
        sent = {}
        monkeypatch.setattr(handler, "_send", lambda status, ctype, body:
                            sent.update(status=status, ctype=ctype, body=body))
        logged = []
        monkeypatch.setattr(serve.logs, "get_logger",
                            lambda: type("L", (), {"warning": lambda _s, *a: logged.append(a)})())

        def boom(_path):
            raise RuntimeError("/Users/secret/leaked/path.json missing")
        monkeypatch.setattr(serve, "route", boom)

        handler.do_GET()

        assert sent["status"] == 500
        assert sent["ctype"] == "application/json"           # JSON body, JSON type
        assert json.loads(sent["body"]) == {"error": "internal server error"}
        assert b"secret" not in sent["body"]                 # nothing leaked to client
        # detail kept server-side, with the request context in the log record
        assert logged, "the failure must be logged server-side"
        record = logged[0]
        assert record[0].startswith("serve:")                # format string intact
        assert record[1] == "GET" and record[2] == "/catalog.json"  # command, path
        assert record[3] == "RuntimeError"                   # exception type name arg
        assert "secret/leaked" in str(record[-1])            # the exception itself

    def test_broken_pipe_is_swallowed(self, monkeypatch):
        # a client that hangs up mid-response must not crash the handler
        handler = serve._CatalogHandler.__new__(serve._CatalogHandler)
        handler.command = "GET"
        handler.path = "/"
        monkeypatch.setattr(serve, "route",
                            lambda _p: (_ for _ in ()).throw(BrokenPipeError()))
        handler.do_GET()   # must not raise
