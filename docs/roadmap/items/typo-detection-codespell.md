---
id: typo-detection-codespell
board: code
section: dx
status: inflight
category: Quality · Docs
complexity: S
impact: Med
wow: 2
note: user-facing text
order: 4
owner: loop/codespell-gate
pr:
title: Typo detection — <code>codespell</code>
---
Cheap, high-signal for a project this documentation-heavy: scan the
           README, <code>docs/*.html</code>, docstrings and every user-facing CLI
           string for misspellings. A typo in <code>boost --help</code> is a bug
           users see on their first run.
