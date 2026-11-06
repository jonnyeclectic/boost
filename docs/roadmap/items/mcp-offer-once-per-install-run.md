---
id: mcp-offer-once-per-install-run
board: code
section: planned
status: planned
category: MCP · UX
complexity: S
impact: Med
wow: 2
note: a tap with k skills that declare servers asks the registration question k times
order: 380
title: "<code>install &lt;tap&gt;</code> asks about MCP servers once per skill, not once per run"
---
<code>_offer_mcp</code> runs from <code>_report_result</code>, once for each installed item. So a tap
whose skills declare MCP servers asks <em>register N servers…?</em> once per declaring skill, partway
through the install output, after <code>-y</code> has already settled the skill list.

<b>Fix.</b> Collect the declared servers across the run and ask once at the end. The question lists
every server's command line, and a decline prints every <code>&lt;host&gt; mcp add</code> line. A
single-skill install reads the same as it does today.
