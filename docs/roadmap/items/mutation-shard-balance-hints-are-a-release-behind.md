---
id: mutation-shard-balance-hints-are-a-release-behind
board: code
section: trust
status: planned
category: CI · Mutation gate
complexity: S
impact: Med
wow: 2
note: the planner packs six shards for 23,251 mutants; there are 27,060
order: 358
title: "The mutation shard planner is packing for a mutant set that is 16% smaller than the real one"
---
<code>scripts/mutation_weights.json</code> is the measured input the shard planner bin-packs on, and
it was last refreshed on 2026-09-08 by #834, from a CI-measured run. It records <b>23,251 mutants
over 66 files</b>. A full local run of the gate on 2026-09-29 counted <b>27,060</b> &mdash; the
planner is balancing six shards against a picture of the work that is 16% light.

<b>The drift is uneven, which is the part that costs balance rather than merely being out of date.</b>
Per file: <code>store.py</code> 2,916 &rarr; 3,962 (+36%), <code>paths.py</code> 110 &rarr; 187
(+70%), <code>dense.py</code> 1,845 &rarr; 1,999 (+8%), <code>gitutil.py</code> 622 &rarr; 710
(+14%), while <code>policy.py</code> went 286 &rarr; 278 (&minus;3%). <code>store.py</code> is the
one file the planner splits per top-level function, so its share is what most decides the pack, and
it is the file that grew most.

<b>What made this visible.</b> On 2026-09-29 <code>mutation-shard (0)</code> on PR #1000 ran 75.6
minutes against the job's <code>timeout-minutes: 75</code>, was killed, and failed the required
<code>mutation</code> check. That one was <em>not</em> a packing defect: the shard plan is
byte-identical on <code>main</code>, #1000 and #1001 (verified by generating all six patterns on
each tree and diffing), and the same shard ran 34 minutes on both of the others, so the immediate
cause was the runner variance the job's own comment already documents &mdash; 2.6x on identical
work. Stale weights are what leaves no headroom to absorb it. The ceiling is ~3.1x the planned
24.1-minute per-shard time, and a pack built from a 16%-light picture spends part of that margin
before a slow runner arrives.

<b>Two smaller corrections fall out of the same reading.</b> The comment above
<code>timeout-minutes: 75</code> in <code>ci.yml</code> dates the weights file to 2026-07-30; git
says 2026-09-08. And <code>mutation_shards.py weights</code> rewrites
<code>scripts/mutation_weights.json</code> <em>in place</em> and prints only a summary to stdout, so
the natural-looking <code>weights --source mutants &gt; new.json</code> silently overwrites the
committed file and puts the summary line in <code>new.json</code>.

The fix is the remedy <code>ci.yml</code> already names for this situation: re-measure from a CI
run and re-pack. It must be a CI run, not a laptop one &mdash; that is the convention #834 set,
and it is load-bearing, because the tier-1 weights are milliseconds and a developer machine's
durations are not the runner's. (A local run also cannot be trusted to be complete: a resumed run
leaves whole files with no recorded duration, which the planner then imputes at the mean rate.)
