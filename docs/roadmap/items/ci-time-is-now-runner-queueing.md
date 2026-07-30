---
id: ci-time-is-now-runner-queueing
board: code
section: pipeline
status: shipped
category: CI speed
complexity: M
impact: High
wow: 4
note: 104 job-min queued vs 236 executing — 31% of CI is waiting for a runner
order: 62
owner: loop/ci-concurrency
pr: 350
title: A third of CI job time is spent waiting for a runner, not running
---
With the mutation gate no longer dominating, the largest remaining term in CI wall clock is
<b>queueing</b>. Measured over six consecutive successful <code>ci</code> runs: <b>104
job-minutes queued</b> against <b>236 job-minutes executing</b> &mdash; <b>31%</b> of all job
time spent waiting for a runner.

<b>The obvious metric lies.</b> A run's <code>run_started_at</code> minus
<code>created_at</code> is <b>0.0 for every run</b>, which reads as "no queueing anywhere".
Queueing happens per <em>job</em>, not per run, so it is only visible as
<code>job.started_at - job.created_at</code>. Anything measuring this at run level will
conclude, wrongly, that there is nothing to fix.

The per-run spread shows what drives it &mdash; median job queue by run:
<code>c36c53a7</code> 0.1&nbsp;min, <code>c15ed9da</code> 0.1, <code>903b704f</code> 0.2,
<code>638bffeb</code> 0.7, <code>ad71ba99</code> <b>2.5</b>, <code>9e190537</code> <b>2.9</b>.
That is a 29&times; swing driven not by the change under test but by how many sibling
<code>loop/*</code> branches and Dependabot PRs happen to be live at the same moment. It is why
one merge took <b>41 minutes</b> wall clock with a max shard of only 11.4.

Sharding the mutation gate made this worse on purpose: it traded one runner slot for six. That
is the right trade for latency in isolation, and the wrong one to keep making blindly while a
dozen branches are in flight, because every concurrent PR now multiplies its footprint. Options,
roughly in increasing order of intrusiveness: a <code>concurrency</code> group that cancels
superseded PR runs; capping the shard matrix with <code>max-parallel</code>; or making the shard
count adaptive. Worth measuring before choosing &mdash; this item is the measurement, not the
fix.

<b>Shipped: the least intrusive one, and it turned out to be a plain omission rather than a
trade-off.</b> Seven workflows here already declare a <code>concurrency</code> group.
<code>ci.yml</code> &mdash; the largest by a wide margin, ~36 checks including six mutation
shards &mdash; declared none, so every push to a pull request left the whole previous run
executing against a commit nobody was waiting on. This session alone pushed four times to one PR,
which is 24 shard jobs of which 18 were already superseded.

The condition is the load-bearing part, and it is what the tests pin rather than the group name.
<code>cancel-in-progress: true</code> would also cancel a <b>push to main</b>, which
<code>publish.yml</code> gates the release on via <code>workflow_run</code> &mdash; a merge that
silently never ships &mdash; and a <b>merge_group</b> run, where a cancelled run never reports its
required contexts and the queue then waits forever on a status that is not coming. Both evaluate
false. A separate assertion sweeps every workflow that triggers on <code>merge_group</code> and
fails if any of them cancels unconditionally, so the deadlock cannot arrive later through a
different file.

What this does <em>not</em> do is reduce the footprint of a single run, which is the other half of
the measurement. <code>max-parallel</code> on the shard matrix and an adaptive shard count are
still open, and both trade latency for footprint rather than removing waste &mdash; worth
re-measuring queue time after this lands before spending that trade.
