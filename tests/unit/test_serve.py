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
import urllib.parse
from pathlib import Path

import pytest

from boost_cli.core import output as out
from boost_cli.core import serve
from boost_cli.errors import BoostError


class _Tap:
    def __init__(self, path):
        self.path = path


def _patch_catalog(monkeypatch, *, installed=None, rules=None, workflows=None,
                   entries=None, find=None, taps=None):
    monkeypatch.setattr(serve.lockfile, "installed", lambda: installed or {})
    monkeypatch.setattr(serve.lockfile, "read",
                        lambda: {"version": 3, "skills": installed or {},
                                 "rules": rules or {},
                                 "workflows": workflows or {}})
    monkeypatch.setattr(serve.catalog, "all_entries", lambda: entries or [])
    monkeypatch.setattr(serve.catalog, "find", lambda n: (find or {}).get(n, []))
    monkeypatch.setattr(serve.registry, "list_taps", lambda: taps or [])
    # The served view is cached on a fingerprint of the on-disk catalogue,
    # which does not move between tests — so a test that swaps the catalogue
    # out from under it would otherwise assert against the previous test's.
    serve._ROWS_CACHE.clear()


class TestRoute:
    def test_root_serves_html(self, monkeypatch):
        _patch_catalog(monkeypatch, installed={"a": {"version": "1", "tap": "t"}})
        status, ctype, body = serve.route("/")
        assert status == 200
        assert ctype == "text/html; charset=utf-8"
        assert b"boost" in body and b'id="rows"' in body

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
        status, ctype, body = serve.route("/installed.json")
        assert status == 200 and ctype == "application/json"
        data = json.loads(body)
        assert data["version"] == 3 and "a" in data["skills"]

    def test_query_string_stripped(self, monkeypatch):
        _patch_catalog(monkeypatch)
        assert serve.route("/catalog.json?foo=bar")[0] == 200

    def test_only_the_first_question_mark_starts_the_query(self, monkeypatch):
        # A second `?` is legal in a query string, and the path is everything
        # before the FIRST one. Splitting on the last (or on all of them) makes
        # this 404 — the routing table never sees `/catalog.json`.
        _patch_catalog(monkeypatch)
        assert serve.route("/catalog.json?a=1?b=2")[0] == 200

    def test_only_surrounding_slashes_are_stripped_from_a_name(self, monkeypatch,
                                                               tmp_path):
        # `/skill/ghost/` must resolve to `ghost`, and the strip must take the
        # slash specifically: stripping whitespace instead leaves the trailing
        # slash in the name, and stripping a wider character set eats real
        # leading/trailing characters out of it.
        _patch_catalog(monkeypatch)
        monkeypatch.setattr(serve.store, "skill_store_dir",
                            lambda n: tmp_path / "missing")
        assert (json.loads(serve.route("/skill/ghost/")[2])["error"]
                == "no skill named 'ghost'")
        assert (json.loads(serve.route("/skill/XghostX/")[2])["error"]
                == "no skill named 'XghostX'")

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
        assert json.loads(body)["error"] == "invalid skill name"

    def test_skill_unknown_404(self, monkeypatch, tmp_path):
        _patch_catalog(monkeypatch)
        monkeypatch.setattr(serve.store, "skill_store_dir",
                            lambda n: tmp_path / "missing")
        status, _ctype, body = serve.route("/skill/ghost")
        assert status == 404
        assert json.loads(body)["error"] == "no skill named 'ghost'"

    def test_unknown_path_404(self, monkeypatch):
        _patch_catalog(monkeypatch)
        status, ctype, body = serve.route("/nope")
        # The content type is asserted on every JSON route, not just some: it is
        # what stops a body being interpreted as something else, and the two
        # routes that skipped it were the two whose type mutants survived.
        assert status == 404 and ctype == "application/json"
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
    """The page is now a shell and the rows arrive over fetch, so the three
    guarantees this class held moved rather than went away.

    They are re-pinned where they now live: the empty state and the counts on
    `/search.json`, and "a rule has no raw-content link" on the two facts that
    actually enforce it — the row says which kind it is, and there is no
    endpoint serving a rule's body regardless of what any client renders.
    """

    def test_the_shell_ships_an_empty_state_for_a_machine_with_nothing(self,
                                                                       monkeypatch):
        _patch_catalog(monkeypatch, installed={}, entries=[], taps=[])
        page = serve.serve_page()
        assert "no taps configured yet" in page
        assert "boost tap --defaults" in page

    def test_counts_come_from_the_search_endpoint(self, monkeypatch):
        _patch_catalog(
            monkeypatch,
            installed={"brainstorming": {"version": "1.4.0", "tap": "core"}},
            entries=[_entry("brainstorming", version="1.4.0"), _entry("other")],
            taps=[_Tap("a")])
        _, _, body = serve.route("/search.json")
        payload = json.loads(body)
        assert payload["total"] == 2
        rows = {r["name"]: r for r in payload["rows"]}
        assert rows["brainstorming"]["installed"] is True
        assert rows["brainstorming"]["version"] == "1.4.0"
        assert rows["other"]["installed"] is False

    def test_a_row_says_which_kind_it_is(self, monkeypatch):
        # The client links a name only when this reads "skill". Everything the
        # renderer needs to withhold a link is on the row.
        _patch_catalog(monkeypatch, entries=[
            _entry("brainstorming"), _entry("house-style", kind="rule"),
            _entry("ship-it", kind="workflow")])
        _, _, body = serve.route("/search.json")
        kinds = {r["name"]: r["kind"] for r in json.loads(body)["rows"]}
        assert kinds == {"brainstorming": "skill", "house-style": "rule",
                         "ship-it": "workflow"}

    def test_the_client_links_only_skills(self, monkeypatch):
        # Pins the branch itself. Losing it would put a /skill/ link on every
        # rule and workflow, and each one would answer 404.
        _patch_catalog(monkeypatch, entries=[])
        assert "r.kind==='skill'" in serve.serve_page()

    def test_no_endpoint_serves_a_rules_body_whatever_the_client_does(
            self, monkeypatch, tmp_path):
        # The half that does not depend on a renderer. `/skill/<name>` reads a
        # SKILL.md from the store or a tap; a rule has neither, so the raw
        # endpoint 404s for one however it is reached.
        _patch_catalog(monkeypatch, rules={"house-style": {"version": "1.0.0"}},
                       entries=[_entry("house-style", kind="rule")])
        monkeypatch.setattr(serve.store, "skill_store_dir",
                            lambda n: tmp_path / n)
        status, _, body = serve.route("/skill/house-style")
        assert status == 404
        assert b"no skill named" in body


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


