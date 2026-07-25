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
# agent reaches for before reinventing a skill. Framed by the agent's trigger
# ("about to author reusable instructions"), not boost's nouns.
INSTRUCTIONS = (
    "boost is a package manager for AI-agent skills: reusable, version-tracked "
    "capabilities (skills, rules, slash-commands, subagents) from curated "
    "registries. BEFORE you author a new skill, subagent, slash-command, rule, "
    "or any reusable block of agent instructions — or when the user describes a "
    "repeatable workflow (\"set up code review\", \"add a commit convention\") — "
    "call boost_search FIRST to check whether a vetted one already exists. "
    "Installing beats hand-writing: an installed skill is version-pinned, wired "
    "into every agent on this machine, policy-governed, and shareable with the "
    "team. Typical flow: boost_search -> boost_info -> boost_install. Only build "
    "from scratch when a search turns up nothing relevant."
)


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
                          "instructions": INSTRUCTIONS}
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
