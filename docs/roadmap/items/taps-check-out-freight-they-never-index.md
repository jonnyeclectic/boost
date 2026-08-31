---
id: taps-check-out-freight-they-never-index
board: code
section: internals
status: shipped
category: Storage · Footprint
complexity: M
impact: High
wow: 4
note: 458 taps held 12 GB to index 1.9 GB of Markdown
order: 112
owner: loop/sparse-tap-clones
pr: 520
title: Taps download and check out the 84% of a repo that boost never opens
---
<b>Measured on a real install, not estimated.</b> <code>~/.boost</code> had grown to
<b>16 GB</b>: <code>repos/</code> 12 GB across 458 taps, <code>cache/</code> 3.9 GB.
The cache is earned — 3.2 GB of it is the dense vector store
(<code>750,416</code> chunks &times; 1024-d float32 = 3.07 GiB exactly) backing a
live semantic search, and 653 MB is the BM25 postings. The clones are not.

Of those 12 GB, <b>1.9 GB is Markdown</b> — every <code>*.md</code>,
<code>*.mdc</code> and rule file on disk, which is the complete set of things
<code>catalog.scan_dir</code> ever opens. The other ~10 GB is freight: 3.5 GB of
<code>.git</code>, 440 MB of <code>node_modules</code>, and the rest binary
assets, <code>.bin</code> meshes, gifs and 10 MB bundled <code>validate.js</code>
files. <code>Shopify/agent-skills</code> alone was <b>611 MB for the 30
SKILL.md files boost wanted</b>.

<b>The precedent was already in the file.</b> <code>gitutil.run</code> sets
<code>GIT_LFS_SKIP_SMUDGE=1</code> with the comment "taps are indexed for their
Markdown, and boost never reads an LFS payload" — the same argument, applied to
one storage mechanism and not the general case.

<b>Taps now clone <code>--filter=blob:none --sparse</code></b> with a
sparse-checkout cone derived from <code>catalog</code>'s own
<code>RULE_SUFFIXES</code> / <code>RULE_FILENAMES</code>. Verified rather than
assumed: <code>Shopify/agent-skills</code> checks out at <b>11 MB</b> and
<code>catalog.scan_dir</code> produces a <b>byte-identical set of entries</b>
against the 611 MB clone — same 30 items, zero missing, zero extra.

<b>The correctness risk is install, and it is the reason this is M and not S.</b>
A skill legitimately owns its <code>scripts/</code> and <code>assets/</code>, and
<code>store._copy_skill</code> is a <code>shutil.copytree</code>. Handed a
partially checked-out directory it copies what is there and <em>reports
success</em> — a skill installed without its scripts, no error, a normal-looking
lock entry, and a failure that surfaces only when the agent runs the thing. So
<code>store.source_dir_for</code>, the single chokepoint every consumer of a
tap's real files goes through, materializes first:
<code>git sparse-checkout add</code> widens the cone and git fetches the blobs
from the promisor remote on demand. <code>add</code>, never <code>set</code> —
<code>set</code> replaces the pattern list and would un-fetch every previously
materialized skill.

<b>Degradation needed less code than expected.</b> A server that cannot filter
makes git warn and send everything by itself, and local clones ignore both
<code>--depth</code> and <code>--filter</code> the same way, so neither is an
error path. Only git older than 2.25 genuinely rejects <code>--sparse</code>, and
that retries as a plain shallow clone.

<b>Existing clones need a migration, or nothing shrinks for anyone who already
has a machine full of taps.</b> <code>boost compact</code> applies the cone to
clones already on disk — offline, no re-clone, and reversible. Measured on
<code>github/awesome-copilot</code>: <b>177 MB &rarr; 93 MB</b>, all 1,736
Markdown files intact, zero non-Markdown files left. The floor is
<code>.git</code> itself (76 MB of that 93 MB), because a clone that already
downloaded every blob cannot be made blobless in place; <code>--reclone</code>
trades network time for that last chunk.

One detail is load-bearing and has its own test: <b>git silently declines to
remove a path it considers not up to date</b>, so on a clone whose mtimes have
moved — a restored backup, a copied <code>BOOST_HOME</code> — the first attempt
kept every file and reported success. <code>compact</code> runs
<code>update-index --refresh</code> first. This was found by doing it, not by
reading about it.

<b>Also fixed here, because it was found while measuring.</b>
<code>boost clean</code> globs <code>cache/*.json</code> and calls anything whose
stem is not a configured tap a "stale tap cache". <code>rag_index.json</code> —
the BM25 index, 44 MB — and <code>discovery.json</code> match that shape, and no
tap can ever be named after them, so <b><code>clean</code> deleted the search
index on every run</b>. Not a cheap self-repair: the next search re-parses every
tap catalog on the machine, ~71k items on a full install. Guarded now by
<code>paths.INTERNAL_CACHE_FILES</code>, with a drift test that fails the build
when a module writes a cache artifact without registering it.

<b>Measured over all 459 taps on the machine that prompted this</b>, with the
same accounting <code>compact</code> uses:

<code>repos/</code> today is <b>11.18 GB</b> &mdash; <b>5.80 GB</b> of freight that
<code>compact</code> frees, <b>3.48 GB</b> of <code>.git</code> that only
<code>--reclone</code> reaches, and <b>1.90 GB</b> genuinely kept (Markdown plus
provenance). So <code>repos/</code> lands at <b>5.38 GB</b> after
<code>compact</code> and <b>~2.6 GB</b> after <code>--reclone</code>.

With <code>cache/</code> unchanged at 3.9 GB that is <b>16 GB &rarr; ~9.3 GB</b>,
or <b>~6.5 GB</b> after <code>--reclone</code> — and the 1.90 GB kept figure
independently matches a plain <code>find</code> over every Markdown file on the
machine, which is the check that says the accounting is right.

<b>Zero retrieval cost, and that is measured rather than argued.</b> The 20
pinned repos of the eval corpus, re-tapped from scratch at their pinned commits
with sparse clones, produce <b>10,152 entries across 20 taps</b> — the same
number the fat corpus produces — and the gate scores
<code>0.852 / 0.473 / 0.605 / 0.657</code> against it, identical to three
decimals, per-kind breakdown included. The corpus itself goes 642 MB &rarr;
256 MB.

The remaining lever is the 3.2 GB vector store — int8 quantization would take it
to ~800 MB — but that is a retrieval-quality change that has to clear the eval
gate's four floors, so it belongs in its own card rather than riding along with a
storage cleanup.
