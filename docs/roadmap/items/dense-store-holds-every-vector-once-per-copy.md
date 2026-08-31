---
id: dense-store-holds-every-vector-once-per-copy
board: code
section: internals
status: inflight
category: Search · Storage
complexity: L
impact: Med
wow: 3
note: 39.7% of vector rows are byte-identical repeats; 1.43x whole-store, no re-embedding
order: 128
owner: loop/dense-store-dedup
pr:
title: The dense store keeps one vector per <em>copy</em>, not one per distinct text
---
<code>_embed_and_store</code> already buys each distinct text <b>once</b> &mdash; <code>seen</code>
de-duplicates before the provider call, which is why <code>build</code>'s progress total counts
distinct texts rather than rows. The <em>storage</em> never got the same treatment: every chunk row
still gets its own <code>vec_raw</code> blob and its own <code>vec_chunks_bin</code> row, so a text
vendored into 1,464 skills is stored 1,464 times.

<b>Measured on a real store</b> (657,587 chunks, 384-d <code>BAAI/bge-small-en-v1.5</code>):
657,587 vector rows collapse to <b>396,638 distinct</b> &mdash; 39.7% repeats, <b>1.658&times;</b>.
The earlier 750,416-chunk / 1024-d Voyage store measured 42.9%, so the ratio is a property of the
corpus rather than of one embedder.

<b>State the payoff in the right scope.</b> The <code>#544</code> note said &ldquo;~1.75&times;&rdquo;
without saying of what, and that reads as a whole-store number. It is not. From <code>dbstat</code>
on the live file: <code>vec_raw</code> 1,287.6&nbsp;MB and <code>vec_chunks_bin</code> 45.1&nbsp;MB
of a 1,634&nbsp;MB total, so vectors are <b>81.6%</b> of the file. Deduplicating them saves
<b>529&nbsp;MB</b>; add back a <code>vid</code> column, a hash index and a <code>chunks(vid)</code>
index and the honest figure is <b>1,634 &rarr; ~1,140&nbsp;MB, 1.43&times; whole-store</b>. On a
1024-d store, where vectors are ~90% of the file, it lands nearer 1.6&times;.

<b>The key must be the embedding blob, not the text &mdash; and this is the constraint that decides
the design.</b> <code>export_shard</code> emits <code>name/tap/path/kind/cix/snip/digest/embedding</code>
and <code>snip</code> is <code>text[:200]</code>: <b>the full chunk text is not in the store and not
in the shard</b>, so <code>import_shard</code> has nothing to hash. A <code>text_hash</code> column
is unpopulatable on the import path. <code>sha256(embedding)</code> is equivalent by construction
&mdash; identical texts are embedded once and serialize to identical bytes &mdash; and it works for
imports and for the migration.

<b>No join table.</b> <code>#544</code> proposed a chunk&rarr;tap join table; <code>chunks</code>
already <em>is</em> that table and already carries <code>tap</code>. The change is one
<code>vid</code> column on <code>chunks</code>, a <code>vectors</code> relation, and
<code>vec_chunks_bin</code> keyed by <code>vid</code>.

<b>Three things break, and one of them is an ordering.</b> <code>_delete_matching</code> drops
vectors <em>then</em> rows; refcounted GC must run <em>after</em> the row delete or it counts
references about to vanish. <code>_store_vector</code>'s orphan guard stops being sufficient, because
under dedup a <code>_COMMIT_EVERY</code> interrupt makes orphans structural rather than exceptional.
And <code>export_shard</code>'s <code>v.id = c.id</code> join becomes <code>v.vid = c.vid</code>
&mdash; the same shape whose breakage the docstring already records as having killed two scheduled
<code>shards</code> runs.

<b>In place, not an <code>INDEX_VERSION</code> bump.</b> Every input is already on disk, so the
migration re-encodes rather than re-embeds &mdash; the posture <code>quantize()</code> established,
and roughly its cost (~1360&nbsp;s, ~2&times; peak while both copies coexist), except that this one
ends <em>smaller</em>. <code>dense.py</code> promises in writing that v3's re-embed is
&ldquo;the last one this mechanism needs&rdquo;; a v4 wipe would charge every user a full re-embed
to reclaim disk, which is the wrong trade even where the embedder is free.

<b>The quality half is already fixed, and this card is not blocked on it.</b>
<code>MAX_PER_VECTOR</code> thins the candidate pool and caps the page, which is what stopped one
1,464-copy cluster taking 60 of 60 result slots. Dedup would make the pool distinct
<em>structurally</em> rather than by thinning, and would let <code>_knn</code> stop hashing 2,048
blobs per query &mdash; a simplification, not a rescue.

<b>The free bonus nobody has claimed:</b> <code>seen</code> in <code>_embed_and_store</code> is a
local rebuilt per call, so reuse is <em>per build</em>. A persisted blob-keyed table makes it
cross-build and cross-tap: a newly tapped mirror registry would cost zero embeddings.

<b>Biggest risk, named:</b> a third schema state. The store already branches float32 vs quantized
through every vector-touching function; &ldquo;deduplicated or not&rdquo; makes four combinations,
each needing mutant-killing tests. And the one invariant that catches silent corruption &mdash;
<code>test_dense_entry_reuse.py</code>'s two-way <code>chunks.id</code> &harr; <code>vec_raw.id</code>
bijection &mdash; must be <b>rewritten</b> rather than extended, because dedup breaks one direction
by design. Its replacement: every <code>chunks.vid</code> resolves, and every <code>vectors</code>
row has at least one referent.
