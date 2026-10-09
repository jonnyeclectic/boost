---
id: publish-the-keyword-index
board: code
section: planned
status: shipped
category: Search · Performance
complexity: L
impact: High
wow: 4
note: 462 measured shards (75.7 MB gzip, one refused) import in ~20–23 s into a 59.3 MB store at 100% body text, where a bundle-only machine indexed 0%
order: 99
owner: loop/publish-keyword-index
pr: 1052
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

<b>Partly landed, and deliberately still <code>inflight</code> — 2026-09-10.</b> What shipped is
the half that needed no size decision: <b>the index now records what it is</b>.
<code>read_body_full</code> returns the text and whether it contains the item's body,
<code>build()</code> reports <code>metadata_only</code> over every document written (reused ones
included, or an incremental build reports zero on the run after a bundle import),
<code>index_completeness()</code> reads the share back off disk, and <code>boost reindex</code>
says it out loud instead of reporting the same confident count for a 6% index. The share is of
<b>tokens</b>, not documents: a bodyless entry still produces a document, so a document share sits
at 1.0 until it drops to 0.0. <code>INDEX_VERSION</code> moved to <b>9</b>, because the flag is
written only when a body is missing and absence may only be read as "complete" once no older
document can survive.

<b>What did NOT land:</b> <code>rag.export_shard</code> / <code>rag.import_shard</code>, the
per-registry assets, and the <code>manifest.json</code> rows — the publishing pipeline itself.
That half is what the payload-size question governs, and
<a href="#shrink-the-published-index">shrink-the-published-index</a> still has no answer: its claim
is <b>stale</b>, not active — branch <code>loop/shrink-postings-index</code> was last touched
2026-09-02, carries one commit, has no pull request, and is 394 commits behind
<code>main</code>. Someone should un-claim it. One structural finding for whoever takes it: doc
ids are positional (<code>_save</code> does <code>enumerate(docs)</code>), so the card's
"merge by offsetting <code>doc_id</code>" is sound as written — and the shard format should
serialize <em>logical</em> postings (digest → term → tf) rather than the SQLite layout, so the
interning that branch was attempting cannot invalidate a published shard.

<b>Shipped — the publishing half.</b> <code>rag.export_shard</code> builds one registry's
documents from its clone (and refuses a tap with none, so a bundle-only machine can never publish
its metadata index); the format is logical — each document's fields plus its own term table — so
merging is concatenation and no SQLite layout is ever published. <code>rag.import_shards</code>
verifies every shard before writing (engine, format, <code>INDEX_VERSION</code>, a commit equal to
the tap's with two absences refused, every document on its own tap with <code>l</code> equal to
the sum of its <code>tf</code>) and merges the survivors in <b>one</b> write. Rows ride the same
<code>manifest.json</code> under a <code>keyword</code> section, so <code>MANIFEST_VERSION</code>
stays 1 and older clients keep their vectors; sha256, same-host URLs and the four-state
carry-forward are the dense rules, reused rather than copied. <code>shards.yml</code> exports
them before the dense step untaps anything, writing each one to a temp file and renaming it
into place so a killed job never leaves a partial <code>.keyword.json.gz</code>; a file the
publish job still cannot inflate is logged, deleted (so <code>--clobber</code> cannot replace the
good asset of that name) and treated as unreported, carrying its previous row instead of
aborting the manifest step and the dense rows with it. <code>boost reindex --fetch-index</code>
imports them on any machine, keyless included. "Already current" means the index holds the tap
<em>with bodies</em> at that commit — a commit-only test would have called the 6% index current
and never fetched the fix.

<b>Measured</b>, re-deriving every registry's shard read-only from a real 462-tap index (62,362
docs, 20,108,624 postings): <b>280.8&nbsp;MB</b> of canonical JSON, <b>75.7&nbsp;MB</b> as 462
gzip&nbsp;-9 files (median 42.9&nbsp;KB, largest 14.2&nbsp;MB). Those were derived from the index,
not from <code>export_shard</code>, and nothing is on the release yet: CI can publish at most 461,
because <code>export_shard</code> refuses <code>boost/builtin</code> (no clone, no commit), whose
file is counted in the 75.7&nbsp;MB. Importing all of them into an empty sandbox wrote a
<b>59.3&nbsp;MB</b> postings store — the v10 size — at <code>body_share</code> 1.0, in
<b>17–20&nbsp;s</b> for the import plus <b>~3&nbsp;s</b> to inflate the gzip on an idle machine
(a reviewer measured 54&nbsp;s under load). One shard was refused, correctly:
<code>boost/builtin</code> has no commit, and an unknown commit is never a match.
<b>The cost is memory:</b> the import is one batch, so every inflated shard, the old index's
documents and the merged postings are held at once — <b>~2.86&nbsp;GB peak RSS</b> for the whole
catalogue (measured twice). That is the price of one write instead of 461; a machine that cannot
afford it can fetch a subset by tapping fewer registries first. End to end on
the fixture: a clone-less index scores 0 for a body-only word; after
<code>--fetch-index</code> it finds the item, and the next <code>boost reindex</code> reuses the
import instead of regressing to metadata. The weekly CI run itself cannot execute locally; its
wiring is pinned statically in <code>tests/unit/test_keyword_shards.py</code>.
