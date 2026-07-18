---
id: extract-mcp-http-servers-out-of-configuration-py
board: code
section: internals
status: next
category: Tech-debt
complexity: L
impact: High
wow: 4
note: 
order: 5
owner:
pr:
title: Extract MCP + HTTP servers out of <code>configuration.py</code>
---
~290 lines implement a full HTTP catalog server <b>and</b> a JSON-RPC 2.0 MCP server — with search/install/doctor dispatch that duplicates the CLI — inside a "configuration" command module (<code>commands/configuration.py:741–1028</code>). Move to <code>core/mcp.py</code> / <code>core/serve.py</code>, leaving thin wrappers. It's the biggest driver of the file's 1,099 lines and nearly untestable in place.