# ------------------------------------------------- reflected request content

class TestRequestTextIsNeverEchoed:
    """A rejected path must not come back out in the response body.

    ``route`` unquotes the path before matching, so the segment after
    ``/skill/`` is arbitrary attacker-chosen bytes — angle brackets, quotes,
    whatever survives a URL. It used to be interpolated into the 404 body with
    ``%r``. The body is typed ``application/json``, which no current browser
    renders as HTML, so this was one missing header away from a live reflected
    XSS rather than a live one; ``--host 0.0.0.0`` is a documented flag, so the
    surface is not only localhost either. Neither half is worth keeping: the
    name is invalid *by definition* in this branch, so echoing it tells the
    caller nothing it did not just send.
    """

    PAYLOADS = (
        "<script>alert(1)</script>",
        "%3Cscript%3Ealert(1)%3C/script%3E",   # unquoted by route() first
        '"><img src=x onerror=alert(1)>',
        "a b<>&'\"",
    )

    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_an_invalid_name_is_not_reflected(self, monkeypatch, payload):
        _patch_catalog(monkeypatch)
        status, ctype, body = serve.route("/skill/" + payload)
        assert status == 404 and ctype == "application/json"
        assert json.loads(body) == {"error": "invalid skill name"}
        # Also assert on the raw bytes, so a future body that reflects the name
        # somewhere other than `error` still fails here. Not `"` — JSON spends
        # that on its own delimiters — but `<`, `>`, `&` and `'` never appear in
        # a structurally-correct body, so any occurrence came from the request.
        for ch in (b"<", b">", b"&", b"'"):
            assert ch not in body, (ch, body)
        assert b"alert" not in body and b"img" not in body

    def test_a_valid_but_unknown_name_is_still_named(self, monkeypatch, tmp_path):
        # The useful message survives where it is safe to keep: this branch is
        # reachable only for a name that already matched SKILL_NAME_RE, whose
        # charset ([A-Za-z0-9._-]) has nothing to escape.
        _patch_catalog(monkeypatch)
        monkeypatch.setattr(serve.store, "skill_store_dir",
                            lambda n: tmp_path / "missing")
        _status, _ctype, body = serve.route("/skill/ghost")
        assert json.loads(body)["error"] == "no skill named 'ghost'"

    def test_the_two_404s_stay_distinguishable(self, monkeypatch, tmp_path):
        # Collapsing both into one generic body would lose the only signal that
        # tells a typo from a name that is simply not installed.
        _patch_catalog(monkeypatch)
        monkeypatch.setattr(serve.store, "skill_store_dir",
                            lambda n: tmp_path / "missing")
        assert (json.loads(serve.route("/skill/ghost")[2])["error"]
                != json.loads(serve.route("/skill/gh ost")[2])["error"])



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
        # The traversal attempt is refused *and* not repeated back. This used to
        # assert `no skill named '../../etc/passwd'`, which pinned the echo in
        # place as if it were the contract.
        assert json.loads(body) == {"error": "invalid skill name"}
        assert b"passwd" not in body


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
        # Exact, and deliberately so: nosniff is a security header, and an
        # `in` assertion would keep passing if a later edit dropped it while
        # adding something else.
        assert calls["headers"] == [("Content-Type", "application/json"),
                                    ("Content-Length", "12"),
                                    ("X-Content-Type-Options", "nosniff")]
        assert calls["ended"] == 1
        assert h.wfile.data == b'{"ok": true}'
        assert dimmed == ["  GET /catalog.json → 200"]

    def test_nosniff_rides_on_every_status_and_type(self, monkeypatch):
        """Not just the 200 above — the error paths are the ones that matter.

        A 404 or 500 body is where a reflected detail is most likely to reappear
        later, and ``_send`` is the single choke point all four routes and the
        generic 500 in ``do_GET`` pass through. Pinned here so the header cannot
        be scoped to the success path by a later edit.
        """
        for status, ctype in ((404, "application/json"),
                              (500, "application/json"),
                              (200, "text/html; charset=utf-8"),
                              (200, "text/plain; charset=utf-8")):
            h, calls = self._handler(monkeypatch)
            monkeypatch.setattr(serve.out, "dim", lambda _m: None)
            h._send(status, ctype, b"x")
            assert ("X-Content-Type-Options", "nosniff") in calls["headers"], \
                (status, ctype)

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


