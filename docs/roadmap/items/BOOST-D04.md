---
id: BOOST-D04
board: design
track: color
status: proposed
impact: med
complexity: S
wow: 2
category: color
ref: core/output.py · commands/*.py
order: 4
owner:
pr:
title: Semantic color roles, not raw codes
---
Commands scatter <code>out.c(x, out.YELLOW)</code> and <code>out.GREEN</code> literally throughout the command layer, so a palette change means a repo-wide sweep. Introduce named roles — <code>accent</code>, <code>brand</code>, <code>success</code>, <code>warn</code>, <code>danger</code>, <code>muted</code> — resolved through the palette. Re-theming becomes a one-file edit, and intent reads clearly at every call site.
