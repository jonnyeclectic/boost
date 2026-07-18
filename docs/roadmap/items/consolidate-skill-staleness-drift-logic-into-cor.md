---
id: consolidate-skill-staleness-drift-logic-into-cor
board: code
section: internals
status: next
category: Correctness
complexity: M
impact: High
wow: 3
note: 
order: 3
owner:
pr:
title: Consolidate skill-staleness / drift logic into core
---
The "is this skill outdated" decision — <code>semver_gt</code> → commit compare → <code>sha256_dir</code> vs lock — is reimplemented nearly verbatim in <code>cmd_update</code>, <code>cmd_outdated</code> and <code>_drift_status</code> (<code>pkg.py:277 · taps.py:225 · quality.py:120</code>). Three copies of core business logic that <b>will drift apart</b>. Make it one <code>core</code> function the commands render.
