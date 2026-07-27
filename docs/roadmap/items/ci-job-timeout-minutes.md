---
id: ci-job-timeout-minutes
board: code
section: pipeline
status: shipped
category: CI/CD
complexity: S
impact: Low
wow: 1
note:
order: 10
owner: loop/ci-timeouts
pr: 276
title: No <code>timeout-minutes</code> on any CI job
---
A hung step — a stalled tap clone, a wedged smoke-test subprocess — runs until GitHub's default
job timeout instead of failing fast, costliest across the 3 OS &#215; 3 Python <code>tests</code>
matrix. (The card said 8 workflow files; there are 24 now, of which only <code>fuzz.yml</code>
and <code>sonarcloud.yml</code> had a timeout.) Shipped: 24 jobs across 22 files, with the
numbers taken from <em>measured</em> durations over recent runs rather than guessed —
<code>mutation</code>'s slowest observed run was 24.8m so it gets 60, the <code>tests</code>
matrix peaked at 8.3m so it gets 30, <code>publish</code>'s release job gets 45 because the
new release preflight can legitimately wait on a sibling gate, and everything else ran under
2m so it gets 15. A timeout that trips on a normal run is worse than no timeout.
<code>osv-scanner.yml</code>'s <code>scan-pr</code> is the one job left without one: it
delegates to a reusable workflow via a job-level <code>uses:</code>, and GitHub rejects
<code>timeout-minutes</code> there outright — the bound has to live in the called workflow.
A unit test holds the line so a job added next month cannot quietly arrive without one, and
it refuses to pass vacuously if its own parser stops finding jobs.
