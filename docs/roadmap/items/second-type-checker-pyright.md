---
id: second-type-checker-pyright
board: code
section: pipeline
status: inflight
category: Testing · Type
complexity: M
impact: Med
wow: 3
note: editor-parity
order: 6
owner: loop/pyright
pr:
title: Second type checker — <code>pyright</code>
---
Run Microsoft's <code>pyright</code> alongside mypy. Its independent
           inference catches <code>None</code>-flow and narrowing bugs the current
           mypy config lets slide, and it's the same engine most editors use — so
           CI enforces what contributors already see. Two type checkers rarely
           agree on <em>nothing</em>.
