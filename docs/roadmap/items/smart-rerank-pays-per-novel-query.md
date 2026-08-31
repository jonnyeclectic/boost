---
id: smart-rerank-pays-per-novel-query
board: code
section: dx
status: shipped
category: Performance · MCP
complexity: S
impact: High
wow: 3
note: MCP boost_search measured 11.7-17 s per call — every call, even a repeat of the last one
order: 123
owner: loop/search-perf
pr: 543
title: The smart rerank pays the LLM again for a search it already answered
---
The MCP <code>boost_search</code> path passes <code>smart=True</code> on every
call and <i>mcp-search-cost-was-understated</i> measured it at 11.7-17.0 s —
nearly all of it the LLM rerank, paid again in full for a byte-identical
repeat of the previous search. Agents retry searches constantly (a session
restart, a re-planned task, a second agent asking the same question), so the
honest "10-15 seconds" cost doctrine was billing every ask at first-ask
prices.<br><br>
Shipped: <code>rag.rerank</code> keeps a small FIFO cache
(<code>~/.boost/cache/rerank_cache.json</code>, 200 entries, registered in
<code>paths.INTERNAL_CACHE_FILES</code> so <code>boost clean</code> spares
it) keyed on a sha256 of <b>exactly what the LLM sees</b> — query, limit, and
the candidate listing — so it self-invalidates on any reindex, ranking drift,
or snippet change without inspecting why. Only the parsed name order is
stored; a hit replays through the same deterministic reorder as a live reply
and keeps the <code>Claude relevance</code> label, because it is the LLM's
ordering. Degrade replies are never cached. <code>BOOST_NO_RERANK_CACHE=1</code>
bypasses read and write — the Tier 2a eval sets it, so a graded rerank is
always live. Both MCP cost surfaces (server instructions and the
<code>boost_search</code> description) now state the repeat-search cost, pinned
by the same agreement test that keeps them from drifting apart. Sibling of
<i>cold-search-reads-the-whole-catalogue</i>, which took the retrieval half of
the same search from 0.94 s to 0.49 s.
