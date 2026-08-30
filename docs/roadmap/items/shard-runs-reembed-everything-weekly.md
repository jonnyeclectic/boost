---
id: shard-runs-reembed-everything-weekly
board: code
section: pipeline
status: shipped
category: Retrieval · CI
complexity: M
impact: High
wow: 4
note: the manifest already knew which registries had not moved
order: 2
owner: loop/shards-incremental
pr:
title: Every weekly shard run re-embedded the whole catalogue
---
The catalogue shard run is <b>60 packed jobs over 463 registries, ~9 job-hours a week</b> at the
measured 0.22&nbsp;s/chunk &mdash; and every one of those hours was spent on ephemeral runners with
no memory of the week before. Registries move slowly. Most weeks most of the catalogue is at the
same commit it was published at, and the run bought the same vectors again, byte for byte.

<b>The manifest already held the answer.</b> Each row pins the registry commit its shard was
built from, because <code>dense.import_shard</code> refuses a shard for any other commit. That
same pin answers "has this registry moved since we published?" in one comparison, and
<code>shards.unchanged(manifest, commits)</code> makes it: a tap is unchanged only for the
<em>exact</em> commit its row describes, an empty local commit (a clone that failed) never
counts, and a manifest in another embedding space reuses nothing however fresh its commits
&mdash; none of its rows would be importable by the consumer this run publishes for.

<b>Carry forward, not re-export.</b> The build job taps its chunk, asks
<code>publish_shards.py unchanged</code>, untaps every registry it lists, and embeds only what
is left &mdash; a chunk with nothing left skips the pass rather than failing on "no taps
configured". The publish job fetches last week's manifest from the release and carries those
rows forward verbatim: the assets are still there, since <code>gh release upload --clobber</code>
replaces but never deletes. The cheaper-looking alternative, import last week's shard and
re-export it, would re-upload ~300&nbsp;MB of identical vectors a week for nothing.

<b>What the row set means now.</b> Fresh beats carried for the same tap. A registry that is
neither fresh nor unchanged &mdash; removed from the catalogue, or failed to tap this week
&mdash; drops out of the manifest rather than accumulating forever; its asset stays on the
release, harmless, and its row returns the week the registry does. A row is carried only when
the job's commit and the manifest's agree: two sources disagreeing means someone is wrong, and
the honest outcome is a re-embed next run, not a row that may describe a tree the registry has
left.

<b>Cost after.</b> The first run is unchanged. Every run after it costs the registries that
moved plus one comparison each for the rest, so a quiet week is a manifest upload and little
else, and wall clock is bounded by the largest registry that actually changed rather than by
the largest registry.
