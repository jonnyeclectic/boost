---
id: required-checks-config-drift
board: code
section: dx
status: planned
category: CI/CD
complexity: S
impact: Med
wow: 2
note:
order: 10
owner:
pr:
title: Required-status-checks list is prose-only, and already stale
---
Branch protection is hand-configured in GitHub Settings and only described in prose in
<code>CONTRIBUTING.md</code> — there is no config-as-code (a repo ruleset export, Terraform, or a CI
check diffing required names against real job names) to catch drift. It has already drifted:
<code>ci.yml</code>'s <code>install-smoke</code> job, and the <code>pip-audit</code>/
<code>package-metadata</code> workflows, are never listed as required, so a PR can merge to main
with any of them red.
