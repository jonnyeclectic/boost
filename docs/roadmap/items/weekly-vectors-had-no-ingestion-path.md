---
id: weekly-vectors-had-no-ingestion-path
board: code
section: pipeline
status: shipped
category: Retrieval · Onboarding
complexity: M
impact: High
wow: 4
note: the vectors were republished weekly and no command could take delivery
order: 129
owner: loop/shard-ingest
pr:
title: The weekly republish reached the machines that had never been set up
---
<a href="#published-shards-have-no-consumer">Prebuilt vectors</a> gave a new machine a
one-command path to semantic search, and <a href="#shard-runs-reembed-everything-weekly">the
incremental run</a> made republishing them weekly affordable. Between the two sat a gap nobody had
a command for: <b>an existing install could not take delivery of next week's vectors.</b>

<b>Which side is authoritative.</b> <code>shards.sync</code> takes the machine's tap commits as
given and asks whether a published shard happens to match. That is the right question on setup day
and the wrong one seven days later, because the weekly run republishes against whatever the
registries moved to &mdash; so for most taps the answer becomes "no", and <code>reindex
--fetch-shards</code> reported <code>refused (commit moved)</code> row after row. The three
existing ways to move a tap all pointed somewhere else: <code>boost update</code> chases the
branch head, <code>--force</code> chases it while dropping the pin, and <code>boost tap --at</code>
refuses a registry that is already tapped. None of them can land on a commit a manifest names, and
the odds that the branch head <em>happens</em> to be that commit fall with every push upstream. The
honest remedy left standing was hours of local CPU.

<b>What shipped.</b> <code>shards.ingest</code> reads the manifest as the <em>target</em> state: a
row for a tap held at another commit is a reason to move the tap.
<code>registry.retarget</code> is the missing primitive &mdash; checkout, then pin, never the
reverse, because a pin recorded for a tree that was not checked out is a lie <code>update</code>
would honour by skipping that tap forever. <code>boost update --shards</code> is the surface, and
it is a separate mode rather than a step of the normal update because the two move taps toward
different commits; asking for both is refused rather than silently resolved.

<b>Order is the load-bearing part.</b> The bytes are downloaded and their digest verified
<em>before</em> the tap moves. Moving first and failing the download leaves vectors that are stale
but still present &mdash; the failure that looks like nothing at all, and the one this whole
subsystem exists to refuse. The <code>retarget</code> callable is injected so that ordering is
asserted in the unit suite without a git remote.

<b>Idempotence is the automation story.</b> The skip test reads
<code>dense.tap_commits()</code> &mdash; which commit the <em>vectors</em> were built at, not just
which commit the clone sits on &mdash; so a tap matching on both is skipped without downloading
anything. In a week where a registry did not move, the command costs one 170&nbsp;KB manifest
fetch, which is what makes it safe to put in a cron line. A registry that dropped out of the
manifest is left pinned exactly where it sits: falling back to the branch head would invent a
target no published vectors describe. Anything that did move has its catalog cache and the BM25
index rebuilt, because a commit is load-bearing for more than vectors.

<b>Search still makes no network call, and cheapness was never the argument.</b> The manifest is
small enough to check inline; acting on the answer is not, since it means moving taps and
downloading hundreds of megabytes inside a command that answers in under a second. So the most an
inline check could ever produce is the one muted line <code>boost search</code> now prints for the
price of one <code>stat</code> &mdash; against a round trip per query and unannounced egress. The
marker lives under <code>state/</code> rather than <code>cache/</code>, because <code>boost
clean</code> sweeps <code>cache/*.json</code> and would otherwise delete it, leaving search to nag
about vectors that were refreshed that morning.
