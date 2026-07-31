---
id: prerequisites-and-semantic-search-setup
board: code
section: docsite
status: planned
category: Docs · Setup
complexity: M
impact: High
wow: 3
note: silent BM25-only is the default outcome
order: 58
owner:
pr:
title: Nothing tells a user semantic search is off — not the README, not <code>search</code>, not <code>/mcp</code>
---
Dense retrieval needs three separate things to line up — the <code>[rag]</code>
extra (<code>sqlite-vec</code>), an embeddings key (<code>VOYAGE_API_KEY</code> or
<code>OPENAI_API_KEY</code>), <em>and</em> a built vector store
(<code>boost reindex --dense</code>) — and every one of them fails
<em>silently</em>: <code>rag.retrieve_any</code> floors to BM25 and returns, so a
user who installed the extra but never set a key, or set a key but never
reindexed, has no way to learn that the semantic search they think they enabled
has never once run. Three gaps to close:
<b>(1) README.</b> Prerequisites live in half a sentence (&ldquo;Needs Python 3.9+
and <code>git</code>&rdquo;) and the optional stack is buried in Install prose.
Give required vs. optional prerequisites a dedicated
<b>Configuring semantic search</b> section, and automate the optional install the
way <code>requirements/*.txt</code> already does for the toolchain, so it is one
command rather than three remembered ones.
<b>(2) Surfacing.</b> <code>cmd_search</code> prints which engine <em>ran</em> but
never that a better one is available — <code>embed.fallback_note()</code> exists
and is only wired into <code>reindex --dense</code>. Say it on search too, and
put engine state in the MCP <code>initialize</code> response
(<code>serverInfo</code>/<code>instructions</code>) so an agent reading
<code>/mcp</code> can see &ldquo;BM25 only — dense not configured&rdquo; instead of
assuming vector search.
<b>(3) Stale docs.</b> <code>mcp-hub.html</code> still advertises
<code>voyage-3</code> (1024-d) in the pipeline diagram and the Phase&nbsp;2
details block; <code>core/embed.py</code> has pinned <code>voyage-4</code> since
the complimentary-token change. Same sweep should catch any other drifted model
or extra names across <code>docs/*.html</code>.
