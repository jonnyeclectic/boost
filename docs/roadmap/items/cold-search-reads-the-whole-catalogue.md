---
id: cold-search-reads-the-whole-catalogue
board: code
section: pipeline
status: shipped
category: Performance · Search
complexity: M
impact: High
wow: 4
note: 0.94 s cold search at 71.6k entries — ~0.5 s spent materialising data the top hits never use
order: 122
owner: loop/search-perf
pr: 542
title: A cold search materialises 71,600 entries to print five
---
Profiled cold <code>boost search</code> at real scale (458 taps, 71,600
entries): 0.94 s, of which <b>0.32 s</b> is <code>catalog.all_entries()</code>
parsing every tap cache on the machine (~100 MB of JSON) to build a
<code>live</code> map whose entries are only <i>displayed</i> for the final k
hits, <b>0.11 s</b> is <code>_passage</code> windowing a snippet for all
39,726 scored docs to show 60, and <b>0.12 s</b> is <code>dense.ready()</code>
importing numpy via sqlite_vec just to answer "no vector store". BM25 scoring
itself: 18 ms. The engine was fine; the packaging around it was the cost.<br><br>
Shipped: <code>rag.retrieve(entries=None)</code> now ranks off the index's own
doc metadata (name/hash/kind/length all live there already), runs the full
ranked list through <code>dedupe_by_content</code> with shadow entries carrying
the two fields <code>source_rank</code> reads, and materialises real entries
for just the survivors' taps — with a <b>byte-identical-or-fall-back</b>
contract: any survivor that fails to materialise reruns the query through the
explicit-<code>entries</code> path (the eval-gate path, unchanged). Snippets
window on returned hits only, on both paths; <code>dense.ready()</code> stats
before importing; <code>_load_raw</code> keys its cache on
<code>(mtime_ns, size)</code>. Measured after: <b>0.94 s → 0.49 s cold</b>.
Complement of the shipped <i>cache-the-catalog-entry-set-across-rag-queries</i>
(PR 114), which memoised <code>all_entries</code> per process — warm repeats
were already amortised; this removes the cold-start read entirely.<br><br>
Analysed and deliberately <b>deferred</b>: moving the per-doc
<code>snip</code> out of <code>rag_index.json</code> into the postings SQLite.
<i>bm25-index-is-one-json-blob</i> declined it at 743 entries (14% of the
JSON); at 71.6k the premise inverts — snips are ~76% (46 MB → 11.4 MB slim,
103 ms → 37 ms parse) — but an adversarial design review found the v6→v7
in-place migration can clobber a concurrently rebuilt pair without a
build-id pairing token, and a mixed-version machine (pipx CLI + long-running
MCP serve) thrashes full 71k-file reindexes across the version boundary.
66 ms does not buy that; if the recorded (tap, skill_md)-keyed postings
follow-up ever lands, fold the snip move into that single format bump.
Residual known cost: the "semantic search is off" hint imports the backend
(~0.1 s) on machines with the extra installed but no store built — the one
state where that line is the advice.
