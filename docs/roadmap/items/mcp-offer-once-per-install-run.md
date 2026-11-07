---
id: mcp-offer-once-per-install-run
board: code
section: planned
status: shipped
category: MCP · UX
complexity: S
impact: Med
wow: 2
note: a tap with k skills that declare servers asks the registration question k times
order: 380
owner: loop/mcp-offer-cards
title: "<code>install &lt;tap&gt;</code> asks about MCP servers once per skill, not once per run"
---
<code>_offer_mcp</code> runs from <code>_report_result</code>, once for each installed item. So a tap
whose skills declare MCP servers asks <em>register N servers…?</em> once per declaring skill, partway
through the install output, after <code>-y</code> has already settled the skill list.

<b>Fix.</b> Collect the declared servers across the run and ask once at the end. The question lists
every server's command line, and a decline prints every <code>&lt;host&gt; mcp add</code> line. A
single-skill install reads the same as it does today.

<b>Shipped.</b> A run that installs several items collects their user-scope results and asks once,
after the last item's report: one block lists every declared server with its command and the skills
that need it, a decline prints every <code>&lt;host&gt; mcp add</code> line, and a server two skills
declare is registered once. A second skill that declares the same server with a different command
is named and not offered. <code>-y</code> still answers only the list; a typed <code>y</code> or
<code>BOOST_ASSUME_YES</code> answers the offer. A project-scope result keeps its own
<code>.mcp.json</code> line, and one declaring skill reads as it did.
