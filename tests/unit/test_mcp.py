# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/mcp.py — the extensible MCP tool registry.

The registry is the Phase-3 "MCP as a hub" seam: tools self-register a spec +
handler, and the JSON-RPC server iterates it. These tests pin registration
order, spec shape, dispatch, and the unknown-tool contract so the mutation gate
has teeth.
"""
from __future__ import annotations

import io
import json
import re

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
        # The repeat-search cost claim is backed by rag's rerank cache; both
        # surfaces must state it, or an agent budgets 15 s for a lookup that
        # would have been free.
        assert "answers from a local cache" in mcp.INSTRUCTIONS
        assert "answers from a local cache" in desc["boost_search"]

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


class TestInstructionsCoverAllThreeKinds:
    """The catalog holds three kinds; the guidance used to describe one.

    `boost_search` returns skills, rules and workflows — `store.install`
    dispatches all three — but every line of MCP prose said "skills". An agent
    reading it has no reason to search for a guardrail or a slash-command, and
    no way to know that installing a rule edits the context file it loads every
    session. Naming the three is what makes two of them reachable at all.
    """

    def test_instructions_name_the_three_kinds(self):
        low = mcp.INSTRUCTIONS.lower()
        assert "rule" in low and "workflow" in low and "skill" in low

    def test_instructions_say_what_a_rule_does(self):
        # A rule is the kind that steers: it recommends a better path and
        # rules out an anti-pattern. That is the whole reason to search for
        # one, and it is not guessable from the word "rule".
        low = mcp.INSTRUCTIONS.lower()
        assert "anti-pattern" in low

    def test_install_description_still_flags_the_invasive_kind(self):
        # Pre-existing contract, restated here because this change is what
        # makes it actionable: search output now marks kind, so the warning
        # names something the caller can actually see.
        from boost_cli.commands import configuration
        desc = {s["name"]: s["description"]
                for s in configuration.REGISTRY.specs()}["boost_install"]
        assert "rule" in desc.lower()


class TestInstructionsBoundIsATestNotAFeeling:
    """"Non-trivial" is only usable if it decides itself.

    The trigger that shipped before this — does the task have a NAME — stays,
    because it is free to evaluate. What it missed is the task that has no
    tidy name and is still large. The fix is not to ask the agent to judge
    difficulty (it will say "this looks small", and every turn looks small
    when it opens) but to give it properties it can read off the REQUEST:
    more than one file, or something that outlives the session.
    """

    # EMNLP 2025 ("Tool Preferences in Agentic LLMs are Unreliable"): editing
    # only a description moves call rates >10x, and assertive phrasing is the
    # lever. Every boost surface is deliberately invitational.
    COERCIVE = ("always call", "you must", "never skip", "required before",
                "do not proceed")

    def test_the_boundary_is_stated_as_observable_properties(self):
        low = mcp.INSTRUCTIONS.lower()
        assert "more than one file" in low
        assert "outlives" in low or "outlast" in low

    def test_no_trigger_swallows_the_skip_list(self):
        # "you would name it in a commit message" was drafted as a third
        # signal and cut: it is true of every edit that ships, INCLUDING the
        # one-line edit the skip list excuses by name. A trigger that
        # contradicts its own bound turns "check first" into "check always",
        # which is the capture this surface exists to avoid.
        low = mcp.INSTRUCTIONS.lower()
        assert "commit message" not in low

    def test_the_original_nameable_trigger_survives(self):
        # Regression guard: the observable boundary is ADDITIVE. The name test
        # is the cheapest one an agent has and predates this change.
        assert "has a name" in mcp.INSTRUCTIONS.lower()

    def test_the_skip_list_stays_in_plain_sight(self):
        # An unbounded "check first" gets ignored wholesale. The bound is what
        # buys the rest of the guidance its credibility.
        low = mcp.INSTRUCTIONS.lower()
        assert "skip it for a question" in low

    def test_nothing_in_the_guidance_orders_the_agent(self):
        low = mcp.INSTRUCTIONS.lower()
        for coercive in self.COERCIVE:
            assert coercive not in low, (
                "coercive framing %r: an agent that is ordered rather than "
                "persuaded routes around the tool the first time it misses"
                % coercive)

    def test_no_tool_description_orders_the_agent_either(self):
        # Widened from INSTRUCTIONS alone. Gemini CLI never delivers server
        # `instructions` in interactive mode — Config.initialize() does not
        # await mcpInitializationPromise, so getMcpInstructions() returns ""
        # and the context entry is stamped once and short-circuited. The
        # declarations are therefore the only boost text reliably in context
        # on every host, which is why the trigger, the cost and now the
        # already-loaded defeater are all repeated into them. A clause that
        # moved from INSTRUCTIONS into a description must not shed the rule
        # INSTRUCTIONS was held to on the way. All seven are clean today; this
        # keeps them that way.
        from boost_cli.commands import configuration
        for spec in configuration.REGISTRY.specs():
            low = spec["description"].lower()
            for coercive in self.COERCIVE:
                assert coercive not in low, (
                    "%s's description uses coercive framing %r"
                    % (spec["name"], coercive))


class TestSearchDescriptionNamesTheLockInMoments:
    """Where a check pays most is where a choice gets frozen.

    Trigger design wants indirect signals, not just direct ones: "user asks
    about pricing" is direct, "a decision is about to be locked in" is the
    class an agent recognises on its own. These are the moments where the
    cost of the wrong path is paid for the rest of the project.
    """

    def _search(self):
        from boost_cli.commands import configuration
        return {s["name"]: s["description"]
                for s in configuration.REGISTRY.specs()}["boost_search"].lower()

    def test_names_setup_shaped_moments(self):
        desc = self._search()
        hits = [m for m in ("new project", "architecture", "linter", "test",
                            "ci", "environment") if m in desc]
        assert len(hits) >= 4, (
            "the description names %r of the lock-in moments; an agent that "
            "cannot recognise the moment will not reach for the tool at it"
            % hits)

    def test_states_what_a_match_contains(self):
        # tool-design's fourth question — "what does it return?" — went
        # unanswered on every tool. An agent that knows a match carries the
        # kind does not need an info round-trip to decide.
        desc = self._search()
        assert "kind" in desc

    def test_keeps_every_existing_guardrail(self):
        desc = self._search()
        assert "the task stays yours" in desc      # non-capture
        assert "10-15 seconds" in desc             # honest cost
        assert "vetted" not in desc                # no unperformed guarantee
        assert "thousands" not in desc             # no unbacked corpus size


class TestHitLinesCarryTheKind:
    """A search reply that hides kind makes `boost_install`'s warning useless.

    Installing a skill copies a file into the store. Installing a RULE merges
    text into the context file the agent loads every session — boost_install's
    own description calls that "the more invasive change" and tells the caller
    to check what kind of thing they are installing. Until the reply said so,
    there was nowhere to check: every hit rendered `name — description (tap)`.
    """

    def test_a_skill_renders_without_a_marker(self):
        # Skills are the common case and the historical shape; marking them
        # too would cost a token on every line to say "nothing unusual here".
        line = mcp.hit_line({"name": "brainstorming", "kind": "skill",
                             "description": "diverge then converge",
                             "tap": "anthropics/skills"})
        assert line == "brainstorming — diverge then converge (anthropics/skills)"

    def test_a_rule_is_marked(self):
        line = mcp.hit_line({"name": "python-style", "kind": "rule",
                             "description": "format before commit",
                             "tap": "PatrickJS/awesome-cursorrules"})
        assert "[rule]" in line
        assert line.startswith("python-style [rule] — ")

    def test_a_workflow_is_marked(self):
        line = mcp.hit_line({"name": "ship-it", "kind": "workflow",
                             "description": "release checklist", "tap": "t"})
        assert "[workflow]" in line

    def test_a_missing_kind_reads_as_a_skill(self):
        # Catalog entries predating the kind field, and any tap whose scanner
        # output is thin, must not render "[None]" at an agent.
        assert mcp.hit_line({"name": "n", "description": "d", "tap": "t"}) == \
            "n — d (t)"

    def test_a_missing_description_still_renders_the_name_and_tap(self):
        line = mcp.hit_line({"name": "n", "kind": "rule", "tap": "t"})
        assert "n [rule]" in line and "(t)" in line


class TestTheEmptyCatalogAnswersDifferentlyFromAMiss:
    """"no skills match X" on a fresh machine is a true sentence that teaches
    the wrong thing. Nothing matched because nothing is *there* — and an agent
    that reads it as "boost has nothing on this" has no reason to ask again.
    tool-design's rule for agent-facing errors applies: say what went wrong
    AND the move that fixes it.
    """

    def test_a_real_miss_keeps_todays_wording(self):
        # Pre-existing contract (tests/functional pin this string): a tapped
        # machine that genuinely has no match must not start blaming setup.
        assert mcp.no_results("widgets", tapped=4) == "no skills match 'widgets'"

    def test_nothing_tapped_says_so_and_names_the_fix(self):
        reply = mcp.no_results("widgets", tapped=0)
        assert "no skills match" not in reply
        assert "boost tap --defaults" in reply

    def test_nothing_tapped_does_not_blame_the_query(self):
        # The query is fine. Repeating it back framed as a failed search is
        # exactly what makes the reply indistinguishable from a real miss.
        assert "widgets" not in mcp.no_results("widgets", tapped=0)


def _descriptions():
    from boost_cli.commands import configuration
    return {s["name"]: s["description"] for s in configuration.REGISTRY.specs()}


class TestTheAlreadyLoadedDefeater:
    """The trigger fired, and a proposition boost never wrote down overruled it.

    Forensics on a Gemini CLI session: asked to build a RAG app with LangGraph,
    LangChain and LangSmith, the agent shipped it without calling one boost
    tool. Asked why, it said it had "immediately activated the pre-installed
    local skills — langchain-rag and rag-engineer" and "overlooked calling
    mcp_boost_boost_search". boost_search's description already named that
    exact moment ("a new project or subsystem, an architecture decision,
    environment and tooling config"), and the agent paraphrased the list back.

    So the trigger did not fail to fire — it fired and was overruled. Every
    trigger boost ships is a predicate over the REQUEST. The gate the model
    applied was a predicate over its OWN CONTEXT: something already matched,
    so I am covered.

    Measured on the parent commit, over INSTRUCTIONS plus all six tool
    descriptions (6,346 characters), that proposition appears nowhere:
    'already have' 0, 'already loaded' 0, 'already matched' 0, 'even if' 0,
    'even when' 0, 'enough' 0, 'sufficient' 0, 'covered' 0, 'active skill' 0.
    A clause that does not exist cannot have failed.

    These pin the missing clause. It is a DEFEATER placed downstream of the
    existing gate, not a fourth trigger — the two signals are unchanged and
    the skip list is untouched.
    """

    def test_the_instructions_address_what_is_already_loaded(self):
        low = mcp.INSTRUCTIONS.lower()
        assert "already holding a match" in low

    def test_it_says_what_an_active_skill_is_rather_than_what_it_is_not(self):
        # Deliberately a scope statement, not a contradiction. An earlier draft
        # said "an active skill does not answer this question", which a model
        # compresses to "an active skill is never enough" — a standing order to
        # search, i.e. exactly the capture this whole surface is written to
        # avoid. What survives is the description an agent can check against
        # its own situation: installed earlier, matched on its own description,
        # one kind of three. The conclusion is left to the reader.
        low = mcp.INSTRUCTIONS.lower()
        assert "installed on an earlier day" in low
        assert "matched on its own description" in low
        assert "one kind of three" in low
        assert "does not answer this question" not in low
        assert "never enough" not in low

    def test_it_sits_downstream_of_the_two_signals_not_beside_them(self):
        # Order is the argument. A fourth trigger would widen the gate; this
        # narrows an exception to it, so it has to be read after the gate it
        # defeats and before the miss protocol that keeps the tool honest.
        text = mcp.INSTRUCTIONS
        gate = text.index("WORTH THE SECONDS")
        defeater = text.index("ALREADY HOLDING A MATCH")
        miss = text.index("Finding nothing")
        assert gate < defeater < miss

    def test_it_leaves_the_two_signals_and_the_skip_list_exactly_as_they_were(self):
        # Regression guard on the shape of the change: a defeater that quietly
        # widened the trigger, or ate the bound, would be the same failure in
        # the other direction.
        low = mcp.INSTRUCTIONS.lower()
        assert "more than one file" in low
        assert "outlives this session" in low
        assert "skip it for a question" in low
        assert "the task stays yours" in low

    def test_the_search_description_repeats_it(self):
        # Gemini CLI never delivers server `instructions` in interactive mode:
        # Config.initialize() does not await mcpInitializationPromise, so
        # getMcpInstructions() returns "" and startChat stamps the context
        # entry once, under a stable id, and short-circuits; the later
        # refreshMcpContext() re-renders Tier 1 only and excludes project
        # memory. The failing session's log has an empty ${environmentMemory}
        # slot and zero hits for "start of server instructions". Claude Code
        # does deliver them. The declarations are the only text present on
        # every host, which is why the trigger and the cost are already
        # duplicated there — the defeater has to be too, or it is absent on
        # the host where the failure was observed.
        low = _descriptions()["boost_search"].lower()
        assert "one kind of three" in low
        assert "[installed]" in low

    def test_the_defeater_sits_against_the_trigger_list_it_protects(self):
        # It defends the lock-in list specifically — "a new project or
        # subsystem, an architecture decision, environment and tooling config"
        # is what the failing session matched and then discounted. Sentences
        # that qualify each other and sit paragraphs apart do not get read as
        # one thought.
        #
        # The one sentence allowed between them is the authoring trigger, which
        # is the last item of the same enumeration and shares its verb ("Reach
        # for it..."). Putting the defeater ahead of it read as a topic change
        # mid-list and stranded "Also before writing a skill" from the clause
        # it continues. 400 is that sentence plus headroom, not a free budget.
        desc = _descriptions()["boost_search"]
        lock_in = desc.index("architecture decision")
        defeater = desc.index("one kind of three")
        assert lock_in < defeater
        assert desc.index("Also before writing") < defeater
        assert defeater - lock_in < 400, (
            "the defeater drifted %d characters from the trigger list it "
            "qualifies" % (defeater - lock_in))

    def test_boost_list_no_longer_only_looks_inward(self):
        # boost_list was the crowd-out amplifier. Its description said an
        # installed item is "capability you own and may not know you own" —
        # true, and purely inward-facing. Had the failing agent called the free
        # tool, that sentence would have CONFIRMED the belief that stopped it.
        # The inward half stays; it is the only half that used to be said.
        low = _descriptions()["boost_list"].lower()
        assert "capability you own" in low            # the half that was right
        assert "not what exists" in low               # the half that was missing
        assert "boost_search" in low                  # and where the rest lives


class TestListDescriptionCarriesItsOwnTrigger:
    """`boost_list` has to sell itself on the host that drops INSTRUCTIONS.

    Same mechanism as the defeater above: Gemini CLI never delivers server
    `instructions` in interactive mode, so a function declaration is the only
    boost text reliably in context at the moment an agent picks a tool.
    INSTRUCTIONS says "boost_list is free, call it whenever"; the declaration
    has to carry that itself, or on that host the one tool the guidance calls
    free arrives with no stated reason to reach for it.

    The cost half is deliberately NOT symmetrical with boost_search's. This
    tool is a local file read — the lock file and the tap list, no catalog
    scan, which `test_it_never_reads_the_catalog` holds true — so it names
    that mechanism and stays silent about "10-15 seconds", which is the other
    tool's price and would be an invented one here.
    """

    def test_it_says_why_it_is_free_and_not_only_that_it_is_fast(self):
        # "instant" is a claim about the clock; "a local file read" is the
        # reason for it, and the reason is the part an agent can check against
        # its own model of what a call costs. Both ship, and so does the word
        # INSTRUCTIONS uses for this tool — free.
        low = _descriptions()["boost_list"].lower()
        assert "local file read" in low
        assert "free" in low
        assert "instant" in low
        assert "read-only" in low

    def test_it_states_the_threshold_and_the_mistake(self):
        # The trigger, in the same three beats as the guidance: no threshold,
        # the moment it applies to, and what happens to an agent that skips it.
        low = _descriptions()["boost_list"].lower()
        assert "no threshold worth applying" in low
        assert "about to plan something" in low
        assert "sits on disk" in low

    def test_it_does_not_borrow_the_price_of_the_slow_tool(self):
        # boost_list reranks nothing and reads no catalog. Quoting the other
        # tool's cost here would talk an agent out of the one call the whole
        # surface wants it to make without deliberating.
        low = _descriptions()["boost_list"].lower()
        assert "10-15 seconds" not in low
        assert "reranks" not in low

    def test_it_stays_far_shorter_than_the_tool_that_costs_time(self):
        # boost_search earns 2,000 characters by being the expensive call that
        # needs justifying. A free tool that grew to match it would be spending
        # context it never earned.
        desc = _descriptions()
        assert len(desc["boost_list"]) < len(desc["boost_search"]) / 2


class TestCoverageLine:
    """`boost_list`'s footer: the exact half of the answer, and no more.

    A machine showing `0 rules` cannot have loaded the guardrail that would
    have steered this task — that inference is what the footer is for, and the
    installed counts are enough to support it on their own.
    """

    def test_it_counts_the_three_kinds_from_the_lock_sections(self):
        line = mcp.coverage_line(
            {"skill": {"a": {}, "b": {}}, "rule": {}, "workflow": {"w": {}}},
            tapped=3)
        assert "2 skills · 0 rules · 1 workflow installed here" in line

    def test_a_kind_at_zero_is_printed_rather_than_omitted(self):
        # The zero is the signal. Dropping empty kinds to tidy the line would
        # delete the only evidence that a whole kind is missing from the
        # machine, which is the inference the footer exists to make available.
        line = mcp.coverage_line({"skill": {}, "rule": {}, "workflow": {}},
                                 tapped=2)
        assert "0 skills · 0 rules · 0 workflows" in line

    def test_it_quotes_no_number_it_cannot_compute_exactly(self):
        # The draft this replaced ended with "the tapped catalog holds 57,119
        # skills · 3,016 rules · 11,520 workflows". Those are un-de-duplicated
        # index entries, and CLAUDE.md's own eval section is the refutation:
        # the ranked list de-duplicates on CONTENT HASH precisely because 13
        # distinct skills named `code-reviewer` collapsing into one slot was
        # "crediting the ranker with a compression that existed only in the
        # scoring code". 57,119 entries is not 57,119 distinct capabilities.
        # It was also the only new text with no bound attached — the closest
        # thing in the surface to a sales pitch — in the one place an agent
        # cannot check it. The installed counts cannot inflate; nothing else
        # numeric belongs here.
        line = mcp.coverage_line(
            {"skill": {"a": {}, "b": {}}, "rule": {}, "workflow": {"w": {}}},
            tapped=57119)
        assert re.findall(r"\d+", line) == ["2", "0", "1"], (
            "coverage_line leaked a number that is not an installed count: %r"
            % line)

    def test_one_of_a_kind_is_singular(self):
        line = mcp.coverage_line({"skill": {"a": {}}, "rule": {"r": {}},
                                  "workflow": {"w": {}}}, tapped=1)
        assert "1 skill · 1 rule · 1 workflow installed here" in line

    def test_a_tapped_machine_is_pointed_at_the_catalog_not_at_setup(self):
        line = mcp.coverage_line({"skill": {"a": {}}}, tapped=4)
        # Case-exact, and each clause is a claim rather than a copy of the
        # sentence: the outward half, who answers it, and that it spans every
        # kind (a footer that pointed at skills alone would reproduce the bug
        # in a smaller font).
        assert "installed here — what this machine holds, not what exists. " in line
        assert "boost_search reads the tapped registries themselves, across " in line
        assert "all three kinds." in line
        assert "boost tap" not in line

    def test_one_tap_is_a_tapped_machine(self):
        # The boundary, and mutation testing is what found it missing: with
        # `tapped > 1` in place of `tapped > 0`, every single-tap machine — the
        # shape of a fresh `boost tap <one repo>` — is told to run
        # `boost tap --defaults`, which is advice for a machine that has none.
        line = mcp.coverage_line({"skill": {"a": {}}}, tapped=1)
        assert "not what exists" in line
        assert "boost tap --defaults" not in line

    def test_an_untapped_machine_names_the_same_command_as_the_other_two(self):
        # `mcp.no_results` and `_tool_doctor` both key their setup message on
        # tapped == 0 and both name `boost tap --defaults` first. The comment
        # at configuration.py:1015-1020 says why: an agent calling two of these
        # in one session must not see the recommendation flip and read it as
        # two different fixes. `boost mcp --seed` is the wrong one to name — it
        # re-registers the server with every agent CLI on PATH as a side
        # effect, and overrides a BOOST_NO_SEED the user set deliberately.
        line = mcp.coverage_line({"skill": {}, "rule": {}, "workflow": {}},
                                 tapped=0)
        assert "Nothing is tapped yet" in line
        assert "boost tap --defaults" in line
        assert "boost mcp --seed" not in line

    def test_the_untapped_branch_keys_on_taps_not_on_an_empty_lock(self):
        # These two states are different and used to be confusable: a machine
        # with items installed can still have had its taps removed, and a
        # freshly tapped machine has nothing installed yet. The counts and the
        # setup note answer different questions, so each keys on its own input.
        installed_untapped = mcp.coverage_line(
            {"skill": {"a": {}}, "rule": {}, "workflow": {}}, tapped=0)
        assert "1 skill" in installed_untapped
        assert "boost tap --defaults" in installed_untapped
        empty_but_tapped = mcp.coverage_line(
            {"skill": {}, "rule": {}, "workflow": {}}, tapped=9)
        assert "boost tap --defaults" not in empty_but_tapped

    def test_a_missing_lock_section_counts_as_zero(self):
        # lockfile.all_installed() always returns all three, but a caller
        # passing a partial dict must not crash the one tool that is supposed
        # to be free to call.
        assert "0 rules" in mcp.coverage_line({"skill": {"a": {}}}, tapped=1)


class TestOverlapNote:
    """How much of a search reply is already on the machine.

    The defeater's other half, and the only place the `[installed]` marker's
    imprecision is disclosed to the agent that reads it.
    """

    def test_no_hits_no_note(self):
        # The empty reply is mcp.no_results' job; a second sentence about zero
        # overlap on top of it would be noise.
        assert mcp.overlap_note(0, 0) == ""

    def test_nothing_installed_says_so(self):
        # Directly refutes "something already matched, so I am covered": every
        # line on screen is something this machine does not have. Byte-exact
        # because it is one short sentence, the way no_results' miss branch is.
        assert mcp.overlap_note(0, 8) == \
            "\n(none of these are installed on this machine.)"

    def test_a_partial_overlap_counts_both_sides(self):
        note = mcp.overlap_note(3, 10)
        assert "3 of 10" in note
        assert "[installed]" in note

    def test_a_total_overlap_is_still_reported_as_a_count(self):
        # No special case: "10 of 10" is a true and useful sentence, and a
        # bespoke "you have all of these" line would be the one shape an agent
        # could read as "stop here".
        assert "10 of 10" in mcp.overlap_note(10, 10)

    def test_it_discloses_that_the_marker_matches_on_the_name_alone(self):
        # The marker is name-keyed, matching lockfile.find_any and
        # store.install. That is a real false-positive rate — the corpus holds
        # 13 different skills called `code-reviewer` — and it errs in the
        # direction that suppresses a search, so it cannot go unsaid.
        #
        # Keying it more precisely was the alternative and was rejected: the
        # lock file IS name-keyed, so a tap-qualified marker would disagree
        # with the tool it is advising about. A hit marked "not installed"
        # that `boost_install <name>` then resolves to the item already in the
        # lock is a second, contradicting notion of identity inside one reply.
        # Disclosing the imprecision keeps one identity and hands the agent
        # the field that resolves it — every hit line already names its tap.
        #
        # Case-exact, clause by clause. Each is a separate load-bearing claim —
        # what the match is on, which tools share it, what the consequence is,
        # and the field that resolves it — and losing any one of them leaves an
        # agent trusting a marker it has not been told the limits of.
        note = mcp.overlap_note(2, 5)
        assert "already installed here, marked [installed]. The match " in note
        assert "is on the name alone — the same test boost_install and " in note
        assert "so an item from a different tap that shares a name is " in note
        assert "marked too; each line names its tap.)" in note

    def test_it_never_claims_more_overlap_than_there_were_hits(self):
        assert "5 of 5" in mcp.overlap_note(5, 5)


class TestHitLineMarksWhatIsAlreadyInstalled:
    """A search reply that cannot tell you what you already have is what makes
    "I already have something" a guess rather than a reading."""

    def test_the_default_is_byte_identical_to_before(self):
        # `installed` is keyword-only and defaults False precisely so every
        # existing assertion on this function keeps passing unchanged.
        assert mcp.hit_line({"name": "n", "description": "d", "tap": "t"}) == \
            "n — d (t)"

    def test_an_installed_skill_is_marked(self):
        line = mcp.hit_line({"name": "rag-engineer", "kind": "skill",
                             "description": "d", "tap": "t"}, installed=True)
        assert line == "rag-engineer [installed] — d (t)"

    def test_an_installed_rule_keeps_both_markers_kind_first(self):
        # The kind marker is what boost_install's warning about the invasive
        # kind is checked against, so it keeps its position next to the name.
        line = mcp.hit_line({"name": "python-style", "kind": "rule",
                             "description": "d", "tap": "t"}, installed=True)
        assert line == "python-style [rule] [installed] — d (t)"

    def test_an_entry_missing_every_field_still_renders(self):
        # scan_dir output is thin for some taps, and a hit line is the only
        # place an agent sees a candidate at all. Every placeholder is pinned:
        # a `None` leaking into any of the three slots renders "None" at an
        # agent as if it were the item's real name, description or tap.
        assert mcp.hit_line({}) == "? —  (?)"
        assert mcp.hit_line({}, installed=True) == "? [installed] —  (?)"

    def test_installed_is_keyword_only(self):
        # Positional would make `hit_line(entry, True)` legal, which reads as
        # nothing at the call site and is one refactor away from meaning the
        # opposite.
        with pytest.raises(TypeError):
            mcp.hit_line({"name": "n", "description": "d", "tap": "t"}, True)


class TestListReportsTheShapeOfWhatIsThere:
    """`boost_list` was the crowd-out amplifier: it answered "what do I have"
    and nothing else, so the one free tool an agent could have called on the
    way to being wrong would have agreed with it. The footer is the second
    half — same call, same cost, no catalog read."""

    def test_the_empty_state_still_gets_the_footer(self, sandbox):
        # The empty machine is where the footer matters most and where a
        # short-circuit `return "nothing installed"` would silently skip it.
        from boost_cli.commands import configuration
        text, is_err = configuration._tool_list({})
        assert is_err is False
        assert text.startswith("nothing installed")
        assert "0 skills · 0 rules · 0 workflows" in text

    def test_a_populated_list_ends_with_the_footer(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration
        monkeypatch.setattr(configuration.lockfile, "all_installed", lambda: {
            "skill": {"brainstorming": {"version": "1.4.0", "tap": "a/b"}},
            "rule": {}, "workflow": {}})
        text, _ = configuration._tool_list({})
        assert text.splitlines()[0].startswith("brainstorming v1.4.0")
        assert text.splitlines()[-1].startswith("1 skill · 0 rules · 0 workflows")

    def test_it_never_reads_the_catalog(self, sandbox, monkeypatch):
        # INSTRUCTIONS ships the claim that boost_list is "instant" (pinned by
        # test_instructions_still_separate_the_free_tool_from_the_slow_one),
        # and that claim is what buys it "no threshold worth applying". A
        # footer that quoted catalog totals would have cost a full tap scan —
        # 423 ms for 71,655 entries on a real install — and made the shipped
        # claim false. Cutting the catalog half of the footer is what pays for
        # this; the counts that remain come from the lock file alone.
        from boost_cli.commands import configuration

        def boom(*_a, **_k):
            raise AssertionError("boost_list read the catalog")

        monkeypatch.setattr(configuration.catalog, "all_entries", boom)
        monkeypatch.setattr(configuration.catalog, "kind_counts", boom)
        configuration._tool_list({})


class TestSearchSaysHowTheOrderWasProduced:
    """`_tool_search` has two branches and only one of them told the truth.

    The RAG branch appends `_ranking_note`, which says in plain words when the
    LLM rerank named in the tool's own description did not run. The frontmatter
    fallback — taken when no index exists — appended nothing at all, so an
    agent on that path got ten confident lines produced by a name-and-
    description scorer and was told nothing about where the order came from.
    Both branches now carry the marker, the overlap note and a ranking note.
    """

    def _entry(self, name, kind="skill"):
        return {"name": name, "kind": kind, "description": "d", "tap": "t"}

    def _run(self, monkeypatch, *, rag_result, frontmatter=(), installed=()):
        from boost_cli.commands import configuration
        monkeypatch.setattr(configuration.rag, "ensure", lambda: True)
        monkeypatch.setattr(configuration.rag, "search",
                            lambda *_a, **_k: rag_result)
        monkeypatch.setattr(configuration.catalog, "search",
                            lambda _q: [(e, 1) for e in frontmatter])
        # A real Tap, not a bare string: the reply now asks each tap whether
        # it is boost's OWN builtin (which must not answer "has this user
        # configured anything"), so a stand-in without a name is no longer a
        # faithful stub of list_taps.
        monkeypatch.setattr(
            configuration.registry, "list_taps",
            lambda: [configuration.registry.Tap(name="t", url="https://x/y")])
        self.lock_reads = []
        monkeypatch.setattr(
            configuration.lockfile, "all_installed",
            lambda: self.lock_reads.append(1) or {
                "skill": {n: {} for n in installed},
                "rule": {}, "workflow": {}})
        text, is_err = configuration._tool_search({"query": "rag"})
        assert is_err is False
        return text

    def _both_branches(self, monkeypatch, entries, **kw):
        rag_hits = ([{"entry": e} for e in entries], "BM25 full-content")
        return (self._run(monkeypatch, rag_result=rag_hits, **kw),
                self._run(monkeypatch, rag_result=None, frontmatter=entries,
                          **kw))

    def test_both_branches_end_with_a_ranking_note(self, monkeypatch):
        for text in self._both_branches(monkeypatch,
                                        [self._entry("langchain-rag")]):
            assert text.strip().splitlines()[-1].startswith("(ranked by ")

    def test_the_fallback_names_the_scorer_that_actually_ran(self, monkeypatch):
        # Naming a specific wrong engine is worse than naming none — rag.rerank
        # says so in its own comment, having once labelled a dense result
        # "BM25 full-content" and sent debugging somewhere else. The fallback
        # is neither engine: it is catalog.search over frontmatter, taken
        # because no index exists yet.
        text = self._run(monkeypatch, rag_result=None,
                         frontmatter=[self._entry("langchain-rag")])
        assert "frontmatter" in text
        assert "no index" in text
        assert "did NOT run" in text          # the rerank the description sells

    def test_the_fallback_does_not_borrow_the_reranked_shape(self, monkeypatch):
        # The whole risk: ten lines that look exactly like a reranked ten, so
        # an agent acts on the top one because the description told it to.
        text = self._run(monkeypatch, rag_result=None,
                         frontmatter=[self._entry("langchain-rag")])
        assert "Claude relevance" not in text

    def test_both_branches_mark_a_hit_that_is_already_installed(self,
                                                                monkeypatch):
        entries = [self._entry("langchain-rag"), self._entry("something-else")]
        for text in self._both_branches(monkeypatch, entries,
                                        installed=["langchain-rag"]):
            assert "langchain-rag [installed] — " in text
            assert "something-else [installed]" not in text

    def test_both_branches_carry_the_overlap_note(self, monkeypatch):
        entries = [self._entry("langchain-rag"), self._entry("something-else")]
        for text in self._both_branches(monkeypatch, entries,
                                        installed=["langchain-rag"]):
            assert "1 of 2" in text

    def test_a_reply_with_no_overlap_says_that_too(self, monkeypatch):
        for text in self._both_branches(monkeypatch, [self._entry("a")]):
            assert "none of these are installed" in text.lower()

    def test_the_lock_file_is_read_once_for_the_whole_reply(self, monkeypatch):
        # `lockfile.find_any` re-reads and re-parses the lock on every call, so
        # the obvious `find_any(name)` inside the marker comprehension is ten
        # reads of the same bytes per search. The union of the three sections
        # is the same name-keyed predicate, once.
        entries = [self._entry("a"), self._entry("b"), self._entry("c")]
        self._run(monkeypatch,
                  rag_result=([{"entry": e} for e in entries], "BM25"))
        assert self.lock_reads == [1]

    def test_an_empty_reply_reads_no_lock_at_all(self, monkeypatch):
        # Nothing to mark, so nothing to look up. mcp.no_results returns before
        # the marker pass on both branches.
        self._run(monkeypatch, rag_result=([], "BM25"))
        assert self.lock_reads == []

    def test_an_empty_reply_is_untouched_on_both_branches(self, monkeypatch):
        # mcp.no_results owns the empty reply, including the untapped-machine
        # branch. Neither the marker nor the overlap note may bolt onto it.
        for text in self._both_branches(monkeypatch, []):
            assert text == "no skills match 'rag'"


class TestDoctorCountsWithoutBuildingTheList:
    """`len(catalog.all_entries())` materialised every tap's cache — 71,655
    entries on a real install — to produce one integer. Same reads, no
    accumulation."""

    def test_it_asks_for_counts_not_for_entries(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration

        def boom():
            raise AssertionError("boost_doctor materialised the whole catalog")

        monkeypatch.setattr(configuration.catalog, "all_entries", boom)
        monkeypatch.setattr(configuration.catalog, "kind_counts",
                            lambda: {"skill": 40, "rule": 2, "workflow": 0})
        text, _ = configuration._tool_doctor({})
        assert "42 items available" in text

    def test_the_reported_total_is_still_every_kind(self, sandbox, monkeypatch):
        # "items", not "skills": the comment on this line is explicit that
        # counting rules and workflows as skills overstates one kind and hides
        # the other two in the same breath. Summing the counts keeps that true.
        from boost_cli.commands import configuration
        monkeypatch.setattr(configuration.catalog, "kind_counts",
                            lambda: {"skill": 1, "rule": 1, "workflow": 1})
        text, _ = configuration._tool_doctor({})
        assert "3 items available" in text
