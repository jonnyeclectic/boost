---
id: guard-output-table-against-ragged-rows
board: code
section: internals
status: planned
category: Robustness
complexity: S
impact: Low
wow: 1
note: 
order: 19
owner:
pr:
title: Guard <code>output.table</code> against ragged rows
---
Column-width computation does <code>max(… for r in rows if i &lt; len(r))</code> (<code>core/output.py:300</code>), which raises <code>max() arg is empty</code> when a header column has no matching cell in any row. Add <code>default=0</code>.
