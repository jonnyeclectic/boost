---
id: prerequisites-and-semantic-search-setup
board: code
section: docsite
status: shipped
category: Docs · Setup
complexity: M
impact: High
wow: 3
note: silent BM25-only is the default outcome
order: 58
owner: loop/semantic-search-setup
pr: 361
title: Nothing tells a user semantic search is off — not the README, not <code>search</code>, not <code>/mcp</code>
---
<b>Shipped.</b> Dense retrieval needs things to line up — the <code>[rag]</code>
extra (<code>sqlite-vec</code> plus a bundled local model, so an embeddings key
is now a quality upgrade rather than the entry fee) <em>and</em> a built vector
store (<code>boost reindex --dense</code>) — and every one of them failed
<em>silently</em>: <code>rag.retrieve_any</code> floors to BM25 and returns, so a
user who installed the extra but never set a key, or set a key but never
reindexed, has no way to learn that the semantic search they think they enabled
had never once run. Three gaps, all closed:
<b>(1) README.</b> Prerequisites live in half a sentence (&ldquo;Needs Python 3.9+
and <code>git</code>&rdquo;) and the optional stack is buried in Install prose.
Give required vs. optional prerequisites a dedicated
<b>Configuring semantic search</b> section, and automate the optional install the
way <code>requirements/*.txt</code> already does for the toolchain, so it is one
command rather than three remembered ones.
<b>(2) Surfacing.</b> <code>cmd_search</code> printed which engine <em>ran</em> but
never that a better one was available — <code>embed.fallback_note()</code> exists
and is only wired into <code>reindex --dense</code>. Now said on search — including the
zero-results path, where a keyword engine finding nothing is exactly what a
semantic one is for — and silent when vectors already served or output is
<code>--json</code>. The remedy table moved out of <code>commands/quality.py</code>
into <code>core.dense.fix_hint</code>, so <code>doctor</code> and
<code>search</code> cannot give contradictory advice; it had no tests at all,
which is how its &ldquo;set an API key&rdquo; entry went stale. Engine state also
lands in the MCP <code>initialize</code> <code>instructions</code>, appended at
connect time, so an agent reading <code>/mcp</code> sees
&ldquo;BM25 keyword matching only&rdquo; instead of assuming vector search.
<b>(3) Stale docs.</b> <code>mcp-hub.html</code> advertised
<code>voyage-3</code> (1024-d) in the pipeline diagram and the Phase&nbsp;2
details block; <code>core/embed.py</code> has pinned <code>voyage-4</code> since
the complimentary-token change; the sweep also caught the diagram and prose
still calling a key mandatory, and the same claim in <code>CLAUDE.md</code>.
Three environment-dependent tests were fixed on the way: they asserted answers
that were only correct where the <code>[rag]</code> extra was <em>absent</em>,
so they were green on CI and red on any machine that had installed it.
