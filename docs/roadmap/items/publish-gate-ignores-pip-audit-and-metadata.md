---
id: publish-gate-ignores-pip-audit-and-metadata
board: code
section: pipeline
status: shipped
category: CI/CD
complexity: S
impact: High
wow: 3
note: gates PyPI
order: 9
owner: loop/publish-gate
pr: 267
title: <code>publish.yml</code> ignores the <code>pip-audit</code> / metadata gates
---
<code>publish.yml</code> triggers on <code>workflow_run: [ci]</code> and gates only on
<code>github.event.workflow_run.conclusion == 'success'</code> — it never checks the
independently-triggered <code>pip-audit.yml</code> or <code>package-metadata.yml</code> workflows
that run on the same push. A merge that fails the live-CVE gate or the twine/metadata check still
auto-publishes to PyPI as long as <code>ci</code> itself is green.
Shipped as the second option: <code>scripts/release_preflight.py</code> runs as the release job's
first step — before <code>release-drafter</code> creates the tag, so a blocked release leaves no
published Release behind — and waits for each required workflow to conclude for
<code>git rev-parse HEAD</code>, the commit actually checked out and about to be built.
Folding them into <code>ci.yml</code> was rejected: <code>pip-audit</code> also runs weekly on a
cron, which inside <code>ci.yml</code> would drag the whole 9-cell test matrix along with it.
The gate <strong>fails closed</strong> — red, cancelled, <em>skipped</em>, never started, still
running at the deadline and an unreadable API reply are all refusals. Silence is the dangerous
case: a gate that never ran leaves nothing red to see, so it must never read as consent.
