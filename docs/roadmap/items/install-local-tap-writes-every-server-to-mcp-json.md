---
id: install-local-tap-writes-every-server-to-mcp-json
board: code
section: planned
status: planned
category: Safety · MCP
complexity: S
impact: Med
wow: 2
note: --local writes a whole tap's declared servers into the repo's .mcp.json without a prompt
order: 383
title: "<code>install &lt;tap&gt; --local</code> records every declared MCP server in <code>.mcp.json</code> unasked"
---
A project-scoped install records declared servers in the repo's <code>.mcp.json</code> with no
prompt, because the file is committed and reviewed. With a tap as NAME, one <code>-y</code> now
writes every server that the tap's skills declare. That may be dozens of third-party commands,
which every teammate's agent launches once the file is committed.

<b>Fix.</b> Name every server written in the project-scope report, which already prints
<em>recorded N servers</em>. Add a functional test that pins the whole-tap case.
