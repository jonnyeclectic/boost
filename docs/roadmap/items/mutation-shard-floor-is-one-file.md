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

<b>Splitting alone was not enough, and the first green run proved it.</b> With
<code>store.py</code> divided, <code>mutation-shard (0)</code> fell from 9.3&ndash;11.7 minutes to
<b>4.7</b> &mdash; it is no longer the slowest leg, which is exactly what the card predicted. But
shard 3 became the new bottleneck at <b>10.3</b> minutes, leaving the run at 1.6&times; ideal. The
diagnosis above was right and incomplete: counts were balanced to 0.4%, and the <em>time</em>
spread across shards was still 2.6&times;.

So the second half is weighting by measured time, which a divisible file finally makes possible.
<code>weights</code> now records mutmut's per-mutant durations and the planner prefers them. The
count-based split, balanced to <b>1.08&times;</b> of ideal <i>by count</i>, was <b>2.24&times;</b> of
ideal <i>by time</i> &mdash; one shard carrying 39.3 minutes of summed test time against a
17.5-minute even share.

<b>Measured, that bought less than the arithmetic suggested.</b> Time-weighting moved the critical
path from 10.3 to <b>9.3</b> minutes (shards 5.2, 5.8, 6.3, 6.8, 6.2, 9.3), 1.41&times; ideal rather
than the 1.04&times; the summed-time model predicted. Summed test time is not shard wall clock:
mutmut runs mutants across parallel workers, so a shard's elapsed time is its summed time divided by
an effective worker count, and the model ignored that. Per-shard fixed overhead was ruled out by
measurement rather than assumed &mdash; checkout, venv and install together are <b>0.4 minutes</b>,
against 4.8&ndash;8.9 minutes inside <code>mutmut run</code> itself.

The residual had a specific cause, and it is the same proxy error one level down: a split file's
time was apportioned across its functions by <em>mutant count</em>. Across
<code>store.py</code>'s functions the per-mutant cost spans <b>0.273 s to 3.900 s</b> &mdash;
<b>14.3&times;</b> &mdash; and <code>install</code> alone is <b>36%</b> of the file's time from
<b>12%</b> of its mutants, so the shard that drew it ran 8.9 minutes against a 4.8-minute sibling.
<code>weights</code> now records per-<em>function</em> durations too and apportions on those, which
balances the plan to <b>0.06%</b>.

<b>That closed most of the gap.</b> The next run came back at 4.9, 5.6, 6.3, 7.2, 7.3,
<b>7.7</b>&nbsp;minutes &mdash; a critical path of <b>7.7</b> against a 6.5-minute even share, or
<b>1.19&times;</b>, from 1.5&ndash;1.9&times; before. Measured end to end, the slowest leg went from
<b>9.3&ndash;11.7 minutes to 7.7</b>, and the shard that used to be <code>store.py</code> alone now
finishes first. Total work is unchanged at ~39 job-minutes, as it should be &mdash; this moved the
work around, it did not remove any.

The remaining 1.19&times; is not packing error. The plan is balanced to 0.06% on measured time, so
what is left is variance between runners and the fact that a mutant's cost is not perfectly stable
run to run. Chasing it further would mean re-measuring every run rather than better arithmetic.

Two bugs found by running it rather than reasoning about it. mutmut records durations in
<b>seconds</b>, so summing them into a field named <code>millis</code> understated
<code>store.py</code>'s 2360 seconds of test time as 2.4 &mdash; a 1000&times; mislabel. And
requiring a duration for <i>every</i> file before trusting the tier was too brittle to fire: one
file of 46 (<code>util.py</code>) came back short on the first run, which would have silently
dropped the planner back to counting mutants and looked like the feature simply not working. A
missing file is now imputed at the measured mean rate, which keeps every weight in one unit
&mdash; the property that actually matters.
