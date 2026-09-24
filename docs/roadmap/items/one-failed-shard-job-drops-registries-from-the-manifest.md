---
id: one-failed-shard-job-drops-registries-from-the-manifest
board: code
section: planned
status: shipped
category: Shards · Bug
complexity: M
impact: High
wow: 4
note: A single failed build job deletes ~10 unrelated registries from the published manifest, and their assets stay on the release, orphaned…
order: 337
owner: loop/shard-carry-forward-gaps
pr: 958
title: One failed shard-build job silently drops its whole chunk from the published manifest
---
<b>Found by the audit of the repo's own automation, and confirmed live on the current release.</b>
<code>shards.yml</code>'s build matrix is <code>fail-fast: false</code> and bin-packs the catalogue
into ~60 jobs of roughly ten registries each. Every job writes an <code>unchanged-N.txt</code> and
uploads it beside its fresh shards; the publish job runs under <code>if: !cancelled()</code> and
rebuilds <code>manifest.json</code> <b>from scratch</b> out of whatever artifacts arrived. A job that
failed uploads neither, so <code>publish_shards.py manifest --carry-forward</code> never hears about
its registries — and carry-forward is driven only by the <code>unchanged-*.txt</code> files that
exist, so last week's perfectly good rows for those registries are dropped rather than carried.
<br><br>
The assets stay on the release (<code>gh release upload --clobber</code> replaces and never deletes),
so the result is a set of orphaned shard files no manifest names, and every user of those registries
sent back to embedding them locally — ~1.2 s per chunk against a 0.12 s import.
<br><br>
<b>Fix.</b> <code>shards.unreported</code> makes silence its own answer: a registry named by no fresh
shard and no <code>unchanged</code> line keeps its published row, and only one that has left the
bundled catalogue is dropped. The publish job prints both counts, so a manifest that shrinks says so
in the log. Measured on the release of 2026-09-20 before the fix: 453 manifest rows against 461
<code>.shard.json</code> assets — <b>8 registries, 245.5 MB orphaned</b>, among them the 199 MB
<code>sickn33/antigravity-awesome-skills</code> whose rebuild is the run's 2 h 07 m critical path.
All eight were still in the catalogue, so all eight would have been carried.
