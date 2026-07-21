"""Unit tests: boost_cli/core/mcp.py — the extensible MCP tool registry.

The registry is the Phase-3 "MCP as a hub" seam: tools self-register a spec +
handler, and the JSON-RPC server iterates it. These tests pin registration
order, spec shape, dispatch, and the unknown-tool contract so the mutation gate
has teeth.
"""
from __future__ import annotations

import io
import json

import pytest

from boost_cli.core import mcp
from boost_cli.errors import BoostError


def _ok(_args):
    return "ok", False


class TestRegister:
    def test_spec_shape_and_order(self):
        reg = mcp.Registry()
        reg.register("a", "does a", {"type": "object"}, _ok)
        reg.register("b", "does b", {"type": "object", "properties": {}},
                     lambda a: ("b!", False))
        assert reg.names() == ["a", "b"]                 # registration order
        specs = reg.specs()
        assert [s["name"] for s in specs] == ["a", "b"]
        assert specs[0] == {"name": "a", "description": "does a",
                            "inputSchema": {"type": "object"}}
        assert specs[1]["inputSchema"] == {"type": "object", "properties": {}}

    def test_specs_preserve_insertion_not_sorted(self):
        reg = mcp.Registry()
        for n in ("zebra", "alpha", "mid"):
            reg.register(n, n, {"type": "object"}, _ok)
        assert reg.names() == ["zebra", "alpha", "mid"]  # not alphabetized

    def test_empty_name_rejected(self):
        reg = mcp.Registry()
        with pytest.raises(ValueError, match="non-empty"):
            reg.register("", "d", {"type": "object"}, _ok)

    def test_duplicate_name_rejected(self):
        reg = mcp.Registry()
        reg.register("a", "d", {"type": "object"}, _ok)
        with pytest.raises(ValueError, match="duplicate"):
            reg.register("a", "d2", {"type": "object"}, _ok)
        assert reg.names() == ["a"]                       # first wins, unchanged

    def test_decorator_registers_and_returns_fn(self):
        reg = mcp.Registry()

        @reg.tool("greet", "say hi", {"type": "object"})
        def greet(args):
            return "hi %s" % args.get("who", "?"), False

        assert reg.has("greet")
        assert callable(greet)                            # returned unchanged
        assert greet({"who": "x"}) == ("hi x", False)
        assert reg.call("greet", {"who": "y"}) == ("hi y", False)


class TestDispatch:
    def test_call_routes_to_handler(self):
        reg = mcp.Registry()
        seen = {}
        reg.register("echo", "d", {"type": "object"},
                     lambda a: (seen.update(a) or "done", bool(a.get("bad"))))
        assert reg.call("echo", {"x": 1}) == ("done", False)
        assert seen == {"x": 1}
        assert reg.call("echo", {"bad": 1})[1] is True    # is_error propagates

    def test_unknown_tool_is_none_false(self):
        reg = mcp.Registry()
        reg.register("a", "d", {"type": "object"}, _ok)
        assert reg.call("nope", {}) == (None, False)
        assert reg.has("nope") is False
        assert reg.has("a") is True

    def test_handler_none_text_passes_through(self):
        reg = mcp.Registry()
        reg.register("silent", "d", {"type": "object"}, lambda a: (None, True))
        assert reg.call("silent", {}) == (None, True)     # not masked as unknown


def _reg_with(name="echo", handler=None):
    reg = mcp.Registry()
    reg.register(name, "d", {"type": "object"},
                 handler or (lambda a: ("hi %s" % a.get("who", "?"), False)))
    return reg


