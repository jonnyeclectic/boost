# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What MCP servers does a skill need, and how do we wire them?

Mining boost's catalog surfaces a recurring shape: skills that only work paired
with a Model Context Protocol server (``manage-mcp-servers``, ``mcp-builder``,
``mcp-integration`` and dozens more). boost already *is* an MCP server and
registers itself with ``boost mcp register`` — but a skill had no way to say
"I need server Y," so installing one left the user to discover that by hand.

Two declaration forms, both deliberately **flat**:

* ``mcp: github, playwright`` in SKILL.md frontmatter (a comma string or a YAML
  block list) — just the names, reusing the exact contract ``requires:`` and
  ``conflicts:`` already use.
* a bundled ``.mcp.json`` in the skill directory — the standard MCP shape
  (``{"mcpServers": {name: {command, args, env}}}``), carrying full specs.

Why flat, and not the nested ``mcp:`` mapping the roadmap card sketched:
:mod:`boost_cli.core.frontmatter` is a stdlib-only YAML *subset* with no nested
mapping support, and it does not fail loudly on one — it hoists the inner keys to
top level and clobbers their siblings. A nested block parses to
``{'mcp': '', 'servers': [...], 'command': 'npx'}``, silently corrupting the
entry's metadata. Teaching the parser nested mappings would change the shape of
every catalog entry's ``meta`` (and every consumer of it), so the declaration
meets the parser where it already works and the full specs live in the standard
sidecar file that needs no parser at all.

