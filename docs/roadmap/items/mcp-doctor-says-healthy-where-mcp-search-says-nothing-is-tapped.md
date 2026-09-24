---
id: mcp-doctor-says-healthy-where-mcp-search-says-nothing-is-tapped
board: code
section: planned
status: shipped
category: MCP · Bug
complexity: S
impact: Medium
wow: 3
note: Two tools, one session, opposite answers about the same first-run machine…
order: 340
owner: loop/mcp-doctor-counts-configured-taps
pr: 959
title: boost_doctor certifies a machine healthy that boost_search calls untapped
---
<b>Found by the audit of the MCP surface.</b> <code>_tool_doctor</code> counts taps with
<code>registry.list_taps()</code>, which includes boost's own wheel-shipped <code>boost/builtin</code>
tap, while <code>mcp.no_results</code> and <code>mcp.coverage_line</code> count with
<code>builtin.configured_tap_count()</code>, which deliberately excludes it. On a machine holding the
builtin tap and nothing else — exactly what <code>boost mcp</code> leaves behind when the user
accepts the boost-first rule and has not yet run <code>boost tap --defaults</code> — an agent calling
both tools in one session is told <code>taps: 1 (1 items available)</code> and <i>healthy — no issues
found</i> by one, and <i>nothing is tapped yet, so there is no catalog to search</i> by the other.
<br><br>
The requirement is already written down in the code that breaks it: <code>_tool_doctor</code>'s own
comment says <i>same command, same order, as mcp.no_results: an agent that calls both tools in one
session must not see the recommendation flipped</i>, and
<code>configured_tap_count</code>'s docstring claims <code>boost_doctor</code> asks through it. It
does not.
<br><br>
<b>Fix.</b> Count with <code>builtin.configured_tap_count()</code> for the "is anything configured"
question, keeping <code>list_taps()</code> where the literal clone list is meant, and test both tools
against one builtin-only HOME.
