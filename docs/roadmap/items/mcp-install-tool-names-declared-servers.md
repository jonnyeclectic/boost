---
id: mcp-install-tool-names-declared-servers
board: code
section: planned
status: shipped
category: MCP · UX
complexity: S
impact: Med
wow: 2
note: an agent installing through MCP never learns a human has to register the skill's server
order: 382
owner: loop/agent-awareness
pr: 1324
title: "MCP <code>boost_install</code> replies should name the servers a skill declares"
---
The MCP <code>boost_install</code> tool never registers servers, which is correct: an agent must
not grant itself machine-wide commands. But its reply does not say the skill declares any. So the
agent reports success, and the skill fails later for a reason nobody surfaced.

<b>Fix.</b> Add one line per declared server to the reply: its name, its command line, and the
<code>mcp add</code> line a human would run. This matches what the CLI's decline prints.
