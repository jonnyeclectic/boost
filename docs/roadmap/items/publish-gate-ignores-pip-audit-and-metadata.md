---
id: publish-gate-ignores-pip-audit-and-metadata
board: code
section: pipeline
status: planned
category: CI/CD
complexity: S
impact: High
wow: 3
note: gates PyPI
order: 9
owner:
pr:
title: <code>publish.yml</code> ignores the <code>pip-audit</code> / metadata gates
---
<code>publish.yml</code> triggers on <code>workflow_run: [ci]</code> and gates only on
<code>github.event.workflow_run.conclusion == 'success'</code> — it never checks the
independently-triggered <code>pip-audit.yml</code> or <code>package-metadata.yml</code> workflows
that run on the same push. A merge that fails the live-CVE gate or the twine/metadata check still
auto-publishes to PyPI as long as <code>ci</code> itself is green. Fold both as jobs inside
<code>ci.yml</code>, or have the release job poll their run status via the API before publishing.