Everything here is pure and I/O-free, like :mod:`boost_cli.core.resolve` and
:mod:`boost_cli.core.staleness`: callers read the files and pass text in, so
every branch of the *decision* is unit-testable and reachable by the mutation
gate.
"""
from __future__ import annotations

import json

from . import mcphost

# The frontmatter key a skill uses to name the servers it needs.
DECL_KEY = "mcp"

# The sidecar file a skill bundles to carry full server specs. Standard MCP
# filename and shape, so an author can lift the file straight from a server's
# own README.
SIDECAR = ".mcp.json"

# Top-level key inside .mcp.json, per the MCP config convention.
SERVERS_KEY = "mcpServers"

# Ownership tag written alongside a server boost registered, mirroring
# claude_settings.MARKER. Without it an uninstall could not tell a
# boost-registered server from one the user configured by hand, so it would
# either strip the user's config or leak boost's.
MARKER_KEY = "x-boost-skill"


def declared_names(meta: dict | None) -> list[str]:
    """Server names a skill's frontmatter declares, de-duped, order preserved.

    Accepts a YAML list or a comma-separated string and drops blanks — the same
    contract ``requires:``/``conflicts:`` use, so an author who knows one knows
    this one. A missing/empty/``False`` value means "declares nothing".
    """
    val = (meta or {}).get(DECL_KEY)
    if val in (None, "", False):
        return []
    raw = ([str(x) for x in val] if isinstance(val, list)
           else str(val).split(","))
    out: list[str] = []
    for item in raw:
        name = item.strip()
        if name and name not in out:
            out.append(name)
    return out


def parse_sidecar(text: str | None) -> dict[str, dict]:
    """``{name: spec}`` from a bundled ``.mcp.json``'s text.

    Tolerant by design: unreadable JSON, a non-object document, a missing or
    non-object ``mcpServers`` key, and non-object individual specs all read as
    "no specs". A malformed sidecar must never make an otherwise-fine install
    fail — the skill still works, the user just does not get the wiring offer.
    """
    if not text:
        return {}
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    servers = doc.get(SERVERS_KEY)
    if not isinstance(servers, dict):
        return {}
    return {str(k): v for k, v in servers.items()
            if k and isinstance(v, dict)}


def servers_for(meta: dict | None, sidecar_text: str | None = None,
                ) -> list[dict]:
    """Every MCP server a skill needs, as ``{"name", "spec", "source"}`` rows.

    Merges the two declaration forms. A name in *both* uses the sidecar's spec —
    the frontmatter only names a server, so a bundled spec is strictly more
    information. ``spec`` is ``None`` for a name-only declaration, which the
    caller renders as "you need this, here is no command to run it" rather than
    offering a registration it cannot perform.

    ``source`` is ``"sidecar"`` or ``"frontmatter"``, so output can tell the user
    where a requirement came from when the two disagree. Rows are sorted by name
    for deterministic output.
    """
    specs = parse_sidecar(sidecar_text)
    rows: dict[str, dict] = {
        name: {"name": name, "spec": spec, "source": "sidecar"}
        for name, spec in specs.items()}
    for name in declared_names(meta):
        if name not in rows:
            rows[name] = {"name": name, "spec": None, "source": "frontmatter"}
    return [rows[k] for k in sorted(rows)]


def registrable(rows) -> list[dict]:
    """The rows boost can actually wire up — those carrying a runnable spec.

    A spec is runnable when it names a ``command``. Anything else (a name-only
    frontmatter declaration, or a sidecar entry describing a remote/URL server
    boost has no launcher for) is reported to the user but never auto-registered:
    boost will not invent a command line on an author's behalf.
    """
    return [r for r in rows
            if isinstance(r.get("spec"), dict)
            and str(r["spec"].get("command") or "").strip()]


def register_argv(name: str, spec: dict, *, scope: str = "user",
                  host: str = mcphost.CLAUDE) -> list[str]:
    """The ``<host> mcp add`` argv that registers one declared server.

    Mirrors :mod:`boost_cli.core.mcphost`'s per-host grammar exactly, because
    the two build the same command for different servers and a divergence would
    only show up on someone else's machine. For Claude the server **name**
    precedes every ``-e`` flag (its ``-e`` is variadic, so a name after it is
    swallowed as another env var) and a bare ``--`` separates boost's flags from
    the server's own command; for Gemini the flags precede the name and there is
    no ``--``, which would be passed through as a literal argument.

    ``host`` defaults to Claude Code so existing callers are unchanged.
    """
    exe = mcphost.cli(host)
    env = spec.get("env")
    flags: list[str] = []
    if isinstance(env, dict):
        for key in sorted(env):
            flags += ["-e", "%s=%s" % (key, env[key])]
    command = str(spec["command"])
    args = spec.get("args")
    tail = [str(a) for a in args] if isinstance(args, list) else []
    if host == mcphost.GEMINI:
        return [exe, "mcp", "add", "--scope", scope, *flags,
                name, command, *tail]
    return [exe, "mcp", "add", name, "--scope", scope, *flags,
            "--", command, *tail]


def merge_into(existing: dict | None, rows, skill: str) -> tuple[dict, list[str]]:
    """Add ``rows``' specs to an ``.mcp.json`` document -> ``(doc, added)``.

    Returns a **new** document rather than mutating the caller's, and never
    overwrites a server the user already configured: a name already present is
    left exactly as-is and omitted from ``added``. Each entry boost does add
    carries a :data:`MARKER_KEY` naming the skill that asked for it, so a later
    uninstall can remove precisely what boost wrote and nothing else.
    """
    doc = dict(existing) if isinstance(existing, dict) else {}
    servers = dict(doc.get(SERVERS_KEY) or {})
    added: list[str] = []
    for row in registrable(rows):
        name = row["name"]
        if name in servers:
            continue
        entry = dict(row["spec"])
        entry[MARKER_KEY] = skill
        servers[name] = entry
        added.append(name)
    doc[SERVERS_KEY] = servers
    return doc, added


def strip_owned(existing: dict | None, skill: str) -> tuple[dict, list[str]]:
    """Remove the servers boost registered for ``skill`` -> ``(doc, removed)``.

    Only entries whose :data:`MARKER_KEY` names this skill are removed, so a
    server the user configured by hand — or one another skill still needs —
    survives an uninstall untouched.
    """
    doc = dict(existing) if isinstance(existing, dict) else {}
    servers = dict(doc.get(SERVERS_KEY) or {})
    removed = [name for name, spec in servers.items()
               if isinstance(spec, dict) and spec.get(MARKER_KEY) == skill]
    for name in removed:
        del servers[name]
    doc[SERVERS_KEY] = servers
    return doc, sorted(removed)
