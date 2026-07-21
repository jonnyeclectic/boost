---
id: startup-and-import-time-budget-x-importtime
board: code
section: compat
status: inflight
category: Perf · Startup
complexity: M
impact: High
wow: 4
note: lazy-import guard
order: 5
owner: loop/import-budget
pr:
title: Startup &amp; import-time budget — <code>-X importtime</code>
---
For a CLI, cold-start latency <em>is</em> the UX — every command pays it.
           A gate on <code>python -X importtime boost</code> catches the accidental
           top-level import of a heavy module (the optional <code>[rag]</code> stack
           is the obvious trap) and keeps common commands feeling instant.
