"""Extensible MCP tool registry — the Phase-3 "MCP as a hub" seam.

An MCP tool is a *handler* — ``fn(args: dict) -> (text, is_error)`` — paired with
its JSON spec (``name`` / ``description`` / ``inputSchema``). Instead of a flat
``if/elif`` dispatcher, tools self-register on a :class:`Registry`; the JSON-RPC
server iterates it for both ``tools/list`` and ``tools/call``. Adding a
capability (a GitHub reach-out, a database query, some future dependency) is one
``register()`` call — no dispatcher edits, no server changes.

Handlers return ``(text, is_error)``. A handler that returns ``text is None``
signals "I did not produce a result"; :meth:`Registry.call` also returns
``(None, False)`` for an unknown tool, so the server can answer with a JSON-RPC
``unknown tool`` error in exactly one place. Reach-out handlers degrade the way
``core/ai.py`` does: probe for the dependency, and when it is absent return a
short helpful message rather than raising.
"""
from __future__ import annotations

import json
import sys
from typing import Callable, Dict, List, Optional, Tuple

from ..errors import BoostError

# A handler maps parsed arguments to (text, is_error). ``text is None`` means the
# handler produced no result (treated by the server as an unknown/aborted tool).
Handler = Callable[[dict], Tuple[Optional[str], bool]]


class Registry:
    """An ordered name -> (spec, handler) map for MCP tools."""

    def __init__(self) -> None:
        self._order: List[str] = []
        self._specs: Dict[str, dict] = {}
        self._handlers: Dict[str, Handler] = {}

    def register(self, name: str, description: str, input_schema: dict,
                 handler: Handler) -> None:
        """Register one tool. Raises on an empty or duplicate name."""
        if not name:
            raise ValueError("MCP tool name must be non-empty")
        if name in self._handlers:
            raise ValueError("duplicate MCP tool %r" % name)
        self._order.append(name)
        self._specs[name] = {"name": name, "description": description,
                             "inputSchema": input_schema}
        self._handlers[name] = handler

    def tool(self, name: str, description: str,
             input_schema: dict) -> Callable[[Handler], Handler]:
        """Decorator form of :meth:`register`; returns the handler unchanged."""
        def deco(fn: Handler) -> Handler:
            self.register(name, description, input_schema, fn)
            return fn
        return deco

    def specs(self) -> List[dict]:
        """The ``tools/list`` payload — specs in registration order."""
        return [self._specs[name] for name in self._order]

    def names(self) -> List[str]:
        """Registered tool names, in registration order."""
        return self._order.copy()

    def has(self, name: str) -> bool:
        return name in self._handlers

    def call(self, name: str, args: dict) -> Tuple[Optional[str], bool]:
        """Dispatch to a handler. ``(None, False)`` for an unknown tool."""
        handler = self._handlers.get(name)
        if handler is None:
            return None, False
        return handler(args)


# ── JSON-RPC 2.0 protocol ─────────────────────────────────────────────────
# The wire protocol Claude Code speaks to `boost mcp --stdio`. handle_request is
# a *pure* request→response mapping (no I/O), so the whole protocol is unit
# testable; serve_stdio only adds the newline-delimited stdin/stdout loop.
PROTOCOL_VERSION = "2024-11-05"

# Server-level guidance returned in the `initialize` result. MCP hosts load this
# into the model's context, so it is boost's one chance to tell an agent WHEN it
# is relevant — the difference between a search tool that sits unused and one an
# agent reaches for. Framed by the agent's triggers, not boost's nouns.
#
# ONE benefit, stated once: find a skill for the task in front of you. Earlier
# passes gave equal billing to "before you author a skill", and that cost more
# than it bought — authoring is the rarer moment, and an agent handed two
# triggers matches the one it can recognise fastest, which was the wrong one.
# Authoring now lives as a clause on boost_search's own description.
#
# The trigger is observable rather than a judgement call. "Before non-trivial
# work" lost to its own escape hatch every time: deciding a task is non-trivial
# takes judgement, while "this turn looks small" is free, and every turn looks
# small when it opens. Whether the task has a NAME can be pattern-matched
# without deciding anything, and a named task is exactly the kind someone has
# already written down.
#
# Three things below are load-bearing, not padding. The stated COST kills the
# hesitation over an unknown-price call. The MISS PROTOCOL stops a zero-result
# search reading as a wasted turn — without it one empty search teaches an agent
# to stop checking. And "the task stays yours" is what makes an agent willing to
# look at all: one that expects a hit to seize the work is safer not looking.
# The closing bound names concrete shapes instead of the word "trivial", which
# an unbounded "always check first" needs or the guidance gets ignored wholesale.
INSTRUCTIONS = (
    "boost is a shared shelf of vetted, version-tracked skills for AI coding "
    "agents — procedures someone already worked out, ready to follow.\n"
    "\n"
    "THE CHECK: if the task in front of you has a name — \"set up code "
    "review\", \"add commit conventions\", \"write a migration\", \"debug "
    "flaky tests\" — someone has probably already written it down. Call "
    "boost_list for what is installed on this machine and boost_search for "
    "what exists. Both are read-only and install nothing. boost_list is "
    "instant. boost_search takes a few seconds: it retrieves, then ranks them "
    "with an LLM, which is worth it because you act on the top result — "
    "measured, that ranking puts the right skill first 95% of the time "
    "against 79% without it.\n"
    "\n"
    "Finding nothing is a good outcome, not a wasted call: it tells you to "
    "build it yourself, now knowing that nothing already covers it. Finding "
    "something is a head start, not an instruction — read it, take what fits, "
    "discard the rest. The task stays yours.\n"
    "\n"
    "Two moments beat the odds: the first step of anything that will take more "
    "than a few steps, and the moment a small task turns out to be a large "
    "one. The second matters because the first only fires at a boundary you "
    "recognized at the time — a question that became an investigation never "
    "got one.\n"
    "\n"
    "Flow: boost_search -> boost_install. Skip it for a question, a one-line "
    "edit, or a command you were just handed."
)


