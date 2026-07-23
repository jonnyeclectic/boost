---
id: BOOST-D08
board: design
track: layout
status: done
impact: med
complexity: M
wow: 3
category: layout
ref: "core/output.py · table()"
order: 4
owner: loop/d08-tables
pr: 202
title: Width-aware, right-aligned tables
---
<code>table()</code> is a naive <code>ljust</code> that ignores terminal width and left-aligns numeric columns. Make it width-aware (shrink the widest text column to fit), right-align counts with tabular figures, and add dim column separators — matching the web's <code>font-variant-numeric: tabular-nums</code> stat blocks.
