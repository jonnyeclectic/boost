---
id: ai-bridge-silent-failure-logging
board: code
section: internals
status: planned
category: Observability
complexity: S
impact: Med
wow: 2
note:
order: 40
owner:
pr:
title: AI bridge swallows failures with zero diagnostic trail
---
<code>core/ai.py</code>'s CLI and API call paths both catch their failure modes (timeout, OS error,
URL error, bad JSON) and return <code>None</code> — but neither ever calls into the logger, unlike
the rest of boost. A user whose expired key or flaky network silently degrades every AI-assisted
command to its heuristic fallback has no trail to diagnose why, even with <code>--debug</code>. Add
a one-line <code>logger.debug(...)</code> in each except branch.