# ── the searchable, tagged catalogue ──────────────────────────────────────

def _entry(name, *, tap="o/r", kind="skill", desc="", meta=None, version="1.0.0",
           curated=False):
    return {"name": name, "description": desc, "version": version, "tap": tap,
            "curated": curated, "kind": kind, "rel_dir": ".",
            "skill_md": name + "/SKILL.md", "meta": meta or {},
            "search_blob": (name + " " + desc).lower()}


class TestEntryTags:
    """Tags are facets a reader can filter on, not decoration.

    Every value is namespaced (`kind:`, `tap:`, `topic:`, `tag:`) so a filter
    can be applied per namespace and two namespaces can never collide — a tap
    literally named "skill" would otherwise be indistinguishable from the kind.
    """

    def test_kind_and_tap_are_always_present(self):
        tags = serve.entry_tags(_entry("a", tap="acme/skills", kind="rule"))
        assert "kind:rule" in tags
        assert "tap:acme/skills" in tags

    def test_topic_comes_from_the_curated_registry_taxonomy(self):
        # registries.json is where a repo's category is decided, and it is
        # decided from the names of the items it ships — not its README. That
        # judgement is already made and test-pinned; this surfaces it.
        tags = serve.entry_tags(_entry("a", tap="acme/skills"),
                                categories={"acme/skills": "ui"})
        assert "topic:ui" in tags

    def test_a_tap_with_no_curated_category_gets_no_topic(self):
        tags = serve.entry_tags(_entry("a", tap="who/dis"), categories={})
        assert not [t for t in tags if t.startswith("topic:")]

    def test_installed_is_a_tag_because_it_is_the_first_thing_you_filter_on(self):
        e = _entry("a")
        assert "state:installed" in serve.entry_tags(e, installed={"a"})
        assert "state:installed" not in serve.entry_tags(e, installed=set())

    def test_frontmatter_tags_come_through_namespaced(self):
        e = _entry("a", meta={"tags": ["Testing", "ci"]})
        tags = serve.entry_tags(e)
        assert "tag:testing" in tags and "tag:ci" in tags

    def test_a_comma_string_of_tags_is_split(self):
        # Frontmatter is third-party YAML: `tags: a, b` is as common as a list.
        e = _entry("a", meta={"tags": "alpha, beta"})
        tags = serve.entry_tags(e)
        assert "tag:alpha" in tags and "tag:beta" in tags

    @pytest.mark.parametrize("bad", [None, 5, {"x": 1}, [None, ""], ["  "]])
    def test_junk_frontmatter_tags_never_raise(self, bad):
        # `meta` is whatever a stranger's YAML parsed to. A serving path that
        # raises on it takes the whole page down for one bad item in one tap.
        tags = serve.entry_tags(_entry("a", meta={"tags": bad}))
        assert "kind:skill" in tags

    def test_tags_are_sorted_and_de_duplicated(self):
        e = _entry("a", meta={"tags": ["ci", "ci", "CI"]})
        tags = serve.entry_tags(e)
        assert tags == sorted(set(tags))
        assert tags.count("tag:ci") == 1


