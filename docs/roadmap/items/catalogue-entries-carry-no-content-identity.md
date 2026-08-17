---
id: catalogue-entries-carry-no-content-identity
board: code
section: internals
status: shipped
category: Catalog · Correctness
complexity: M
impact: High
wow: 5
note: 42.9% of 750,416 embedded chunks are duplicates — one was embedded 1,464 times
order: 116
owner: feat/catalogue-content-identity
pr:
title: A catalog entry knew where it came from, never what it was
---
<b>boost collapses duplicate copies at both places a user sees them</b> &mdash;
<code>rag.dedupe_by_content</code> for search results, <code>resolve_one</code> for install
resolution &mdash; and at neither place it <em>pays</em> for them. A catalog entry carried
<code>(tap, skill_md)</code>, which is row identity and deliberately strict, but nothing that said
<em>this is the same thing as that</em>. Every consumer needing content identity therefore derived
its own, and they disagreed.

<b>The bill was measurable.</b> On a real 460-tap install <code>rag_vectors.sqlite</code> is
<b>3.2&nbsp;GB</b>, and <b>42.9% of its 750,416 chunks are duplicates</b> &mdash; one chunk was
embedded <b>1,464 times</b>. Those embeddings cost API credits and buy nothing:
<code>retrieve_any</code> runs <code>dedupe_by_content</code> on every retrieval path, so each
redundant vector is computed, stored, billed, then discarded before it can reach a result slot.

<b>Three keys were in play, and the comment was wrong about which one shipped.</b>
<code>dedupe_by_content</code>'s docstring says clustering is &ldquo;on the body, never the name&rdquo;
and offers as proof that no cluster spans more than one name. Both are artefacts: the code hashes
<code>read_body()</code>, which <em>prepends</em> name and description, so zero name-spanning clusters
is guaranteed rather than measured. Over all 60,047 entries:

<b>name + description + body</b> keeps 41,051 clusters and spans more than one name <b>zero</b> times
&middot; <em>body alone</em> keeps 40,372 but spans more than one name <b>259</b> times, which is the
<code>admin-interface-rule</code> collision again &middot; <em>name + description</em> keeps 37,668,
over-collapsing <b>3,383</b> clusters of items that share metadata while carrying different prose.

<b>So the entry now carries the digest the code already believed in.</b>
<code>_make_entry</code> hashes name + description + body at scan time, which is free &mdash; the
body is already read, parsed and about to be discarded, measured at <b>2.04&nbsp;&micro;s per entry,
122&nbsp;ms for the whole corpus</b>. It also <em>removes</em> work: <code>rag</code> was re-opening
all 60k files at index-build time purely to recompute this. Verified against real data by rescanning
40 tapped repos and checking all <b>8,564</b> entries against what <code>read_body</code> hashes:
zero mismatches.

<b>Nothing is dropped.</b> Duplicate rows stay in the catalogue, because removing them breaks
<code>--path</code> disambiguation, typosquat detection, tap-scoped repair in <code>sync_apply</code>,
the eval harness's exemplar resolution, and the <code>source_rank</code> quality prior. The mark is
the digest, and it is reversible by rebuilding a cache. The tap cache gained a
<code>format</code> version to backfill 460 machines' worth of caches on read &mdash; it was the one
derived artifact that could not self-invalidate, which is why no entry field could ever be added
before. A stale cache whose clone is gone is still served rather than discarded: consumers all
degrade cleanly on a missing digest, so refusing to answer would cost a user their catalogue to buy
a hash.