def engine_note() -> str:
    """One line telling the agent which retrieval engine `boost_search` will use.

    MCP hosts load `instructions` into the agent's context, and an agent that
    cannot tell a keyword index from a semantic one will phrase queries for a
    vector search that is not running — asking "my containers keep restarting"
    of a BM25 index that needs the word "docker". Naming the engine, and the one
    command that upgrades it, costs a line and removes the guess.

    Appended at `initialize` rather than baked into INSTRUCTIONS because the
    answer depends on machine state at connect time, not on the build.
    """
    from . import dense
    st = dense.status()
    if st.get("ready"):
        return ("\n\nSEARCH ENGINE: hybrid — BM25 keywords fused with dense "
                "vectors (%s). Natural-language problem descriptions retrieve "
                "well; you do not need to guess the skill's vocabulary."
                % st.get("model"))
    return ("\n\nSEARCH ENGINE: BM25 keyword matching only — dense vectors are "
            "not configured, so queries are matched on shared words rather than "
            "meaning. Prefer concrete terms over paraphrase. To enable semantic "
            "search, %s." % dense.fix_hint(st.get("reason", "")))


def handle_request(req: dict, *, version: str,
                   registry: Registry) -> Optional[dict]:
    """Map one parsed JSON-RPC request to its response dict.

    Returns ``None`` for a notification (a request with no ``id``) — the caller
    sends nothing back. Handlers that raise during ``tools/call`` are turned into
    an error *result* (``isError``) rather than a protocol error, so a failing
    tool never kills the session.
    """
    method = str(req.get("method", ""))
    if "id" not in req:  # notification (e.g. notifications/initialized)
        return None
    resp: dict = {"jsonrpc": "2.0", "id": req.get("id")}
    if method == "initialize":
        resp["result"] = {"protocolVersion": PROTOCOL_VERSION,
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "boost", "version": version},
                          "instructions": INSTRUCTIONS + engine_note()}
    elif method == "ping":
        resp["result"] = {}
    elif method == "tools/list":
        resp["result"] = {"tools": registry.specs()}
    elif method == "tools/call":
        params = req.get("params") or {}
        tool = str(params.get("name", ""))
        try:
            text, is_err = registry.call(tool, params.get("arguments") or {})
        except BoostError as e:
            text = "Error: %s" % e.message + ("\nhint: %s" % e.hint if e.hint else "")
            is_err = True
        except Exception as e:
            text, is_err = "Error: %s" % e, True
        if text is None:
            resp["error"] = {"code": -32602, "message": "unknown tool %r" % tool}
        else:
            # Annotated: the literal alone infers a list-only value type, so
            # adding the `isError` bool below would be a type error.
            result: dict = {"content": [{"type": "text", "text": text}]}
            if is_err:
                result["isError"] = True
            resp["result"] = result
    else:
        resp["error"] = {"code": -32601, "message": "method not found: %s" % method}
    return resp


def serve_stdio(registry: Registry, *, version: str,
                stdin=None, stdout=None) -> int:
    """Newline-delimited JSON-RPC 2.0 MCP server on stdin/stdout.

    ``stdin``/``stdout`` default to the process streams but can be injected
    (e.g. ``io.StringIO``) so the loop is testable end to end.
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    def send(msg: dict) -> bool:
        try:
            stdout.write(json.dumps(msg) + "\n")
            stdout.flush()
            return True
        except (BrokenPipeError, OSError):
            return False

    while True:
        try:
            line = stdin.readline()
        except (KeyboardInterrupt, OSError):
            return 0
        if not line:  # EOF
            return 0
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            if not send({"jsonrpc": "2.0", "id": None,
                         "error": {"code": -32700, "message": "parse error"}}):
                return 0
            continue
        resp = handle_request(req, version=version, registry=registry)
        if resp is None:  # notification — nothing to send
            continue
        if not send(resp):
            return 0
