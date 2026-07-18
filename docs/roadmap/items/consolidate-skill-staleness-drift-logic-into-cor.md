---
id: consolidate-skill-staleness-drift-logic-into-cor
board: code
section: shipped
status: shipped
category: Correctness
complexity: M
impact: High
wow: 3
note: three copies → one core module
order: 3
owner: loop/consolidate-staleness
pr: 91
title: Consolidate skill-staleness / drift logic into core
---
The "is this skill outdated" decision — <code>semver_gt</code> → commit compare → <code>sha256_dir</code> vs lock — was reimplemented nearly verbatim in <code>cmd_update</code>, <code>cmd_outdated</code> and <code>_drift_status</code> — three copies of core business logic that would drift apart. It now lives in one place: <code>core/staleness.py</code> exposes two <b>pure</b> (I/O-free) decisions — <code>upstream_reason()</code> (the version→commit→content ladder rendered by <code>cmd_update</code>/<code>cmd_outdated</code>) and <code>drift_state()</code> (the store/local-edits/upstream ladder rendered by <code>_drift_status</code>). The commands became thin renderers; behavior is byte-for-byte preserved and the new module is fully unit-tested (every branch pinned, all mutants killed).
