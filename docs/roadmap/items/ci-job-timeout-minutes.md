---
id: ci-job-timeout-minutes
board: code
section: pipeline
status: planned
category: CI/CD
complexity: S
impact: Low
wow: 1
note:
order: 10
owner:
pr:
title: No <code>timeout-minutes</code> on any CI job
---
None of the 8 workflow files set <code>timeout-minutes</code>, so a hung step — a stalled tap
clone, a wedged smoke-test subprocess — runs until GitHub's default job timeout instead of failing
fast, costliest across the 2 OS &#215; 3 Python <code>tests</code> matrix. Add explicit per-job
timeouts: short for <code>lint</code>/<code>pip-audit</code>, longer for
<code>tests</code>/<code>mutation</code>.
