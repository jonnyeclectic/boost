---
id: published-shards-have-no-consumer
board: code
section: pipeline
status: shipped
category: Retrieval · Onboarding
complexity: L
impact: High
wow: 5
note: the vectors were being built and then nobody could get them
order: 1
owner: loop/shard-quickstart
pr:
title: Prebuilt vectors are published where no new user can reach them
---
Step 2 of <a href="#keyless-semantic-search-for-everyone">keyless semantic search</a> shipped the
producer and stopped there. <code>shards.yml</code> embeds each pinned registry weekly and
<code>dense.export_shard</code> / <code>import_shard</code> move the rows, but the two halves were
never joined: the output goes to <code>actions/upload-artifact</code>, and a workflow artifact
<b>needs a GitHub token to download and expires at 90 days</b>. A new user cannot
<code>curl</code> one. There was also no command that would look for a shard &mdash;
<code>--import-shard</code> takes a local file the user is expected to have found by hand. So the
measured 4,431&nbsp;s&nbsp;&rarr;&nbsp;0.12&nbsp;s saving existed and reached nobody.

<b>What shipped.</b> A <code>manifest.json</code> (schema v1) carrying the embedding space once at
the top and one row per shard &mdash; registry commit, chunk count, size, sha256, URL &mdash;
published with the shards to a rolling <code>shards-latest</code> prerelease on boost's own repo.
Anonymous, no expiry, stable URL. <code>core/shards.py</code> fetches and validates it,
<code>boost quickstart</code> is the one command a new machine needs, and
<code>boost reindex --fetch-shards</code> is the same import for a machine that is already tapped.

<b>Three refusals, because each failure is otherwise silent.</b> <em>Space</em> is checked against
the manifest before a byte is downloaded &mdash; mixing a 384-d keyless shard into a 1024-d Voyage
store does not raise, it returns wrong rankings, and refusing after a 129&nbsp;MB download is its
own bug. <em>Commit</em> is checked twice, in <code>sync</code> to skip the download and again in
<code>import_shard</code>, because a shard for a tree the registry has moved past would let
<code>dense.build</code> mark that tap "reused" and pin the user to stale vectors indefinitely.
That is what <code>boost tap --at &lt;sha&gt;</code> exists for: quickstart pins each registry to
the commit its vectors describe, rather than tapping HEAD and hoping. <em>Digest</em> is checked
over the bytes actually written and the file is deleted on mismatch, and a shard URL that is not on
the manifest's own host is refused &mdash; a manifest names what boost downloads, so it must not be
able to widen where the download goes.

<b>The prerelease flag is load-bearing.</b> <code>shards-latest</code> is marked prerelease and
not-latest so it is invisible to everything that reads "the latest release": release-drafter
resolves the next version from published non-prereleases, the README's shields badge excludes
prereleases, and the tag carries no digit so setuptools-scm's <code>--match *[0-9]*</code> never
sees it as a version. A shard release that shifted boost's own version resolution would be a very
expensive way to host a JSON file.

<code>scripts/publish_shards.py</code> is the other end: <code>export</code> dumps a machine's
vectors, <code>manifest</code> digests a directory into the manifest, and it refuses to describe two
embedding spaces in one file &mdash; the mistake that would otherwise publish a keyless index whose
header claims rows only a Voyage key can read.
