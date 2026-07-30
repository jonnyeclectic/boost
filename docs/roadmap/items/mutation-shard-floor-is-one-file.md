---
id: mutation-shard-floor-is-one-file
board: code
section: pipeline
status: shipped
category: CI speed
complexity: M
impact: Med
wow: 3
note: shard 0 is store.py alone — 9.3-11.7 min against a 6.1 even split
order: 61
owner: loop/mutation-subfile-shards
pr: 346
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

<b>Shipped.</b> A file heavier than an even share is now split into one unit per top-level
function, and those units pack independently. <code>store.py</code>'s 31 functions come out as a
<b>complete partition</b> &mdash; each assigned exactly once, each matched by exactly one pattern
&mdash; and spread across all six shards, so no shard is more than <b>27%</b> store.py where one
was previously <b>100%</b>. By mutant count the critical path drops from <b>1931 to 1786</b>, i.e.
from 1.08&times; of ideal to <b>1.00&times;</b>, and the packing lands within 0.4% of a perfect
split (1777&ndash;1786 against an ideal 1779).

Both invariants are asserted rather than argued. Patterns anchor on the
<code>__mutmut_</code> suffix, which is what stops <code>install</code> swallowing
<code>install_from_path</code> &mdash; a real pair in this file. And the merge now <b>unions</b>
each shard's results: every shard writes a <code>.meta</code> listing every key in the file with
<code>None</code> against what it did not run, so a mutant is only "unrun" when it is
<code>None</code> everywhere. A function no shard was assigned therefore reddens the gate. That
was verified adversarially &mdash; a synthetic mutant name outside the enumerated partition matches
no shard's pattern, stays <code>None</code>, and is reported. Any file whose partition cannot be
enumerated exactly (a class with methods, a duplicate name, a syntax error) is left whole rather
than guessed at.

<b>The count-based number understates the win.</b> The planner was already balancing count to
1.08&times; of ideal &mdash; the 1.5&ndash;1.9&times; wall-clock gap was never count imbalance, it
was that <code>store.py</code>'s mutants are the slow ones. Spreading them is the actual fix. And
because a file can now be divided, weighting by <i>seconds</i> finally changes the answer where
before it could not, so <code>weights</code> also records per-file durations and the planner
prefers them when every file has one &mdash; all-or-nothing, since milliseconds run to five digits
where counts run to three. That tier stays dormant until a measured run populates it; CI now
uploads a refreshed hints file as an artifact so it can be.
