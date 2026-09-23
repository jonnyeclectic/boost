---
id: one-failed-shard-job-drops-registries-from-the-manifest
board: code
section: planned
status: planned
category: Shards · Bug
complexity: M
impact: High
wow: 4
note: A single failed build job deletes ~10 unrelated registries from the published manifest, and their assets stay on the release, orphaned…
order: 337
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
<b>Fix.</b> Carry forward from the previous manifest for any registry the run did not report on at
all, rather than only for the ones an <code>unchanged</code> file names; and make the publish job
say plainly how many rows it carried for jobs that did not report.
