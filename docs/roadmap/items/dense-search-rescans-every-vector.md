---
id: dense-search-rescans-every-vector
board: code
section: internals
status: inflight
category: Search · Performance
complexity: M
impact: High
wow: 5
note: 33.9s cold search; 28.2s of it was one brute-force scan of 3.08 GB
order: 1
owner: loop/dense-quantization
pr: 544
title: Every dense search re-scanned all 3.08&nbsp;GB of vectors &mdash; <code>vec0</code> has no ANN index
---
<b>A user reported <code>boost search "refactor UI with taste"</code> taking 34 seconds.</b> The
log agrees exactly: <code>done: boost search refactor UI with taste -&gt; rc=0 in 33943ms</code>,
and the same query four minutes later at <code>2458ms</code>.

<b>The 13.8x spread is not a cache, and chasing it as one is the trap here.</b> The fast runs were
not warm &mdash; they were <em>degraded</em>. <code>embed.embed()</code> failed (rate limit or a
dropped request), <code>dense.retrieve</code> returned <code>None</code>, and the search silently
fell back to BM25 and answered in 2.5&nbsp;s from a different engine. The label on the last line is
the tell: <code>ranked by full-content BM25</code> on the fast runs,
<code>ranked by hybrid RRF (BM25 + dense)</code> on the slow ones. So the honest reading is that
<b>every search that actually used the vector store cost ~30&nbsp;s</b>, and the cheap ones were
answers to a different question.

<b>Cause: <code>sqlite-vec</code>'s <code>vec0</code> is brute force by design.</b> There is no ANN
index; a <code>MATCH</code> computes a distance against every stored vector. This machine holds
<b>750,416 chunks &times; 1024-d float32 = 3.08&nbsp;GB</b>, and one query reads and scores all of
it. Measured directly, three runs on the real store: <b>26.8&nbsp;s, 28.2&nbsp;s, 30.3&nbsp;s</b> &mdash;
and stable across repeats, because it is arithmetic, not I/O that a page cache could absorb.

Two things that <em>looked</em> like the cause were measured and cleared:
<code>catalog.all_entries()</code> parses every tap catalog on the machine and costs
<b>0.427&nbsp;s cold / 0.005&nbsp;s warm</b>; the 46&nbsp;MB <code>rag_index.json</code> is
<b>0.020&nbsp;s to read and 0.101&nbsp;s to parse</b>. Neither is worth a forced reindex, and the
second was nearly "fixed" before it was measured.

<b>The fix is binary quantization with an exact rescore</b> &mdash; the standard two-stage, and the
first strategy in the RAG-optimization write-up the report came with. Rank on one bit per dimension
(128 bytes instead of 4096, <b>114&nbsp;MB instead of 3.08&nbsp;GB</b>, Hamming distance is a
popcount), then re-rank the survivors on their exact float32 vectors.

<b>Both stages are load-bearing, which the measurements settle rather than assert.</b> The binary
pass alone answers in 0.22&nbsp;s but recovers only <b>0.667</b> of the true top 60 &mdash; a real
quality regression, so shipping it alone would have traded correctness for the number in the
headline. Adding the rescore over 2048 candidates costs 0.35&nbsp;s and restores
<b>recall@60 = 1.000</b>: the same rows, in the same order. A 4096-candidate pool costs 0.57&nbsp;s
and returns the identical 60, so the pool is sized, not guessed.

<b>End to end on the real store: 28.2&nbsp;s &rarr; 1.05&nbsp;s, 27x, with identical results.</b> Re-run
afterwards against a genuinely migrated copy, through the shipped
<code>_knn</code> rather than a prototype: <b>37.9&nbsp;s &rarr; 2.0&nbsp;s, 19x, recall@60 = 1.000</b>
&mdash; both sides inflated by a concurrent mutation run, which is why the ratio and the recall are
the claim and the absolute seconds are not.

<b>The rescore needs a second relation, and that is the non-obvious part.</b> <code>vec0</code>
cannot fetch a row by rowid: <code>id IN (...)</code> against it plans as
<code>SCAN ... VIRTUAL TABLE</code>, and 256 single-row lookups measured <b>3.2&nbsp;s</b>. So the
exact vectors move to <code>vec_raw</code>, an ordinary <code>INTEGER PRIMARY KEY</code> table where
the same lookup is a b-tree descent. <code>vec_chunks_bin</code> ranks, <code>vec_raw</code>
re-ranks, and the old float32 <code>vec_chunks</code> is dropped &mdash; the same blobs, relocated.

<b>It costs disk, and an early draft of this card wrongly said it did not.</b> An ordinary table
pays overflow-page overhead on 4&nbsp;KB blobs that vec0's packed storage avoids, so
<code>vec_raw</code> lands ~12% larger than the table it replaces, and the binary index adds its own
114&nbsp;MB. Measured on the real store rather than predicted: <b>3.40&nbsp;GB &rarr; 3.87&nbsp;GB</b>,
a 14% permanent increase, and roughly double that at peak while both copies coexist. The migration
itself took <b>1360&nbsp;s</b>. Worth it for 19-27x on every query, but a trade, not a free win.

<b>Migration is offline and free.</b> <code>dense.quantize()</code> re-encodes vectors already on
disk: no provider call, no re-chunking, no cost. That matters more than it sounds &mdash;
re-embedding 750,416 chunks is a bill, so the migration counts rows into <code>vec_raw</code> and
<b>refuses to drop <code>vec_chunks</code> unless the copy is complete</b>. It runs from
<code>boost reindex --dense</code>, and <code>boost doctor</code> now names a ready-but-unquantized
store, which is the one state that is both fast to fix and expensive to leave.

<b>A second, smaller find on the same path, fixed alongside.</b> Both
<code>dense.ready()</code> and <code>dense.status()</code> ran <code>SELECT COUNT(*) FROM
chunks</code> on <em>every</em> search &mdash; <code>status()</code> only to decide the wording of
one muted hint line. <code>COUNT(*)</code> scans the <code>chunks_tap</code> covering index:
<b>8,419 pages / 34.5&nbsp;MB</b>, measured at <b>1.94&nbsp;s</b>. The total now comes from
<code>meta</code> (9 pages), emptiness from a <code>LIMIT 1</code> probe, and the exact scan only
when <code>boost doctor</code> asks for it: <b>702x fewer pages</b>, 1.94&nbsp;s &rarr;
0.003&nbsp;s. A legacy store reports its count as <em>unknown</em> rather than zero, because
<code>fix_hint</code> reads a zero as an unfinished install and would send that user to the one
remedy that re-embeds everything they already paid for.

<b>Not done here, worth its own card:</b> 42.9% of the 750,416 chunks are byte-identical texts that
were embedded once and stored per row. Deduplicating the vectors would cut the store a further
~1.75x on top of quantization, but it needs a chunk&rarr;tap join table, because
<code>chunks.tap</code> is what scopes tap deletion today.
