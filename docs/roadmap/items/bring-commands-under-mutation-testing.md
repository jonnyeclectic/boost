---
id: bring-commands-under-mutation-testing
board: code
section: planned
status: planned
category: Testing · Gap
complexity: XL
impact: High
wow: 3
note: 
order: 2
owner:
pr:
title: Bring <code>commands/</code> under mutation testing
---
The ~5,000-line CLI command layer has <strong>zero</strong> mutation
           coverage today — mutmut is scoped to <code>core/</code> only. Extend
           the gate (or a second gate) to the command groups.
