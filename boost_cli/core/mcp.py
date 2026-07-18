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

from typing import Callable, Dict, List, Optional, Tuple

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
        return list(self._order)

    def has(self, name: str) -> bool:
        return name in self._handlers

    def call(self, name: str, args: dict) -> Tuple[Optional[str], bool]:
        """Dispatch to a handler. ``(None, False)`` for an unknown tool."""
        handler = self._handlers.get(name)
        if handler is None:
            return None, False
        return handler(args)
