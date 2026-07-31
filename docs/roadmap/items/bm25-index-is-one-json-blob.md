---
id: bm25-index-is-one-json-blob
board: code
section: pipeline
status: inflight
category: Search · Index
complexity: L
impact: High
wow: 5
note: 2.5 GB RSS per search at 50k items
order: 72
owner: loop/unchunked-bm25-index
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

<b>Win (1) is shipped, and the &ldquo;better on every metric&rdquo; claim did not survive
re-measurement.</b> On the pinned 6-tap corpus unchunking is a <em>trade</em>, not a free win, and
which way it falls depends entirely on the shape of the query.

On the keyword golden set &mdash; which grades items by <b>name</b> &mdash; recall@10 fell
1.000 &rarr; <b>0.978</b> and nDCG 0.895 &rarr; 0.882, while hit@1 rose 0.780 &rarr; <b>0.791</b>.
On the 50 natural-language queries in <code>golden-natural.jsonl</code>, over identical data, every
metric improved and not marginally: recall 0.690 &rarr; <b>0.750</b>, hit@1 0.240 &rarr; <b>0.340</b>,
MRR 0.382 &rarr; 0.474, nDCG 0.446 &rarr; 0.524. That +0.100 hit@1 is 5 of 50 queries, which is at
the edge of what 50 queries can resolve &mdash; worth stating rather than rounding up.

Index cost on the same corpus: <b>5.3 MB &rarr; 2.1 MB</b> and 3,740 documents &rarr; 743, one per
entry, with load time 0.032 s &rarr; 0.015 s. The card's headline figures are from an 83-tap install
where the constant factors are far larger; this is the small-scale confirmation of the same shape,
not a substitute for it.

Chunking's one real contribution was locality &mdash; a term only had to beat the length
normalisation of its own 1000-char window. BM25's <code>b</code> already does that, and
<code>retrieve</code> collapsed chunks back to one hit per entry regardless, so the extra documents
were built, stored, re-parsed on every cold search and then discarded. What chunking <em>did</em>
provide for free was name matching, since the name sat in whichever chunk contained it; one document
per entry has to state the surface explicitly, so <code>rag.surface</code> indexes the name, its
de-hyphenated form (<code>tokenize</code> does not split hyphens, so &ldquo;code reviewer&rdquo;
would otherwise never match <code>code-reviewer</code>) and the description alongside the body.

<b>Still open:</b> win (2), getting postings out of JSON &mdash; the FTS5 probe and the mmap-able
binary format are both untouched, as is moving <code>snip</code> text off the hot path. So is
<code>build()</code>'s O(entire-corpus) incremental path, which still inverts every posting to
reindex one changed file.
