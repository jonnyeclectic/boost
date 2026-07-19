---
id: BOOST-D04
board: design
track: color
status: done
impact: med
complexity: S
wow: 2
category: color
ref: core/output.py:ROLES / role() · commands/*.py
order: 4
owner: loop/color-roles
pr: 111
title: Semantic color roles, not raw codes
---
Commands scattered <code>out.c(x, out.YELLOW)</code> and <code>out.GREEN</code> literally throughout the command layer, so a palette change meant a repo-wide sweep. Now a single <code>ROLES</code> table in <code>output.py</code> maps six named roles — <code>accent</code>, <code>brand</code>, <code>success</code>, <code>warn</code>, <code>danger</code>, <code>muted</code> — resolved through the Aurora palette (truecolor → 16-color → plain), and <code>out.role(text, name)</code> paints by intent. Every color call site across all eight command groups now reads as meaning, not mechanics; brand hues (accent/success/warn) upgraded from flat 16-color to on-theme truecolor in the process. Re-theming is a one-file edit.