class TestCatalogRows:
    def test_a_row_carries_what_the_table_renders(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("alpha", desc="does a thing")],
                       installed={"alpha": {}})
        (row,) = serve.catalog_rows()
        assert row["name"] == "alpha"
        assert row["description"] == "does a thing"
        assert row["installed"] is True
        assert "kind:skill" in row["tags"]

    def test_rules_and_workflows_count_as_installed_too(self, monkeypatch):
        # lockfile.installed() is skills only. A rule shown as "available"
        # while it is materialized into the user's CLAUDE.md is a lie about
        # the most invasive kind boost installs.
        _patch_catalog(monkeypatch,
                       entries=[_entry("r", kind="rule"), _entry("w", kind="workflow")],
                       rules={"r": {}}, workflows={"w": {}})
        rows = {r["name"]: r for r in serve.catalog_rows()}
        assert rows["r"]["installed"] is True
        assert rows["w"]["installed"] is True


class TestFacetCounts:
    def test_facets_are_grouped_by_namespace_and_ranked_by_count(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[
            _entry("a", kind="skill"), _entry("b", kind="skill"),
            _entry("c", kind="rule")])
        facets = serve.facet_counts(serve.catalog_rows())
        assert facets["kind"][0] == ("skill", 2)
        assert ("rule", 1) in facets["kind"]

    def test_an_empty_catalog_yields_empty_facets(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[])
        assert serve.facet_counts(serve.catalog_rows()) == {}


class TestSearchRows:
    def _rows(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[
            _entry("pytest-runner", kind="skill", tap="a/b", desc="run tests"),
            _entry("commit-style", kind="rule", tap="c/d", desc="commit messages"),
            _entry("deploy", kind="workflow", tap="a/b", desc="ship it")])
        return serve.catalog_rows()

    def test_an_empty_query_returns_everything(self, monkeypatch):
        rows = self._rows(monkeypatch)
        assert len(serve.search_rows(rows, "")) == 3

    def test_a_query_narrows_to_matches(self, monkeypatch):
        rows = self._rows(monkeypatch)
        names = [r["name"] for r in serve.search_rows(rows, "commit")]
        assert names == ["commit-style"]

    def test_a_tag_filter_narrows_without_a_query(self, monkeypatch):
        rows = self._rows(monkeypatch)
        got = serve.search_rows(rows, "", tags=["kind:rule"])
        assert [r["name"] for r in got] == ["commit-style"]

    def test_tags_across_namespaces_are_ANDed(self, monkeypatch):
        # Two facets from different namespaces narrow; ORing them would make
        # every extra chip widen the result, which reads as a broken filter.
        rows = self._rows(monkeypatch)
        assert serve.search_rows(rows, "", tags=["kind:rule", "tap:a/b"]) == []
        got = serve.search_rows(rows, "", tags=["kind:workflow", "tap:a/b"])
        assert [r["name"] for r in got] == ["deploy"]

    def test_a_query_and_a_tag_compose(self, monkeypatch):
        rows = self._rows(monkeypatch)
        assert serve.search_rows(rows, "commit", tags=["kind:skill"]) == []

    def test_the_limit_bounds_rows_returned(self, monkeypatch):
        rows = self._rows(monkeypatch)
        assert len(serve.search_rows(rows, "", limit=2)) == 2


