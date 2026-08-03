---
id: modernization-smells-refurb-pyupgrade
board: code
section: dx
status: shipped
category: Quality · Smell
complexity: S
impact: Low
wow: 2
note: shipped under the 3.9 floor; the floor is now 3.12
order: 7
owner: loop/modernization-smells
pr: 232
title: Modernization smells — <code>refurb</code> + <code>pyupgrade</code>
---
<code>refurb</code>'s unique <code>FURB</code> checks flag dated idioms
           the ruff families miss, and <code>pyupgrade</code> rewrites to the
           cleanest form the floor allows. Keeps the codebase
           reading like modern Python instead of accreting legacy patterns.
           Shipped against <code>&gt;=3.9</code>; the floor later moved to
           <code>&gt;=3.12</code>, which widens what "cleanest form" means — the
           PEP 585/604 sweep that unlocks is its own item.
