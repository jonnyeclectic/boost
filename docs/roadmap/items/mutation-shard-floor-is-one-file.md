---
id: mutation-shard-floor-is-one-file
board: code
section: pipeline
status: inflight
category: CI speed
complexity: M
impact: Med
wow: 3
note: shard 0 is store.py alone — 9.3-11.7 min against a 6.1 even split
order: 61
owner: loop/mutation-subfile-shards
pr:
title: The mutation gate's floor is a single file &mdash; shard 0 <em>is</em> <code>store.py</code>
---
Sharding took the mutation gate from ~28 minutes to ~12 (see
<code>mutation-gate-was-the-whole-critical-path</code>), but it cannot go lower without
splitting one file. Measured across four consecutive six-shard runs:

<code>638bffeb</code> ran 1.9, 3.9, 5.7, 6.7, 7.2, <b>11.7</b>&nbsp;minutes;
<code>02c18bd6</code> ran 2.7, 5.0, 5.2, 5.5, 5.9, <b>11.7</b>; <code>fc427839</code> ran 3.1,
4.8, 5.3, 6.4, 7.3, <b>9.7</b>; and <code>f42e617b</code> ran 2.9, 4.9, 5.5, 6.6, 7.3,
<b>9.3</b>.
<b><code>mutation-shard (0)</code> was the slowest leg in all four.</b> Total work is
36&ndash;37 job-minutes, so a perfectly even split would be <b>6.1</b>; the actual critical
path is 9.3&ndash;11.7, or <b>1.5&ndash;1.9&times;</b> that. The gap is not bad packing &mdash;
the planner balances mutant <em>count</em> to within 1.10&times; of ideal. It is that count is
a poor proxy for time: measured throughput spans <b>3.39 to 14.19 mutants/second</b>, because a
<code>store.py</code> mutant re-runs a far larger covering test set than an
<code>ed25519.py</code> one, and survivors run their tests to completion where kills exit early.

Re-weighting the planner by seconds would even out the <em>billed</em> minutes but not the wall
clock, because <code>store.py</code> is <b>1931 mutants (18.4% of the repo)</b> in one file and
longest-processing-time packing cannot place a single file across two bins. The floor is that
file.

The way under it: mutant names are addressable per function, so
<code>boost_cli.core.store.install_*</code> can be its own shard. That would bring the critical
path toward the 6.1-minute even split. Two things must survive the change &mdash;
<code>pattern_for()</code> still has to emit patterns that match nothing else, and
<code>cmd_merge</code>'s completeness assertion has to keep failing closed, since mutmut counts
an unrun mutant inside <code>total</code> and a partial merge would silently depress the score
rather than error.