class TestGraphData:
    """The graph is of the *catalogue*, so its nodes are taps.

    A node per item would be 10k nodes on a real machine — unrenderable, and
    it would draw the one structure nobody needs (items are already a list).
    What a tap-level graph shows is the structure that IS invisible in a
    table: which registries mirror each other. `code-reviewer` ships from 13
    different taps, and that overlap is the edge.
    """

    def _rows(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[
            _entry("shared", tap="a/b"), _entry("only-a", tap="a/b"),
            _entry("shared", tap="c/d"), _entry("only-c", tap="c/d"),
            _entry("lonely", tap="e/f")])
        return serve.catalog_rows()

    def test_one_node_per_tap_sized_by_item_count(self, monkeypatch):
        g = serve.graph_data(self._rows(monkeypatch))
        sizes = {n["id"]: n["size"] for n in g["nodes"]}
        assert sizes == {"a/b": 2, "c/d": 2, "e/f": 1}

    def test_an_edge_is_a_shared_item_name_and_carries_its_weight(self, monkeypatch):
        g = serve.graph_data(self._rows(monkeypatch))
        assert len(g["links"]) == 1
        (edge,) = g["links"]
        assert {edge["source"], edge["target"]} == {"a/b", "c/d"}
        assert edge["weight"] == 1

    def test_a_tap_sharing_nothing_still_gets_a_node(self, monkeypatch):
        # Dropping isolated nodes would hide exactly the registries that are
        # unique, which are the interesting ones.
        g = serve.graph_data(self._rows(monkeypatch))
        assert "e/f" in {n["id"] for n in g["nodes"]}

    def test_no_self_edges(self, monkeypatch):
        # Two items with the same name inside ONE tap (an agent mirror) is the
        # single most common shape in the catalog. It is not an overlap.
        _patch_catalog(monkeypatch, entries=[
            _entry("dup", tap="a/b"), _entry("dup", tap="a/b")])
        g = serve.graph_data(serve.catalog_rows())
        assert g["links"] == []

    def test_every_node_lands_in_a_community(self, monkeypatch):
        g = serve.graph_data(self._rows(monkeypatch))
        assert all("community" in n for n in g["nodes"])
        assert {n["id"] for n in g["nodes"]} == {"a/b", "c/d", "e/f"}

    def test_connected_taps_share_a_community(self, monkeypatch):
        g = serve.graph_data(self._rows(monkeypatch))
        by_id = {n["id"]: n["community"] for n in g["nodes"]}
        assert by_id["a/b"] == by_id["c/d"]
        assert by_id["e/f"] != by_id["a/b"]

    def test_it_is_deterministic(self, monkeypatch):
        rows = self._rows(monkeypatch)
        assert serve.graph_data(rows) == serve.graph_data(rows)

    def test_an_empty_catalog_is_an_empty_graph_not_a_crash(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[])
        g = serve.graph_data(serve.catalog_rows())
        assert g["nodes"] == [] and g["links"] == []


