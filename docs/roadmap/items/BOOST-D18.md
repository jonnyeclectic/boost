---
id: BOOST-D18
board: design
track: commands
status: done
impact: low
complexity: S
wow: 2
category: ux
ref: "commands/info.py:117–119 · core/output.py"
order: 5
owner:
pr:
title: Consistent empty-states &amp; hint styling
---
Empty and hint lines are ad-hoc — <code>info</code>'s "no skills installed" hint is a hand-rolled <code>DIM</code> string. Standardize a single empty-state affordance (muted icon + one-line guidance + suggested command) and a single hint style, applied everywhere, so guidance always looks the same.
