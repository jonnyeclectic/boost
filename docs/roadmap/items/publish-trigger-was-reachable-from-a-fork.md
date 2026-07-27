---
id: publish-trigger-was-reachable-from-a-fork
board: code
section: trust
status: shipped
category: Security
complexity: S
impact: High
wow: 5
note: a PR branch named main could cut a PyPI release
order: 53
owner: loop/publish-trigger-hardening
pr:
title: The release trigger was reachable from a fork — <code>branches:</code> filters head_branch, not the event
---
<code>publish.yml</code> fires on <code>workflow_run</code> of <code>ci</code> with
<code>branches: [main]</code>. That filter matches the <b>triggering run's head_branch</b> —
not the event type, and not the repository. <code>ci.yml</code> also runs on
<code>pull_request</code>, so a pull request opened from a branch named <code>main</code>
produced a ci run whose head_branch was <code>main</code> and satisfied the filter. The job
gate checked only <code>workflow_run.conclusion == 'success'</code>, so a green run on that
path fired the release job with <code>contents: write</code> and PyPI Trusted-Publishing
OIDC — cutting a tag, a GitHub Release and a PyPI upload. There was no second gate: the
<code>pypi</code> environment has no protection rules and no deployment branch policy.

Never code execution — the checkout pins <code>ref: main</code>, so what ships is always
main's code. The exposure was an <b>unreviewed release triggerable from outside the repo</b>.

Measured rather than assumed: <code>ci-failure-issue.yml</code> draws from the same
<code>workflow_run</code> source with no <code>branches</code> filter and has <b>679</b> runs
against ci's <b>254</b> pushes, proving <code>workflow_run</code> fires for PR-triggered runs
too; only the head_branch filter kept <code>publish.yml</code> near the push count.

Fixed by requiring the triggering run to be a <code>push</code> whose
<code>head_repository</code> is this repo. No regression: all 254 ci runs with
<code>head_branch=main</code> are pushes from <code>jonnyeclectic/boost</code>, and the gate
still admits push-to-main and <code>workflow_dispatch</code> while rejecting fork PRs,
same-repo PRs and red CI.