class TestTheNewEndpoints:
    def test_graph_json(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("a")])
        status, ctype, body = serve.route("/graph.json")
        assert status == 200 and ctype == "application/json"
        assert "nodes" in json.loads(body)

    def test_search_json_honours_the_query(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("alpha"), _entry("beta")])
        _, _, body = serve.route("/search.json?q=alpha")
        assert [r["name"] for r in json.loads(body)["rows"]] == ["alpha"]

    def test_search_json_honours_repeated_tag_params(self, monkeypatch):
        _patch_catalog(monkeypatch,
                       entries=[_entry("a", kind="rule"), _entry("b", kind="skill")])
        _, _, body = serve.route("/search.json?tag=kind:rule")
        assert [r["name"] for r in json.loads(body)["rows"]] == ["a"]

    def test_search_json_reports_facets_and_a_total(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("a"), _entry("b")])
        _, _, body = serve.route("/search.json")
        payload = json.loads(body)
        assert payload["total"] == 2
        assert "kind" in payload["facets"]

    def test_a_bare_search_path_still_answers(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("a")])
        status, _, _ = serve.route("/search.json")
        assert status == 200


class TestThePageIsSelfContained:
    """`boost serve` binds a socket on a developer's machine. Every byte the
    page needs has to come from that socket.

    A CDN reference would make the catalogue silently blank on a plane, and it
    would hand a third party a request per page view naming the port a
    developer tool is listening on.
    """

    def test_no_remote_asset_is_referenced(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("a")])
        page = serve.serve_page()
        for scheme in ("http://", "https://", "//cdn", "integrity="):
            assert scheme not in page, scheme

    def test_both_tabs_are_present(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("a")])
        page = serve.serve_page().lower()
        assert "catalogue" in page or "catalog" in page
        assert "graph" in page

    def test_the_page_embeds_no_catalog_data(self, monkeypatch):
        # The rows arrive over fetch, never interpolated into a <script>.
        # A description is third-party text, and one containing `</script>`
        # closes the block and turns the rest into markup — the exact class of
        # bug the 404 reflection was. Not embedding it removes the class.
        _patch_catalog(monkeypatch, entries=[
            _entry("pwned", desc="</script><img src=x onerror=alert(1)>")])
        page = serve.serve_page()
        assert "onerror" not in page
        assert "pwned" not in page


class TestTheViewIsCachedOnTheCatalogueMoving:
    """71,695 rows take 0.54s to build and 0.12s to facet on a real machine.

    The search box issues a request per keystroke, so rebuilding per request
    makes the page unusable at exactly the catalogue size that makes it worth
    having — and caching forever serves a catalogue the machine stopped having
    the moment `boost update` ran in another terminal.
    """

    def setup_method(self):
        serve._ROWS_CACHE.clear()

    def test_a_second_request_does_not_rebuild(self, monkeypatch):
        calls = []
        monkeypatch.setattr(serve.catalog, "all_entries",
                            lambda: calls.append(1) or [_entry("a")])
        _patch_catalog(monkeypatch, entries=[_entry("a")])
        monkeypatch.setattr(serve.catalog, "all_entries",
                            lambda: calls.append(1) or [_entry("a")])
        serve.cached_view()
        serve.cached_view()
        assert len(calls) == 1

    def test_a_changed_fingerprint_rebuilds(self, monkeypatch):
        calls = []
        _patch_catalog(monkeypatch, entries=[_entry("a")])
        monkeypatch.setattr(serve.catalog, "all_entries",
                            lambda: calls.append(1) or [_entry("a")])
        monkeypatch.setattr(serve, "_catalog_fingerprint", lambda: (1, 1, 1))
        serve.cached_view()
        monkeypatch.setattr(serve, "_catalog_fingerprint", lambda: (1, 2, 1))
        serve.cached_view()
        assert len(calls) == 2

    def test_an_unreadable_cache_dir_is_a_fingerprint_not_a_crash(self, monkeypatch):
        def boom(*_a, **_k):
            raise OSError("gone")
        monkeypatch.setattr(serve.paths, "cache_dir", boom)
        assert serve._catalog_fingerprint() == ()

    def test_the_graph_rides_the_same_signal(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("a")])
        monkeypatch.setattr(serve, "_catalog_fingerprint", lambda: (1, 1, 1))
        first = serve.cached_graph()
        assert serve.cached_graph() is first
        monkeypatch.setattr(serve, "_catalog_fingerprint", lambda: (2, 2, 2))
        assert serve.cached_graph() is not first


