---
id: required-checks-can-declare-a-check-that-deadlocks-prs
board: code
section: pipeline
status: shipped
category: Release safety
complexity: S
impact: High
wow: 4
note: the gate green-lit a list that bricks every PR
order: 49
owner: loop/required-checks-paths
pr:
title: The required-check gate could not see <code>paths:</code>, so it green-lit a list that deadlocks every PR
---
<code>.github/required-checks.txt</code> declared 21 contexts and
<code>scripts/check_required_checks.py</code> reported
<i>"21 required, 22 PR check names, no ambiguity"</i> and exited 0. Four of those 21 —
<code>validate</code>, <code>markdown-lint</code>, <code>theme-lint</code> and
<code>vale</code> — are produced by <b>path-filtered</b> workflows.

When a pull request touches none of a workflow's <code>paths:</code>, GitHub does not
create a pending check run that later resolves; it creates <b>no check run at all</b>.
Branch protection then waits forever for a status that is never coming, and the pull
request can never merge. Applying that list would have bricked the repository — and
<code>--print-api</code> would have emitted the payload to do it.

The cause is one regex. The gate decided "runs on pull_request" with
<code>re.search(r"^\s{2}pull_request:", header)</code>, which is true for any workflow
that <em>mentions</em> the trigger, whether or not <code>paths:</code>,
<code>paths-ignore:</code> or <code>types: [labeled]</code> narrows it — precisely the
distinction that decides whether a required check deadlocks.

Demonstrated live rather than argued: the PR that fixed the
<code>adapter-conformance</code> install touches no <code>style/**</code> file, and its 30
check runs contain <code>validate</code>, <code>markdown-lint</code>, <code>vale</code>,
<code>check</code> and <code>sweep</code> — but no <code>theme-lint</code>. Requiring
<code>theme-lint</code> would have hung that PR permanently.

Fix: classify the trigger as none/always/filtered and refuse any required name that
resolves only to a filtered workflow, with an error that names the culprit file. The four
docs checks move to a commented block explaining why they are useful but not requireable.
The list is 17 contexts, all verified to report on every PR. Ten new tests cover the rule
and all ten fail against the previous script.
