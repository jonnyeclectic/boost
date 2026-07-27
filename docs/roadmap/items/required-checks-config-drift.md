---
id: required-checks-config-drift
board: code
section: dx
status: shipped
category: CI/CD
complexity: S
impact: Med
wow: 2
note:
order: 10
owner: loop/required-checks-as-code
pr:
title: Required-status-checks list is prose-only, and already stale
---
<b>Shipped.</b> <code>.github/required-checks.txt</code> is now the source of truth and <code>scripts/check_required_checks.py</code> (in <code>make lint</code>, so in CI) fails when a required name stops matching a job that runs on <code>pull_request</code>. It also caught something the card missed: <b>three check names were ambiguous</b> — <code>lint</code> in ci/markdownlint/theme-lint, <code>audit</code> in lighthouse/pip-audit, <code>analyze</code> in codeql/sonarcloud. GitHub matches required checks by name, so none of those could be required unambiguously, and the colliding jobs are renamed. Original report follows. Branch protection was hand-configured in GitHub Settings and only described in prose in
<code>CONTRIBUTING.md</code> — there is no config-as-code (a repo ruleset export, Terraform, or a CI
check diffing required names against real job names) to catch drift. It has already drifted:
<code>ci.yml</code>'s <code>install-smoke</code> job, and the <code>pip-audit</code>/
<code>package-metadata</code> workflows, are never listed as required, so a PR can merge to main
with any of them red.
