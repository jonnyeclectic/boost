---
id: workflow-sast-zizmor
board: code
section: pipeline
status: planned
category: Security · CI/CD
complexity: S
impact: High
wow: 5
note: pipx-run
order: 1
owner:
pr:
title: Workflow SAST — <code>zizmor</code>
---
boost's four workflows embed <code>github-script</code> JavaScript and
           shell and drive a Trusted-Publisher release — a rich attack surface.
           <code>zizmor</code> statically flags template injection, unpinned
           actions, over-broad <code>GITHUB_TOKEN</code> permissions and dangerous
           triggers. The one tool that audits the automation that ships every
           other fix.
