---
id: workflow-linting-actionlint
board: code
section: pipeline
status: planned
category: Quality · CI/CD
complexity: S
impact: Med
wow: 3
note: shellcheck built in
order: 2
owner:
pr:
title: Workflow linting — <code>actionlint</code>
---
Catches GitHub Actions YAML bugs before they fail a live release:
           malformed <code>${{ }}</code> expressions, deprecated syntax, and
           shellcheck run over every <code>run:</code> block. Cheap insurance for a
           repo whose release is fully automated — a broken workflow is a broken
           publish.
