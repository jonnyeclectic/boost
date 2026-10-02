---
id: cancelled-ci-on-main-is-silent-and-skips-the-release
board: code
section: trust
status: planned
category: CI · Bug
complexity: S
impact: High
wow: 4
note: the alerting that exists to make a red main impossible to miss asks only about 'failure', and the run that skipped a release was 'cancelled'
order: 365
owner:
pr:
title: "A <code>cancelled</code> <code>ci</code> on main skips the release and alerts nobody, because the alert asks only about <code>failure</code>"
---
<b>Two independent gates, both keyed on the wrong half of the same enum.</b>
<code>publish.yml</code> fires on <code>workflow_run</code> and ships only when
<code>conclusion == 'success'</code>; <code>ci-failure-alert</code> opens the tracking issue
only when <code>conclusion == 'failure'</code>. A <code>ci</code> run that concludes
<code>cancelled</code> satisfies neither. <b>It does not ship and it does not tell anyone</b>
&mdash; the one conclusion that falls through both.

<b>Observed, on the merge of #1015.</b> <code>mutation-shard (4)</code> hit
<code>timeout-minutes: 75</code> and was cancelled, the aggregate <code>mutation</code> job
failed, and the run concluded <code>cancelled</code> rather than <code>failure</code>. No
release, no issue, no notification. It surfaced the same day, and only because somebody was
reading per-shard job durations out of the Actions API for an unrelated reason &mdash; nothing
in the repo would have raised it, and the next one will be found the same way or not at all.

<b>This is the exact blind spot <code>ci-failure-alert</code>'s own header describes.</b> That
file opens by explaining that <code>demo</code> "failed six runs out of six on main, alerted
nobody, and was found by a manual audit instead", and concludes that "any workflow that runs on
main and nobody watches belongs here". The list was then enforced by
<code>tests/unit/test_failure_alerting_covers_unattended.py</code> so a new workflow cannot
quietly join the blind spot. <b>The enforcement is over <em>which workflows</em> are watched,
and the hole here is <em>which conclusions</em> are</b> &mdash; <code>ci</code> is on the list
and still said nothing.

<b>Why a timeout is not an exotic case.</b> It is the designed behaviour of every
<code>timeout-minutes</code> in the repo, and <code>mutation-shard</code>'s is reached by an
ordinary slow runner rather than by a bug: across 169 measured shard jobs the worst was 72.5
minutes against a 75-minute cap. A job can also be cancelled by the concurrency group, by a
runner eviction (<code>mutation-shard (4)</code> on #1012 died at 15.1 min with exit 143), or by
a human pressing the button &mdash; and only the last of those is one anybody already knows
about.

<b>Shape of the work.</b> Widen the alert's condition from <code>== 'failure'</code> to the set
of conclusions that mean "main is not green", which is every one except <code>success</code>,
<code>skipped</code> and <code>neutral</code> &mdash; naming what is <em>excluded</em> rather
than what is included, so the next conclusion GitHub adds defaults to loud. The issue body
should say which conclusion it was, because <em>cancelled</em> and <em>failure</em> want
different first moves. Then pin it: the sibling test already enforces the workflow list, so the
conclusion set wants the same treatment rather than a comment. Worth checking at the same time
whether <code>publish.yml</code> should distinguish "CI did not pass" from "CI did not finish"
&mdash; today both are a silent no-op, and a release that was skipped because a runner was slow
is recoverable by a rerun that nobody currently knows to start.
