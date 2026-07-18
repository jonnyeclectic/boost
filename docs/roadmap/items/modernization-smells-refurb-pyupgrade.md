---
id: modernization-smells-refurb-pyupgrade
board: code
section: dx
status: planned
category: Quality · Smell
complexity: S
impact: Low
wow: 2
note: respects 3.9 floor
order: 7
owner:
pr:
title: Modernization smells — <code>refurb</code> + <code>pyupgrade</code>
---
<code>refurb</code>'s unique <code>FURB</code> checks flag dated idioms
           the ruff families miss, and <code>pyupgrade</code> rewrites to the
           cleanest form the <code>&gt;=3.9</code> floor allows. Keeps the codebase
           reading like modern Python instead of accreting legacy patterns.
