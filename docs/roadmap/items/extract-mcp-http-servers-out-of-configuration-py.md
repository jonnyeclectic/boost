---
id: extract-mcp-http-servers-out-of-configuration-py
board: code
section: shipped
status: shipped
category: Tech-debt
complexity: L
impact: High
wow: 4
note: two servers now testable in core
order: 5
owner: loop/extract-serve-mcp
pr: 106
title: Extract MCP + HTTP servers out of <code>configuration.py</code>
---
~200 lines implementing a full HTTP catalog server <b>and</b> a JSON-RPC 2.0 MCP
server lived inside the "configuration" command module — nearly untestable in
place. The JSON-RPC protocol now lives in <code>core/mcp.py</code> as a <em>pure</em>
<code>handle_request(req, *, version, registry)</code> plus a
<code>serve_stdio()</code> loop with injectable stdin/stdout; the HTTP server
moved to a new <code>core/serve.py</code> with a pure <code>route()</code>
function, <code>serve_page()</code>/<code>skill_text()</code>, and
<code>serve_http()</code>. <code>cmd_serve</code> and <code>cmd_mcp --stdio</code>
became thin wrappers. Behavior is preserved exactly (the full-server and
stdio-protocol functional tests pass unchanged) and the extracted core is pinned
by new unit tests covering every branch.
