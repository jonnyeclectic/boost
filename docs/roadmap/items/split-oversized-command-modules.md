---
id: split-oversized-command-modules
board: code
section: internals
status: shipped
category: Maintainability
complexity: L
impact: Med
wow: 2
note: 
order: 15
owner: loop/split-cmds
pr: 221
title: Split oversized command modules
---
<code>quality.py</code> (15 cmds / 1,264 lines) mixes audit regexes, conflict NLP, decay scoring, fingerprinting, a health dashboard and tap-provenance; <code>intelligence.py</code> and <code>configuration.py</code> are similarly overloaded. Split along cohesive seams to shrink blast radius. First seam (this PR): lift the installed-skill safety &amp; integrity commands — <code>audit</code>, <code>verify</code>, <code>attest</code>, <code>quarantine</code> — into <code>commands/safety.py</code>, with the two shared helpers in <code>commands/_common.py</code>; <code>quality.py</code> drops from 1,264 to ~955 lines. Tap-side <code>trust</code> and the health/diagnostics set stay put.
