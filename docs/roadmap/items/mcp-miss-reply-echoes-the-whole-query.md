---
id: mcp-miss-reply-echoes-the-whole-query
board: code
section: planned
status: shipped
owner: loop/mcp-miss-truncates-query
pr: "968"
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
<b>Fixed.</b> <code>mcp.echo()</code> bounds every echoed string at
<code>QUERY_ECHO_CHARS</code> (120), collapsing whitespace first so a query of 100,000 newlines
cannot beat the cut, and cutting on a word boundary when there is one. Both echoing branches take
it: the plain miss, and the unsearchable-term branch, which also lists at most
<code>ECHO_TERMS</code> (8) terms and counts the rest — a query of 500 punctuation marks used to
name all 500. 120 is not arbitrary: the longest of the 141 graded queries across
<code>tests/eval/golden.jsonl</code> and <code>golden-natural.jsonl</code> is 87 characters, so the
cap never fires on a real question and the functional suite's reply assertions stay byte-identical.
Nine tests pin it, and all five fail against the unbounded version.