class TestTheGraphStaysLegibleAtRealScale:
    """Measured on a real 445-tap machine: 300 nodes carry 5,181 overlaps, and
    55% of those are a single shared name — often a coincidence on a generic
    one. Drawn in full it is a hairball; the strongest few hundred are a graph.
    """

    def test_only_the_strongest_edges_are_drawn(self, monkeypatch):
        entries = []
        # 40 taps, each sharing a name with tap 0 — 40 edges before the cap.
        for i in range(40):
            entries.append(_entry("shared-%d" % i, tap="hub/h"))
            entries.append(_entry("shared-%d" % i, tap="spoke/%d" % i))
        _patch_catalog(monkeypatch, entries=entries)
        monkeypatch.setattr(serve, "GRAPH_EDGES", 10)
        g = serve.graph_data(serve.catalog_rows())
        assert len(g["links"]) == 10
        assert g["graph"]["overlaps"] == 40, "the true total stays reported"
        assert g["graph"]["links_shown"] == 10

    def test_the_node_cap_reports_what_it_dropped(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[
            _entry("a", tap="t/%d" % i) for i in range(9)])
        monkeypatch.setattr(serve, "GRAPH_NODES", 4)
        g = serve.graph_data(serve.catalog_rows())
        assert len(g["nodes"]) == 4
        assert g["graph"]["taps"] == 9 and g["graph"]["dropped"] == 5


class TestJsonBodiesCannotBeReadAsMarkup:
    """Every JSON body here carries third-party text — a name, a description
    and a tap all come from whatever repos the reader has tapped.

    Correct `Content-Type` plus `nosniff` is what makes that safe today. This
    is the layer that survives either one being got wrong: by a proxy, by a
    future route that types a body wrong, or by someone saving the response and
    opening it in a browser.
    """

    @pytest.mark.parametrize("ch", ["<", ">", "&"])
    def test_the_markup_characters_never_appear_raw(self, monkeypatch, ch):
        _patch_catalog(monkeypatch, entries=[
            _entry("x", desc="</script><img src=x onerror=alert(1)>&lt;")])
        for path in ("/search.json", "/catalog.json", "/graph.json"):
            body = serve.route(path)[2]
            assert ch.encode() not in body, (path, ch)

    def test_the_document_still_parses_to_the_same_object(self, monkeypatch):
        payload = {"desc": "a <b> & </script> c", "n": [1, 2]}
        assert json.loads(serve._json_body(payload)) == payload

    def test_a_404_body_is_inert_too(self, monkeypatch):
        # The generic misses go through the same helper, so a route added later
        # inherits this rather than having to remember it.
        _patch_catalog(monkeypatch)
        assert b"<" not in serve.route("/nope")[2]


class TestTheRequestIsNeverReflectedIntoTheResponse:
    """The falsifiable half of the standing XSS finding on this module.

    Snyk traces request URL -> `route` -> `search_rows` -> body -> `write` and
    calls it reflected XSS. What the parameters actually do is *select rows*;
    nothing in the response carries the caller's text. That is a claim a test
    can settle, and it is the claim the finding rests on — so it is pinned here
    rather than argued in a comment.

    The one place a request value IS echoed is the `/skill/<name>` 404, and it
    is reachable only after `SKILL_NAME_RE.fullmatch`, whose charset is
    [A-Za-z0-9._-] — nothing in it can close a tag or a quote (see #489).
    """

    PAYLOADS = ("<script>alert(1)</script>", "\"><img src=x onerror=alert(1)>",
                "javascript:alert(1)", "');alert(1);//", "</script><svg onload=1>")

    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_a_crafted_query_comes_back_in_nobody(self, monkeypatch, payload):
        _patch_catalog(monkeypatch, entries=[_entry("real-item", desc="ok")])
        body = serve.route("/search.json?q=" + urllib.parse.quote(payload))[2]
        for fragment in ("script", "onerror", "onload", "alert", "img", "svg"):
            assert fragment.encode() not in body, (payload, fragment)

    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_a_crafted_tag_comes_back_in_nobody(self, monkeypatch, payload):
        _patch_catalog(monkeypatch, entries=[_entry("real-item")])
        body = serve.route("/search.json?tag=" + urllib.parse.quote(payload))[2]
        for fragment in ("script", "onerror", "onload", "alert"):
            assert fragment.encode() not in body, (payload, fragment)

    def test_an_unknown_path_does_not_name_itself(self, monkeypatch):
        _patch_catalog(monkeypatch)
        body = serve.route("/<script>alert(1)</script>")[2]
        assert json.loads(body) == {"error": "not found"}

    def test_the_one_echo_is_charset_bounded(self, monkeypatch, tmp_path):
        # `/skill/<name>` names the name — but only past the regex. Anything
        # that could break out is rejected before that branch is reachable.
        _patch_catalog(monkeypatch)
        monkeypatch.setattr(serve.store, "skill_store_dir",
                            lambda n: tmp_path / "missing")
        assert (json.loads(serve.route("/skill/<script>")[2])["error"]
                == "invalid skill name")


