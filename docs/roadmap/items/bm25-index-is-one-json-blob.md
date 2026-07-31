---
id: bm25-index-is-one-json-blob
board: code
section: pipeline
status: planned
category: Search · Index
complexity: L
impact: High
wow: 5
note: 2.5 GB RSS per search at 50k items
order: 72
owner:
pr:
title: The BM25 index is one JSON blob, and it stops working between 10k and 50k items
---
<code>rag.py</code> persists the whole index as a single JSON file and
<code>json.loads</code> it on every invocation. <code>_CACHE</code>
(<code>rag.py:275</code>) is process-local, so a long-lived MCP server amortises
the cost but <b>every cold <code>boost search</code> pays it in full</b>.
Measured on a synthetic corpus of real repo prose, 10k items &rarr; 50k items:<br>
index on disk 52.7 MB &rarr; <b>270 MB</b>;<br>
<code>json.loads</code> per search 2.0&ndash;2.9 s &rarr; <b>12.2&ndash;13.6 s</b>;<br>
peak RSS 702 MB &rarr; <b>2.49 GB</b>;<br>
BM25 scoring itself 31 ms &rarr; 70 ms &mdash; cold start dominates by ~200&times;.
On a real 83-tap install the index is already 132 MB at 11.1k entries. Scaling
that shape to 50k gives ~594 MB and ~5.7 GB resident. <b>Target RSS, not
bytes</b>: Python object overhead was measured at a consistent 9.5–9.6× file
size across three independent runs, which is what OOM-kills an 8 GB machine
while the disk figure still looks survivable.
Two cheap wins come first and are worth landing on their own.
<b>(1) Stop chunking.</b> An unchunked index with the item's surface
(name + de-hyphenated name + description) counted alongside the body scored
<code>recall@10 0.742 / hit@1 0.429</code> at <b>41 MB and 0.43 s</b> to load,
versus the live chunked index's <code>0.720 / 0.407</code> at <b>132 MB and
8–13 s</b> — better on every metric, 3.2× smaller, 20× faster to load.
<b>(2) Get postings out of JSON.</b> FTS5 is compiled into CPython's bundled
sqlite (verified: 3.53.4, <code>ENABLE_FTS5</code>), so there is a
zero-dependency path — but probe it at runtime, because that is a per-build
property, not a guarantee. A compact mmap-able binary postings format is the
alternative. Either way <code>snip</code> text (46.7 MB of the 132 MB) belongs
out of the hot path.
Also note <code>build()</code>'s incremental path is O(entire corpus): reusing
unchanged taps runs <code>_kept_docs</code> → <code>_postings_to_doc_tf</code>,
which inverts every posting in the index — measured 35 s and 1.72 GB RSS at
11.1k entries to reindex a single changed file.
