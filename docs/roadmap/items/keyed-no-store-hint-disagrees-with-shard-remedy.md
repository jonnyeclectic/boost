---
id: keyed-no-store-hint-disagrees-with-shard-remedy
board: code
section: planned
status: shipped
category: Consistency · Bug
complexity: S
impact: Low
wow: 2
note: On a keyed machine with no vector store, doctor and search say "build it" (paid), while quickstart and update --shards say to unset the key and download free…
order: 331
owner: loop/keyed-no-store-hint
pr:
title: With an API key exported and no vector store yet, <code>doctor</code> and <code>search</code> send the user to a paid build while <code>quickstart</code> offers the free download
---
<b>Found while verifying the quickstart shard-status fix.</b> After that fix, <code>shards.remedy()</code>
tells a keyed machine with no store to <code>unset VOYAGE_API_KEY</code> and run
<code>boost update --shards</code>, which downloads the published keyless vectors for free.
<code>boost doctor</code> and <code>boost search</code> read <code>dense.fix_hint("no-store")</code>
instead, which says <em>build it: <code>boost reindex --dense</code></em>. With a key in force,
that embeds the whole catalogue through the paid API.

That leaves two commands giving the same user contradictory advice, which is the thing
<code>fix_hint</code> exists to prevent. <b>Fix direction:</b> when the reason is
<code>no-store</code> and a key outranks the local model, have <code>fix_hint</code> answer with
<code>shards.remedy()</code> (or the same table row), so <code>doctor</code>, <code>search</code>,
<code>quickstart</code> and <code>update --shards</code> give one answer. Keep the manifest fetch off
the search path: <code>search</code> must not touch the network to word a hint.
