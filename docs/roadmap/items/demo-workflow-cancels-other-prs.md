---
id: demo-workflow-cancels-other-prs
board: code
section: pipeline
status: shipped
category: Build · Bug
complexity: S
impact: High
wow: 4
note: two PRs deadlocked each other for hours — re-running the job just moved the cancellation to the other one
order: 107
owner: fix/demo-concurrency
pr:
title: One global concurrency group let any PR cancel any other PR's check
---
<code>demo.yml</code> declared a <b>constant</b> concurrency group:

<code>concurrency:</code> <code>group: demo</code> · <code>cancel-in-progress: true</code>

A constant name puts every run of the workflow — every pull request, and <code>main</code> — into a
single queue, and <code>cancel-in-progress</code> then means each new run <b>kills whichever other
PR's run was in flight</b>. Not a flake, not a timeout: the configuration working exactly as
written.

<b>Observed 2026-08-10.</b> <code>#498</code> and <code>#504</code> both touch
<code>boost_cli/cli.py</code>, which is in this workflow's path filter, so both triggered it. Both
showed <code>record CANCELLED</code>. Neither could merge — and re-running the job on one just moved
the cancellation to the other. Two PRs held each other hostage with no shared cause visible from
either one.

<b>The diagnosis is unusually hostile, which is the part worth recording.</b> A cancelled check
reports <i>no conclusion</i>, so at the merge button it is indistinguishable from a failing one —
the branch protection message is the same. Nothing on your pull request names the run that killed
yours; the evidence lives on someone else's PR. And the natural first move, re-running the failed
job, <i>reproduces the problem in the other direction</i>, which reads like flakiness and is the
opposite of flakiness. The failing step name (<code>record</code>) points at the GIF recorder, a
component with nothing wrong with it.

<b>Fixed with the shape <code>ci.yml</code> already uses</b> — group per pull request, cancel only
for <code>pull_request</code> events, and key non-PR runs on <code>github.sha</code> rather than
<code>github.ref</code>. That last part is not decoration:
<code>cancel-in-progress: false</code> does not mean "never cancel", it means a newer run <i>waits</i>
and GitHub drops the older <i>pending</i> one when a third arrives, so grouping main on the ref can
leave a middle commit whose run never happens.

<b>A second instance surfaced from writing the guard rather than from an outage.</b>
<code>sonarcloud.yml</code> used <code>github.ref</code>, so it never cancelled across pull requests
the way <code>demo.yml</code> did — but it triggers on <code>push</code>, which puts every commit on
<code>main</code> in one group, and cancels unconditionally. Two merges in quick succession and the
first commit's analysis is killed, leaving <b>silent holes in main's quality history exactly where
merges came fastest</b>. Nobody would have reported that; it produces no red check anywhere.

<b>The guard is scoped, deliberately, rather than maximal.</b> Its first assertion — a PR-triggered
workflow's group must vary per run — is the deadlock. Its second only applies to workflows that
<i>actually run on <code>push</code></i>, because a schedule- or PR-only workflow has no main run to
strand and flagging it would be noise. The first draft was broader and flagged
<code>eval-explain</code>, <code>eval-stats</code> and <code>fuzz</code>, all of which key on
<code>github.ref</code> and are fine; they were checked before the assertion was narrowed rather
than "fixed" to satisfy it. Four tests also assert the parser still sees the workflows and still
calls the old <code>group: demo</code> constant — because every remaining assertion passes
vacuously if the trigger detection silently stops matching.
