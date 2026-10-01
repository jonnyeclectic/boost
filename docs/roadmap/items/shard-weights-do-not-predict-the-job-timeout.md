---
id: shard-weights-do-not-predict-the-job-timeout
board: code
section: trust
status: planned
category: CI · Bug
complexity: M
impact: High
wow: 4
note: the pack is balanced to within 700ms of ideal and a shard still timed out at 75 min, cancelling a release
order: 364
owner:
pr:
title: "Mutation shard weights balance perfectly and predict nothing, so a shard can time out and cancel a release"
---
<b>Observed, on the merge of #1015.</b> <code>mutation-shard (4)</code> ran 75 minutes against the
job's <code>timeout-minutes: 75</code> and was cancelled. The aggregate <code>mutation</code> job
then failed, the whole <code>ci</code> run concluded <code>cancelled</code> rather than
<code>failure</code>, and <code>publish.yml</code> &mdash; which gates on
<code>workflow_run.conclusion == 'success'</code> &mdash; skipped. <b>A merge to main silently did
not ship</b>, which is the exact failure mode the long comment above <code>ci.yml</code>'s
<code>concurrency:</code> block was written to prevent by a different route.

<b>The packer is not at fault, and that is the finding.</b>
<code>mutation_shards.py plan --shards 6 --explain</code> reports every shard within <b>700 ms</b>
of the ideal 6,884,259 ms &mdash; a balance of 0.01%. The same run measured 39, 27, 38, 36,
<b>76</b> and 65 minutes. Perfect balance against numbers that do not predict wall clock.

<b>The units are the tell.</b> Total weight is 41,305,555 ms over six shards, so the plan
predicts <b>114 minutes per shard</b> while shards finish in 27&ndash;76. The weights are
self-consistent ratios measured somewhere other than a CI runner, and ratios are all the
packer needs &mdash; but it means <b>nothing in the repo can answer "will a shard exceed the
cap?"</b>. <code>plan --explain</code> prints the speedup cap and the largest unit; it never
mentions <code>timeout-minutes</code>, and <code>grep</code> finds no comparison between the two
anywhere in <code>scripts/mutation_shards.py</code>.

<b>Run-to-run variance eats the margin.</b> The same tree, built twice: shard 4 took 66 min on
<code>5aaf8bc4</code> (the PR) and 76 min on <code>f196160d</code> (its merge commit); shard 5 went
42 &rarr; 65. On <code>8c4a5094</code> shard 4 was 32. So the heaviest shard's observed range is
32&ndash;76 minutes for identical work, and the cap is 75. Related and probably the same cause:
<code>mutation-shard (4)</code> on #1012 died at 15.1 minutes with exit 143 (SIGTERM), diagnosed
then as runner eviction.

<b>Why the open weights-refresh PR does not fix it.</b> #1014 re-measures and re-packs; under its
weights the plan is again balanced to within ~400 ms, and predicts 121 min/shard. Re-measuring a
quantity that was never in runner time produces a better-calibrated version of the same
unanswerable question.

<b>Shape of the work.</b> Three independent pieces, in increasing order of how much they fix:
calibrate the weights against observed job duration (the API has it per shard, per run) so the
plan is in minutes a human can compare to the cap; have <code>plan</code> fail, or at least warn,
when a packed shard's predicted time is within some margin of <code>timeout-minutes</code>; and
give the heaviest shard headroom &mdash; at eight shards the ideal drops by a quarter, and the
speedup cap is 6.0x only because <code>store.py</code> is split per function already, so more
shards is cheap. Separately, a cancelled <code>ci</code> on main should be loud: it currently
looks identical to a success from the release path's point of view, because
<code>publish.yml</code> only asks whether the conclusion was <code>success</code>.
