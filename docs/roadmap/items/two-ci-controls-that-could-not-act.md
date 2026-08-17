---
id: two-ci-controls-that-could-not-act
board: code
section: internals
status: shipped
category: CI · Correctness
complexity: S
impact: Medium
wow: 4
note: one publisher could never publish and one alert could never stand down — both reported success
order: 119
owner: fix/ci-controls-that-cannot-act
pr: 529
title: a publisher that could not publish, and an alert that could not stand down
---
<b>Two controls, the same failure mode: present, running, and structurally unable to do the thing
they exist for.</b>

<b>1. <code>eval-stats</code> pushed to a branch no token can push to.</b> An earlier fix got the
credentials right &mdash; the checkout uses <code>persist-credentials: false</code>, so the push
needed its own token URL, and it got one. That took the workflow as far as a <em>different</em>
permanent failure: <code>GH013: Repository rule violations found for refs/heads/main</code>.
<code>main</code> carries a ruleset with a <code>pull_request</code> rule and an <b>empty bypass
list</b>, so no token can push to it &mdash; not <code>github.token</code>, not a PAT, not any bot.
The workflow was not misconfigured; it was impossible.

<b>The remedy is not a bypass actor.</b> Adding one would open the protection guarding every change
to main so that a docs payload can skip review. The refreshed metrics now arrive the way
<code>eval-corpus-refresh.yml</code> already lands its moved pins &mdash; as a pull request on one
long-lived <code>bot/eval-metrics</code> branch that each run updates in place, rather than a new PR
a week. Reviewable, mergeable, and no weaker than any other change to main. It carries the same
warning that workflow's PRs do: a <code>GITHUB_TOKEN</code> push never triggers workflows, so the
check list is empty until someone presses <b>Update branch</b>, and empty looks exactly like
&ldquo;not started yet&rdquo;.

<b>2. The failure tracker opened issues and never closed one.</b> Its own closing line said
&ldquo;close this once CI is green again&rdquo; &mdash; a manual step nobody had a reason to take. So
<code>visual</code> stayed open through <b>four consecutive green runs</b>, and an issue list that
mixes live outages with fixed ones makes every entry in it read as equally suspect. An alert that
cannot stand down is only half an alert. A success on main now closes the tracker for
<em>that</em> workflow, keyed on the same per-workflow marker the opener writes &mdash; a
<code>ci</code> success must never close a <code>demo</code> tracker.

<b>The second job is what made the permissions wrong.</b> <code>issues: write</code> sat at the
workflow level, where it reaches every job including any added later; zizmor's excessive-permissions
audit says so and now fails the build on it. Each job asks for its own.

<b>Both halves are pinned statically</b>, and the push guard was verified by reversion: restore the
old <code>HEAD:main</code> and the test names the exact line. The guard outlives this fix &mdash; it
is parametrised over every workflow that pushes, so the next one cannot rediscover the same wall.
