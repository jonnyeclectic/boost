---
id: shrink-the-published-index
board: code
section: planned
status: planned
category: Performance · Storage
complexity: M
impact: Med
wow: 3
note: 653 MB of postings holds 1.4 MB of distinct terms — the term string is stored 88 times over
order: 100
title: shrink the keyword index before publishing it — structure first, then compression
---
<a href="#publish-the-keyword-index">publish-the-keyword-index</a> is worth doing only if the
artifact is small enough to ship weekly. This card is the measurement that decides it, and the
first answer is that <b>compression is the second lever, not the first</b>.

<b>What the format actually stores.</b> <code>_write_postings</code> creates
<code>postings (term TEXT, doc INTEGER, tf INTEGER)</code> and inserts one row per posting, so the
<i>term string is repeated in every row</i>. Measured on the real 458-tap store:
<b>18,619,658</b> rows over <b>210,422</b> distinct terms averaging <b>6.6</b> characters. That is
<b>~123&nbsp;MB of term text to carry 1.4&nbsp;MB of distinct term text — 88&times; redundancy</b>,
before the per-row and B-tree overhead that turns it into a 653&nbsp;MB file (page_size 4096,
167,174 pages, freelist 0, so it is not slack space).

<b>Compression measured on that file, as it stands:</b>

<b><code>rag_index.json</code></b> 43.7&nbsp;MB raw &middot; gzip&nbsp;-6 <b>10.6&nbsp;MB</b> (4.12&times;).<br>
<b><code>rag_postings.sqlite</code></b> 653.0&nbsp;MB raw &middot; gzip&nbsp;-6 201.7&nbsp;MB (3.23&times;) &middot; zstd&nbsp;-3 169.9&nbsp;MB (3.84&times;) &middot; <b>zstd&nbsp;-19 106.7&nbsp;MB (6.11&times;)</b>.

So even with no format change, <b>zstd -19 puts the whole index near 117&nbsp;MB</b> — under half
the ~300&nbsp;MB of dense vectors already published weekly. The trade is already good; the point
of this card is that it can be much better, and that the two levers compose.

<b>Structure first, and it is the bigger win.</b> Interning terms into
<code>terms(id, term)</code> with <code>postings(term_id, doc, tf)</code> removes ~123&nbsp;MB of
duplicated strings <i>and</i> shrinks the <code>postings_term</code> index from a text key to an
integer one. Beyond that, the classic inverted-index encodings apply directly because doc ids
within a term are ascending: delta-encode them, varint or bitpack the deltas, and store one blob
per term rather than one row per posting. Both shrink the file <b>on disk</b>, not just in
transit, which is the half a compressed download never gives back — the user still ends up with
653&nbsp;MB resident after import.

<b>What must not regress.</b> <code>read_postings</code> exists precisely so a query touches a
handful of terms instead of materialising the whole map — the change that took cold search from
8-13&nbsp;s and multiple GB resident to 31-70&nbsp;ms of scoring. A blob-per-term layout keeps
that property (one row read per query term, decoded on the spot); a scheme that requires decoding
neighbouring terms to find one does not. <code>_bm25</code> must stay byte-identical, as it did
through the SQLite move, and <code>TestBm25Math</code> is what says so.

<b>Decompression cost is the thing to measure, not assume.</b> zstd -19 is slow to compress and
fast to decompress, which is the right asymmetry for a weekly build feeding many imports — but
"fast" needs a number on the import path before it is a claim, next to the 0.12&nbsp;s that
importing dense rows costs today. A zstd dictionary trained across shards is the obvious follow-on
for the many-small-registries case, where per-shard compression has little context to work with.

<b>Deliverable.</b> A measured comparison — raw, interned, delta+varint, each &times; none/gzip/zstd
— on the real store, with import-side decode time beside each. That table is what tells
<a href="#publish-the-keyword-index">publish-the-keyword-index</a> what to ship, and it is worth
having even if publishing is declined: the on-disk win applies to every install today.
