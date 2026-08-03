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

    def test_initialize_returns_server_instructions(self):
        # MCP hosts load `instructions` into the agent's context — this is where
        # boost earns the "check for a skill before doing the work" reflex.
        resp = mcp.handle_request({"id": 1, "method": "initialize"},
                                  version="9.9.9", registry=_reg_with())
        instr = resp["result"]["instructions"]
        assert instr.startswith(mcp.INSTRUCTIONS)
        low = instr.lower()
        # ONE trigger, and it must be observable rather than a judgement call.
        # "Non-trivial work" was the old framing and it lost to its own escape
        # hatch: deciding a task is non-trivial takes judgement, while "this
        # turn looks small" is free — and every turn looks small when it opens.
        # A task having a NAME is something an agent can pattern-match without
        # deciding anything.
        assert "has a name" in low
        assert "boost_list" in instr and "boost_search" in instr
        # The cost has to be stated. An unknown-cost call with an unknown hit
        # rate gets skipped, however good the pitch above it.
        assert "read-only" in low
        # ...as does the miss protocol. Without it a zero-result search reads as
        # a wasted turn, so the next task skips the check to avoid repeating it.
        assert "finding nothing" in low
        # Non-capturing, and load-bearing rather than merely polite: an agent
        # that expects a hit to seize the task is safer not looking.
        assert "the task stays yours" in low
        # Escalation still has to be caught — both other moments fire at a task
        # boundary, so a turn that starts small and grows is never re-checked.
        assert "turns out to be a large one" in low
        # ...and it must stay bounded, or an agent learns to ignore all of it.
        assert "skip it for a question" in low

    def test_instructions_lead_with_using_a_skill_not_authoring_one(self):
        # Authoring used to be a co-equal numbered trigger, which cost the
        # instructions their point: boost's primary benefit is finding a skill
        # for the task in front of you, and "am I about to write a skill?" is
        # both rarer and a different question. It survives only as a clause on
        # boost_search's own description, never as a trigger here.
        low = mcp.INSTRUCTIONS.lower()
        assert "before you write a new skill" not in low
        assert "authoring" not in low

    def test_instructions_do_not_understate_what_a_search_costs(self):
        # The first version of this block said both tools "take about a second".
        # boost_list does; boost_search does NOT -- it reranks with an LLM by
        # default, measured at ~12s median against 0.10s without. Shipping a
        # false cost in the text whose whole job is making the tool worth
        # reaching for is the one lie that discredits the rest of it, and an
        # agent that budgeted a second gets a surprise instead of a decision.
        low = mcp.INSTRUCTIONS.lower()
        assert "about a second" not in low
        # State it, and state why it is worth paying rather than just warning.
        assert "seconds" in low
        assert "ranks them with an llm" in low or "reranks" in low
        assert "read-only" in low          # the part that WAS true stays

    def test_instructions_quote_no_retrieval_percentage(self):
        # "95% of the time against 79% without it" was real and measured — over
        # the SIX-repo corpus. tests/eval/baseline.json records BM25 hit@1 at
        # 0.4725 for the twenty-repo corpus that replaced it because six was
        # unrealistically small, so 79% overstated today's baseline by 31
        # points at the one moment an agent cannot check it. #442 kept these
        # figures out of every tool description for exactly this reason and
        # left them here; this closes the gap rather than re-deriving it.
        low = mcp.INSTRUCTIONS.lower()
        for stale in ("95%", "79%", "0.945", "0.791"):
            assert stale not in low, (
                "INSTRUCTIONS quotes %r, a six-repo-corpus figure the eval "
                "gate no longer measures" % stale)
        # The claim that survives is the mechanism, which is what an agent
        # actually acts on and what the eval gate does floor.
        assert "reranks" in low

    def test_instructions_do_not_call_the_catalog_vetted(self):
        # The catalog is indexed, not reviewed. #442 struck "vetted" from every
        # tool description and missed this copy, which implies the same
        # guarantee nobody performs.
        assert "vetted" not in mcp.INSTRUCTIONS.lower()

    def test_instructions_and_tool_descriptions_agree_on_the_cost(self):
        # Two surfaces, one connect: an agent sees INSTRUCTIONS and the
        # boost_search description in the same context window, so a disagreement
        # about what a search costs is visible in a way a single wrong number
        # is not. #442 set the descriptions to "10-15 seconds" while this text
        # still said "a few seconds".
        from boost_cli.commands import configuration
        desc = {s["name"]: s["description"] for s in configuration.REGISTRY.specs()}
        assert "10-15 seconds" in mcp.INSTRUCTIONS
        assert "10-15 seconds" in desc["boost_search"]
        assert "a few seconds" not in mcp.INSTRUCTIONS.lower()

    def test_instructions_still_separate_the_free_tool_from_the_slow_one(self):
        # boost_list really is instant, and collapsing the two costs into one
        # number is what produced the wrong claim. Naming them separately is
        # what lets an agent reach for the cheap one freely.
        low = mcp.INSTRUCTIONS.lower()
        assert "boost_list" in low and "boost_search" in low
        assert "instant" in low

    def test_instructions_route_search_straight_to_install(self):
        # boost_info sat between search and install in the advertised flow, but
        # search already returns each hit's description — the only field that
        # changes an install decision — so the hop bought a round-trip and a
        # decision point and nothing else. It stays a registered tool for
        # looking up a name from elsewhere; it is not a step.
        assert "boost_search -> boost_install" in mcp.INSTRUCTIONS
        assert "boost_info" not in mcp.INSTRUCTIONS

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


class TestEngineNote:
    """`initialize` must tell the agent which retrieval engine it is talking to.

    An agent that cannot distinguish a keyword index from a semantic one phrases
    queries for the wrong engine — the exact failure the natural-language eval
    set measures, where BM25 hit@1 collapses on paraphrased queries. The note is
    appended at connect time because the answer is machine state, not build state.
    """

    def test_bm25_only_says_so_and_names_the_upgrade(self, sandbox, monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "status",
                            lambda: {"ready": False, "reason": "no-store"})
        note = mcp.engine_note()
        assert "BM25 keyword matching only" in note
        assert "boost reindex --dense" in note        # the one next action

    def test_ready_says_hybrid_and_names_the_model(self, sandbox, monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "status",
                            lambda: {"ready": True, "model": "bge-small"})
        note = mcp.engine_note()
        assert "hybrid" in note
        assert "bge-small" in note
        assert "not configured" not in note

    def test_note_is_appended_to_instructions_not_baked_in(self, sandbox,
                                                           monkeypatch):
        # Guards the reason it lives at initialize: two hosts on one machine
        # must be able to get different answers as the store is built.
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "status", lambda: {"ready": False,
                                                      "reason": "no-store"})
        off = mcp.handle_request({"id": 1, "method": "initialize"},
                                 version="9.9.9", registry=_reg_with())
        monkeypatch.setattr(dense, "status", lambda: {"ready": True,
                                                      "model": "bge-small"})
        on = mcp.handle_request({"id": 1, "method": "initialize"},
                                version="9.9.9", registry=_reg_with())
        assert off["result"]["instructions"] != on["result"]["instructions"]
        assert "SEARCH ENGINE" not in mcp.INSTRUCTIONS   # the constant stays static

    def test_note_never_claims_a_key_is_required(self, sandbox, monkeypatch):
        # Same stale-advice trap fix_hint exists to prevent, on a second surface.
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "status",
                            lambda: {"ready": False, "reason": "no-backend"})
        note = mcp.engine_note()
        assert "pip install" in note
        assert "VOYAGE_API_KEY" not in note