class TestTheGraphIsNodeLinkJsonRatherThanASimilarShape:
    """`/graph.json` is loadable by `networkx.node_link_graph`, and by
    graphify's tooling, rather than merely resembling them.

    graphify's own `graph.json` is NetworkX node-link: `directed`,
    `multigraph`, a graph-level attribute dict, `nodes` and — the one that
    actually breaks a loader — `links`, not `edges`. Pinned because "similar
    shape" and "same format" look identical in a screenshot and differ the
    moment anyone tries to feed one to the other.
    """

    def test_it_carries_the_node_link_envelope(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[_entry("a", tap="t/1")])
        g = json.loads(serve.route("/graph.json")[2])
        assert g["directed"] is False and g["multigraph"] is False
        assert set(g) == {"directed", "multigraph", "graph", "nodes", "links"}

    def test_graph_level_metadata_lives_in_the_graph_dict(self, monkeypatch):
        # networkx round-trips this into `G.graph`, which is where graph-wide
        # attributes belong — a sibling "stats" key would be dropped.
        _patch_catalog(monkeypatch, entries=[_entry("a", tap="t/1")])
        g = json.loads(serve.route("/graph.json")[2])
        for key in ("taps", "shown", "dropped", "items", "overlaps"):
            assert key in g["graph"], key

    def test_links_name_their_endpoints_by_node_id(self, monkeypatch):
        _patch_catalog(monkeypatch, entries=[
            _entry("shared", tap="a/b"), _entry("shared", tap="c/d")])
        g = json.loads(serve.route("/graph.json")[2])
        ids = {n["id"] for n in g["nodes"]}
        for link in g["links"]:
            assert link["source"] in ids and link["target"] in ids
            assert link["weight"] >= 1 and link["relation"]


class TestTheTaggingEdgesTheCoverageReportFound:
    """Three branches the suite reached around but never through. Each is a
    live path on real data, and an unexecuted branch is an unkilled mutant."""

    def test_a_non_dict_meta_yields_no_frontmatter_tags(self):
        # `meta` is whatever a stranger's YAML parsed to — a bare string or
        # null frontmatter both land here, and neither is a mapping.
        for meta in (None, "just a string", ["a", "list"], 7):
            tags = serve.entry_tags(_entry("a", meta=meta))
            assert tags == ["kind:skill", "tap:o/r"], meta

    def test_a_curated_entry_is_tagged_as_one(self):
        assert "state:curated" in serve.entry_tags(_entry("a", curated=True))
        assert "state:curated" not in serve.entry_tags(_entry("a", curated=False))

    def test_unreadable_registry_data_reads_as_no_categories(self, monkeypatch):
        # A page that failed to render because a shipped data file moved would
        # be a worse outcome than one with no topic facet.
        monkeypatch.setattr(serve, "_CATEGORIES", None)
        monkeypatch.setattr(serve.Path, "read_text",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("gone")))
        assert serve.registry_categories() == {}
        monkeypatch.setattr(serve, "_CATEGORIES", None)

    def test_malformed_registry_json_reads_as_no_categories(self, monkeypatch):
        monkeypatch.setattr(serve, "_CATEGORIES", None)
        monkeypatch.setattr(serve.Path, "read_text", lambda *a, **k: "{not json")
        assert serve.registry_categories() == {}
        monkeypatch.setattr(serve, "_CATEGORIES", None)