class TestHandleRequest:
    def test_notification_returns_none(self):
        # no "id" -> a notification, the server sends nothing back
        assert mcp.handle_request({"method": "notifications/initialized"},
                                  version="1.0", registry=_reg_with()) is None

    def test_initialize(self):
        resp = mcp.handle_request({"id": 1, "method": "initialize"},
                                  version="9.9.9", registry=_reg_with())
        assert resp["jsonrpc"] == "2.0" and resp["id"] == 1
        assert resp["result"]["protocolVersion"] == mcp.PROTOCOL_VERSION
        assert resp["result"]["capabilities"] == {"tools": {}}
        assert resp["result"]["serverInfo"] == {"name": "boost", "version": "9.9.9"}

    def test_protocol_version_constant(self):
        assert mcp.PROTOCOL_VERSION == "2024-11-05"

    def test_ping(self):
        resp = mcp.handle_request({"id": 2, "method": "ping"},
                                  version="1.0", registry=_reg_with())
        assert resp["result"] == {} and resp["id"] == 2

    def test_tools_list_echoes_registry_specs(self):
        reg = _reg_with()
        resp = mcp.handle_request({"id": 3, "method": "tools/list"},
                                  version="1.0", registry=reg)
        assert resp["result"] == {"tools": reg.specs()}

    def test_tools_call_success(self):
        resp = mcp.handle_request(
            {"id": 4, "method": "tools/call",
             "params": {"name": "echo", "arguments": {"who": "x"}}},
            version="1.0", registry=_reg_with())
        assert resp["result"] == {"content": [{"type": "text", "text": "hi x"}]}
        assert "isError" not in resp["result"]

    def test_tools_call_is_error_flag(self):
        reg = _reg_with(handler=lambda a: ("boom", True))
        resp = mcp.handle_request(
            {"id": 5, "method": "tools/call", "params": {"name": "echo"}},
            version="1.0", registry=reg)
        assert resp["result"]["content"][0]["text"] == "boom"
        assert resp["result"]["isError"] is True

    def test_tools_call_unknown_tool(self):
        resp = mcp.handle_request(
            {"id": 6, "method": "tools/call", "params": {"name": "ghost"}},
            version="1.0", registry=_reg_with())
        assert resp["error"] == {"code": -32602,
                                 "message": "unknown tool 'ghost'"}
        assert "result" not in resp

    def test_tools_call_boost_error_becomes_error_result(self):
        def boom(_a):
            raise BoostError("nope", hint="try that")
        resp = mcp.handle_request(
            {"id": 7, "method": "tools/call", "params": {"name": "echo"}},
            version="1.0", registry=_reg_with(handler=boom))
        assert resp["result"]["isError"] is True
        assert resp["result"]["content"][0]["text"] == "Error: nope\nhint: try that"

    def test_tools_call_boost_error_without_hint(self):
        def boom(_a):
            raise BoostError("bare")
        resp = mcp.handle_request(
            {"id": 8, "method": "tools/call", "params": {"name": "echo"}},
            version="1.0", registry=_reg_with(handler=boom))
        assert resp["result"]["content"][0]["text"] == "Error: bare"

    def test_tools_call_generic_exception_kept_alive(self):
        def boom(_a):
            raise RuntimeError("kaboom")
        resp = mcp.handle_request(
            {"id": 9, "method": "tools/call", "params": {"name": "echo"}},
            version="1.0", registry=_reg_with(handler=boom))
        assert resp["result"]["isError"] is True
        assert "kaboom" in resp["result"]["content"][0]["text"]

    def test_unknown_method(self):
        resp = mcp.handle_request({"id": 10, "method": "no/such"},
                                  version="1.0", registry=_reg_with())
        assert resp["error"] == {"code": -32601,
                                 "message": "method not found: no/such"}

    def test_missing_arguments_default_empty(self):
        seen = {}
        reg = _reg_with(handler=lambda a: (seen.update(a) or "ok", False))
        mcp.handle_request(
            {"id": 11, "method": "tools/call", "params": {"name": "echo"}},
            version="1.0", registry=reg)
        assert seen == {}   # no 'arguments' -> {}


class TestServeStdio:
    def _run(self, lines, registry=None, version="1.0"):
        out = io.StringIO()
        code = mcp.serve_stdio(registry or _reg_with(), version=version,
                               stdin=io.StringIO("".join(l + "\n" for l in lines)),
                               stdout=out)
        return code, [json.loads(x) for x in out.getvalue().splitlines()]

    def test_eof_returns_zero_with_no_output(self):
        code, resps = self._run([])
        assert code == 0 and resps == []

    def test_blank_lines_skipped(self):
        _code, resps = self._run(["", "   ", json.dumps({"id": 1, "method": "ping"})])
        assert [r["id"] for r in resps] == [1]

    def test_notification_produces_no_line(self):
        _code, resps = self._run([
            json.dumps({"method": "notifications/initialized"}),
            json.dumps({"id": 1, "method": "ping"}),
        ])
        assert len(resps) == 1 and resps[0]["id"] == 1

    def test_invalid_json_emits_parse_error(self):
        _code, resps = self._run(["this is not json",
                                 json.dumps({"id": 2, "method": "ping"})])
        assert resps[0]["error"]["code"] == -32700
        assert resps[0]["id"] is None
        assert resps[1]["id"] == 2

    def test_full_sequence_and_version_passthrough(self):
        _code, resps = self._run([
            json.dumps({"id": 1, "method": "initialize"}),
            json.dumps({"id": 2, "method": "tools/list"}),
            json.dumps({"id": 3, "method": "tools/call",
                        "params": {"name": "echo", "arguments": {"who": "z"}}}),
        ], version="7.7.7")
        assert resps[0]["result"]["serverInfo"]["version"] == "7.7.7"
        assert [t["name"] for t in resps[1]["result"]["tools"]] == ["echo"]
        assert resps[2]["result"]["content"][0]["text"] == "hi z"

    def test_send_failure_stops_loop(self):
        class BrokenOut:
            def write(self, _s):
                raise BrokenPipeError()
            def flush(self):
                pass
        code = mcp.serve_stdio(
            _reg_with(), version="1.0",
            stdin=io.StringIO(json.dumps({"id": 1, "method": "ping"}) + "\n"),
            stdout=BrokenOut())
        assert code == 0   # a dead stdout ends the loop cleanly
