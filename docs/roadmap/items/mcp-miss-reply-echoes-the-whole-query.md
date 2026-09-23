---
id: mcp-miss-reply-echoes-the-whole-query
board: code
section: planned
status: planned
category: MCP · UX
complexity: S
impact: Low
wow: 2
note: The one reply an agent hits repeatedly while rephrasing costs context in proportion to the query…
order: 342
title: A search that finds nothing echoes the whole query back into the agent's context
---
<b>Found by the audit of the MCP surface.</b> <code>mcp.no_results</code> returns
<code>"no skills match %r" % query</code>, unbounded, and the miss reply is the one an agent hits
repeatedly while it rephrases. Every miss therefore costs context in proportion to the query rather
than a fixed line — a 1:1 amplifier on a surface where the result rendering elsewhere is measured
and capped. A 100,000-character query comes back whole.
<br><br>
<b>Fix.</b> Truncate the echoed query the way the result rows are already truncated, and pin the cap
in the round-trip tests.
