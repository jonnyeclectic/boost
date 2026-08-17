---
id: the-shard-job-that-could-not-finish
board: code
section: internals
status: shipped
category: CI · Performance
complexity: S
impact: High
wow: 5
note: 5h30m cancelled at the ceiling, then 2h07m green — the same job, with duplicate embeddings collapsed
order: 120
owner: docs/shards-measured-scale
pr:
title: the shard job that had never once finished, and the timeout that could not be raised
---
<b><code>shards</code> exists so a keyless user gets semantic search without paying to embed the
catalogue themselves</b> &mdash; embedding is ~1.2 s/chunk on CPU, importing the same rows is 0.12 s,
so without published shards the keyless tier is available in principle and unreachable in practice.
It had <b>never once produced an artifact</b>.

<b>Two mechanisms, in order.</b> The first was a matrix built by splitting
<code>taps.txt</code> on whitespace &mdash; rows are <code>repo &lt;sha&gt; &lt;count&gt;</code>, so
20 registries became 60 jobs, and the run log is full of <code>build (18)</code> and
<code>build (b29e7cf6…)</code>. That was fixed. The <em>next</em> scheduled run then had one job
left that could not finish: <code>sickn33/antigravity-awesome-skills</code> burned its entire
<code>timeout-minutes: 330</code> and was cancelled, having published nothing.

<b>Raising the timeout was never on the table.</b> GitHub's job ceiling is 6 hours and 330 minutes is
already under it. So the workflow's own scale note &mdash; &ldquo;the largest pinned tap is ~75
min&rdquo; &mdash; was not a stale estimate to nudge upward; it was wrong about the shape of the
problem.

<b>The measurement that changed the answer.</b> That registry is 6,309 entries and 77,423 chunks
&mdash; of which only <b>24,246 are distinct</b>. <b>68.7% are byte-identical repeats</b>, because the
registry vendors its own items many times over. Embeddings are deterministic, so every copy was
bought at full price for the same vector, and <code>retrieve_any</code> discards the copies anyway.

<b>Same job, 5 h 30 m cancelled &rarr; 2 h 07 m green.</b> With the duplicate embedding work collapsed
(the catalogue content-identity change), the job completed and uploaded a <b>129 MB shard carrying
78,095 chunks</b>. Nothing about the output shrank &mdash; one row per entry-chunk is what keeps tap
deletion correct; only the number of times the provider was asked did.

<b>The lesson is where the budget lives.</b> A per-registry cost estimate keyed on entry count is
measuring the wrong thing: a registry that mirrors itself heavily is far cheaper than its size
suggests, and one that does not is the case to watch against the ceiling. The workflow now says so,
with the numbers.
