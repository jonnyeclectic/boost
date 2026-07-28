"""Unit tests: boost_cli/core/serve.py — the `boost serve` HTTP catalog server.

`route` is the pure request→response core (no socket), so every endpoint and
status code is pinned here. The store/tap lookups (`skill_text`, `serve_page`)
are exercised against monkeypatched core modules so the mutation gate has teeth
without binding a port.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path

import pytest

from boost_cli.core import output as out
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


# ---------------------------------------------------------------- _is_within

class TestIsWithin:
    def test_base_itself_is_within(self, tmp_path):
        assert serve._is_within(tmp_path, tmp_path) is True

    def test_child_is_within(self, tmp_path):
        assert serve._is_within(tmp_path, tmp_path / "a" / "b") is True

    def test_sibling_is_not_within(self, tmp_path):
        assert serve._is_within(tmp_path / "a", tmp_path / "b") is False

    def test_name_prefix_sibling_is_not_within(self, tmp_path):
        # "…/foobar" starts with "…/foo" as a *string* but is not inside it
        assert serve._is_within(tmp_path / "foo", tmp_path / "foobar") is False

    def test_parent_is_not_within_child(self, tmp_path):
        assert serve._is_within(tmp_path / "a", tmp_path) is False

    def test_unresolvable_path_is_not_within(self, tmp_path):
        # embedded NUL -> ValueError out of resolve(), swallowed as "not within"
        assert serve._is_within(tmp_path, Path("a\x00b")) is False


# --------------------------------------------------------- _safe_join_within

class TestSafeJoinWithin:
    def test_relative_join_returns_resolved_child(self, tmp_path):
        assert (serve._safe_join_within(tmp_path, Path("SKILL.md"))
                == tmp_path.resolve() / "SKILL.md")

    def test_string_rel_is_accepted(self, tmp_path):
        assert (serve._safe_join_within(tmp_path, "SKILL.md")
                == tmp_path.resolve() / "SKILL.md")

    def test_dotdot_inside_base_is_normalised_not_rejected(self, tmp_path):
        assert (serve._safe_join_within(tmp_path, Path("sub/../SKILL.md"))
                == tmp_path.resolve() / "SKILL.md")

    def test_absolute_rel_is_refused(self, tmp_path):
        assert serve._safe_join_within(tmp_path, Path(tmp_path / "x")) is None

    def test_dotdot_escape_is_refused(self, tmp_path):
        base = tmp_path / "base"
        base.mkdir()
        assert serve._safe_join_within(base, Path("../outside.md")) is None

    def test_symlink_escape_is_refused(self, tmp_path):
        base = tmp_path / "base"
        base.mkdir()
        outside = tmp_path / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        os.symlink(outside, base / "link.md")
        assert serve._safe_join_within(base, Path("link.md")) is None

    def test_non_path_rel_is_refused(self, tmp_path):
        assert serve._safe_join_within(tmp_path, None) is None


# ------------------------------------------------------ skill_text adversarial

def _wire(monkeypatch, store_dir, tap_dir, entries):
    monkeypatch.setattr(serve.store, "skill_store_dir", lambda n: store_dir)
    monkeypatch.setattr(serve.catalog, "find", lambda n: entries)
    monkeypatch.setattr(serve.registry, "get", lambda t: _Tap(tap_dir))


class TestSkillTextTraversal:
    def _layout(self, tmp_path):
        store_dir = tmp_path / "store" / "thing"
        store_dir.mkdir(parents=True)
        tap_dir = tmp_path / "tap"
        tap_dir.mkdir()
        secret = tmp_path / "secret.md"
        secret.write_text("TOP SECRET", encoding="utf-8")
        return store_dir, tap_dir, secret

    def test_dotdot_skill_md_is_refused(self, monkeypatch, tmp_path):
        store_dir, tap_dir, secret = self._layout(tmp_path)
        _wire(monkeypatch, store_dir, tap_dir,
              [{"tap": "t", "skill_md": "../secret.md"}])
        assert secret.read_text(encoding="utf-8") == "TOP SECRET"   # readable
        assert serve.skill_text("thing") is None                    # but refused

    def test_absolute_skill_md_is_refused(self, monkeypatch, tmp_path):
        store_dir, tap_dir, secret = self._layout(tmp_path)
        _wire(monkeypatch, store_dir, tap_dir,
              [{"tap": "t", "skill_md": str(secret)}])
        assert serve.skill_text("thing") is None

    def test_tap_symlink_escape_is_refused(self, monkeypatch, tmp_path):
        store_dir, tap_dir, secret = self._layout(tmp_path)
        os.symlink(secret, tap_dir / "SKILL.md")
        _wire(monkeypatch, store_dir, tap_dir,
              [{"tap": "t", "skill_md": "SKILL.md"}])
        assert serve.skill_text("thing") is None

    def test_store_symlink_escape_is_refused(self, monkeypatch, tmp_path):
        store_dir, tap_dir, secret = self._layout(tmp_path)
        os.symlink(secret, store_dir / "SKILL.md")
        _wire(monkeypatch, store_dir, tap_dir, [])
        assert serve.skill_text("thing") is None

    def test_refused_entry_does_not_stop_the_scan(self, monkeypatch, tmp_path):
        # the `continue` must keep scanning: a hostile first entry must not
        # shadow a legitimate later one (a `break` here would return None)
        store_dir, tap_dir, _secret = self._layout(tmp_path)
        (tap_dir / "SKILL.md").write_text("good-body", encoding="utf-8")
        _wire(monkeypatch, store_dir, tap_dir,
              [{"tap": "t", "skill_md": "../secret.md"},
               {"tap": "t", "skill_md": "SKILL.md"}])
        assert serve.skill_text("thing") == "good-body"

    def test_missing_file_entry_does_not_stop_the_scan(self, monkeypatch, tmp_path):
        store_dir, tap_dir, _secret = self._layout(tmp_path)
        (tap_dir / "SKILL.md").write_text("good-body", encoding="utf-8")
        _wire(monkeypatch, store_dir, tap_dir,
              [{"tap": "t", "skill_md": "nope/SKILL.md"},
               {"tap": "t", "skill_md": "SKILL.md"}])
        assert serve.skill_text("thing") == "good-body"

    def test_non_string_name_is_refused(self):
        assert serve._validated_skill_name(None) is None
        assert serve._validated_skill_name(b"brainstorming") is None
        assert serve.skill_text(None) is None

    @pytest.mark.parametrize("name", [".", ".."])
    def test_dot_names_are_refused(self, name):
        assert serve._validated_skill_name(name) is None

    def test_route_dotdot_name_is_404_not_500(self, sandbox, monkeypatch):
        # `..` passes SKILL_NAME_RE; only the {".",".."} guard stops it, and
        # store.skill_store_dir("..") would raise BoostError without it.
        monkeypatch.setattr(serve.catalog, "find", lambda n: [])
        status, ctype, body = serve.route("/skill/..")
        assert status == 404
        assert ctype == "application/json"
        assert json.loads(body) == {"error": "no skill named '..'"}

    def test_route_percent_encoded_traversal_is_404(self, sandbox, monkeypatch):
        monkeypatch.setattr(serve.catalog, "find", lambda n: [])
        status, _ctype, body = serve.route("/skill/%2e%2e%2f%2e%2e%2fetc%2fpasswd")
        assert status == 404
        assert json.loads(body) == {"error": "no skill named '../../etc/passwd'"}


# ------------------------------------------------------------------- _send

class _Wire:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b


class TestSend:
    def _handler(self, monkeypatch):
        h = serve._CatalogHandler.__new__(serve._CatalogHandler)
        h.command = "GET"
        h.path = "/catalog.json"
        h.wfile = _Wire()
        calls = {"status": None, "headers": [], "ended": 0}
        monkeypatch.setattr(h, "send_response",
                            lambda s: calls.__setitem__("status", s))
        monkeypatch.setattr(h, "send_header",
                            lambda k, v: calls["headers"].append((k, v)))
        monkeypatch.setattr(h, "end_headers",
                            lambda: calls.__setitem__("ended", calls["ended"] + 1))
        return h, calls

    def test_headers_body_and_log_are_exact(self, monkeypatch):
        h, calls = self._handler(monkeypatch)
        dimmed = []
        monkeypatch.setattr(serve.out, "dim", dimmed.append)
        h._send(200, "application/json", b'{"ok": true}')
        assert calls["status"] == 200
        assert calls["headers"] == [("Content-Type", "application/json"),
                                    ("Content-Length", "12")]
        assert calls["ended"] == 1
        assert h.wfile.data == b'{"ok": true}'
        assert dimmed == ["  GET /catalog.json → 200"]

    def test_log_message_is_silent(self, monkeypatch, capsys):
        h = serve._CatalogHandler.__new__(serve._CatalogHandler)
        assert h.log_message("%s - %s", "a", "b") is None
        assert capsys.readouterr() == ("", "")


# --------------------------------------------------------------- serve_http

class _FakeServer:
    def __init__(self, addr, handler, boom=None):
        self.addr, self.handler, self.boom = addr, handler, boom
        self.served = 0
        self.closed = 0

    def serve_forever(self):
        self.served += 1
        if self.boom is not None:
            raise self.boom

    def server_close(self):
        self.closed += 1


class TestServeHttpRun:
    def _install(self, monkeypatch, boom=None):
        made = {}

        def factory(addr, handler):
            made["srv"] = _FakeServer(addr, handler, boom)
            return made["srv"]
        monkeypatch.setattr(serve, "ThreadingHTTPServer", factory)
        return made

    def test_binds_announces_serves_and_closes(self, monkeypatch):
        made = self._install(monkeypatch)
        infos = []
        monkeypatch.setattr(serve.out, "info", infos.append)
        serve.serve_http("1.2.3.4", 8080)
        srv = made["srv"]
        assert srv.addr == ("1.2.3.4", 8080)
        assert srv.handler is serve._CatalogHandler
        assert (srv.served, srv.closed) == (1, 1)
        assert infos == ["⚡ serving skill catalog on http://1.2.3.4:8080 "
                         + out.c("(ctrl-c to stop)", out.DIM)]

    def test_keyboard_interrupt_stops_cleanly(self, monkeypatch, capsys):
        made = self._install(monkeypatch, boom=KeyboardInterrupt())
        monkeypatch.setattr(serve.out, "info", lambda _m: None)
        oks = []
        monkeypatch.setattr(serve.out, "ok", oks.append)
        serve.serve_http("127.0.0.1", 9)
        assert oks == ["server stopped"]
        assert made["srv"].closed == 1
