---
id: shard-refresh-skips-processed-commits
board: code
section: internals
status: inflight
category: Search · Performance
complexity: S
impact: Med
wow: 2
note: a quickstart rerun re-downloads every shard the store already holds at that commit
order: 306
owner: loop/shard-sync-skip-built
pr:
title: "<code>quickstart</code> reruns re-download every shard; <code>shards.sync</code> never asks what is built"
---
From a user request: <em>"update PRs to not reprocess the same shards repeatedly. have a
progress map with commit sha or something."</em> The user-visible symptom: running
<code>boost quickstart</code> a second time — after an interrupt, after adding
<code>--catalog</code>, or just to re-check — downloads every published shard again (the largest
single shard is 129&nbsp;MB; a catalog-wide set runs to hundreds of MB) and re-inserts rows the
vector store already holds for exactly those commits. Nothing upstream changed; the run buys the
same bytes twice.

Half the premise is already solved, and the card narrows to the rest. The weekly publish side
skips correctly: <code>.github/workflows/shards.yml</code> asks
<code>publish_shards.py unchanged</code> before embedding and carries last week's manifest rows
forward, so an unmoved registry costs nothing. And the commit-SHA progress map the user asks for
<b>already exists</b>: the store's meta records per-tap commit
(<code>dense.tap_commits()</code>, <code>core/dense.py:292</code>) alongside provider/model/dim —
exactly the (registry, commit, embedding space) key requested. <code>boost update --shards</code>
consults it: <code>commands/pkg.py:918</code> passes <code>built=</code> and
<code>core/shards.py:440</code> skips a tap whose git commit, manifest commit and built commit all
agree, without downloading a byte.

The gap is <code>shards.sync()</code> (<code>core/shards.py:266</code>), the other ingest path. It
takes no <code>built</code> map at all: it refuses only on a tap-vs-manifest commit mismatch
(<code>core/shards.py:300</code>), then downloads and imports unconditionally
(<code>core/shards.py:311</code>) — and <code>dense.import_shard</code>
(<code>core/dense.py:747</code>) deletes and re-inserts the tap's rows. Its callers:
<code>commands/quickstart.py:197</code> (every quickstart),
<code>commands/discovery.py:351</code> (<code>boost reindex --fetch-shards</code>, the documented
"refresh vectors on demand" surface — a rerun re-downloads everything), and
<code>commands/pkg.py:870</code> (<code>_resync_vectors</code> after a plain
<code>boost update</code> moves taps — correct there, since moved taps need fresh vectors). So the
runs that pay are any repeat of <code>quickstart</code> or <code>reindex --fetch-shards</code>.

Fix: give <code>sync()</code> the same optional <code>built</code> map and triple-equality
short-circuit <code>ingest()</code> has, checked <b>before</b> the download, reporting
"current"; pass <code>dense.tap_commits()</code> from <code>quickstart</code> and
<code>reindex --fetch-shards</code>. Side effect worth naming: an interrupted quickstart becomes
resumable for free — taps imported before the interrupt skip on the next run, which is the
durability half of the user's ask. No flags change, so <code>docs/commands.html</code> needs no
regeneration; no other docs affected. Filed from the user's request during the 2026-08 CLI audit;
verified by reading <code>core/shards.py</code> — the missing check is unambiguous in code, no
repro run needed. Absolute date of verification: 2026-08-31.
