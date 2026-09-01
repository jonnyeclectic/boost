---
id: publish-the-keyword-index
board: code
section: planned
status: planned
category: Search · Performance
complexity: L
impact: High
wow: 4
note: every machine rebuilds 697 MB of index for a corpus that is byte-identical on all of them
order: 99
title: publish the keyword index the way vectors are published
---
Dense vectors are built once in CI and downloaded. The BM25 index is not:
<code>core/rag.py</code> has <b>no export or import function at all</b>, and
<code>shards.yml</code> / <code>scripts/publish_shards.py</code> are dense-only end to end. Every
install rebuilds the same index from the same registries, at the same pinned commits, to produce
the same bytes.

<b>Measured, on a real 458-tap machine.</b> The on-disk index is
<code>rag_index.json</code> <b>43.7&nbsp;MB</b> plus <code>rag_postings.sqlite</code>
<b>653.0&nbsp;MB</b> — <b>696.7&nbsp;MB</b> for 18,619,658 postings. Build cost, timed over a
9,306-entry / 69-tap slice: <b>4.54&nbsp;s</b> reading bodies and tokenizing, <b>3.83&nbsp;s</b>
writing postings, <b>8.4&nbsp;s</b> total — about 0.9&nbsp;ms per entry, so roughly
<b>65&nbsp;s</b> and <b>~900&nbsp;MB</b> extrapolated to the full 71,700-entry catalogue.

<b>Which user actually pays it.</b> Not the default one: <code>boost quickstart</code> taps the
<b>7 starter registries</b> and indexes them in about a second. The cost lands on
<code>boost quickstart --catalog</code> — 463 registries, 2&nbsp;min 10&nbsp;s of parallel cloning
and then a minute of indexing on top — and on anyone who taps their way there gradually.

<b>The bug that makes this worth doing is not speed.</b> <code>boost catalog --import</code>
already exists and already looks like the answer: <i>shareable-catalogue-bundle</i> advertises
10.9&nbsp;MB replacing a 12&nbsp;GB clone and "59,972 searchable items in 4 seconds". That 4
seconds is fast for a reason the card does not state. <code>rag.read_body</code> degrades
<b>silently</b> to name + description when the item's clone is absent
(<code>rag.py</code>: "Missing files degrade to just the catalog metadata"), and a bundle import
restores catalogues with <i>zero repositories cloned</i>. So the index it builds is not the
full-content index the <code>evals</code> gate floors — it is a frontmatter index wearing the same
file name.

<b>Measured directly</b> over 3,015 real entries, indexing them with and then without their
clones: <b>3,041,326 tokens versus 182,507</b>. A bundle-only index carries <b>6.0%</b> of the
searchable text, and nothing in the output says so. That is the same failure shape as an
unpinned eval corpus — a number that still renders confidently while measuring something else.

<b>Why this is easier than the dense shards, not harder.</b> BM25 looks like it needs global
statistics, and it does — but none of them are frozen at build time. <code>_bm25</code> derives
<code>n = len(docs)</code> and <code>df = len(plist)</code> on <i>every query</i>, so IDF is
computed from whatever corpus is loaded. A per-registry shard therefore merges by offsetting
<code>doc_id</code>, unioning the postings, and recomputing <code>avg_len</code> from per-shard
totals — arithmetic, not re-derivation. And unlike vectors there is no embedding space to match
and no API key to hold, so <code>shards.incompatible()</code> has no analogue here: a published
keyword index is importable by everyone, including the keyless user who cannot use vectors at all.

<b>Shape.</b> <code>rag.export_shard</code> / <code>rag.import_shard</code> mirroring
<code>dense</code>'s pair, per-registry assets on the existing <code>shards-latest</code> release,
rows carried in the same <code>manifest.json</code> with the same commit pin and sha256 — the
carry-forward machinery in <code>publish_shards.py manifest --carry-forward</code> applies
unchanged, because a registry whose commit did not move has an index that did not change either.
Three invariants transfer verbatim from the dense side and each is load-bearing: verify before
replacing, refuse a shard whose commit is not the tap's commit, and never treat a missing digest
as a match.

<b>The open question is payload size</b>, and it is large enough to be its own decision — see
<a href="#shrink-the-published-index">shrink-the-published-index</a>. This card should not ship
until that one has an answer, because publishing 697&nbsp;MB per refresh to save 65&nbsp;s of CPU
is not obviously the right trade, and at the compressed sizes measured there it clearly is.
