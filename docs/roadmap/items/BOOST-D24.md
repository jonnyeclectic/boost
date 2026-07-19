---
id: BOOST-D24
board: design
track: layout
status: done
impact: med
complexity: L
wow: 4
category: layout
ref: "core/output.py:table() / _fit_widths / _clip_visible"
order: 7
owner: loop/table-width
pr: 127
title: Width-aware shared <code>table()</code>
---
<code>out.table()</code> backs ~28 call sites, and several overflowed: <code>taps</code> padded the NAME column to the widest repo (<code>K-Dense-AI/claude-scientific-skills</code> = 44 cols) and then printed full URLs, so wide catalogs wrapped. Now <code>table()</code> is width-aware itself — when a row would exceed the terminal it shrinks the widest <b>text</b> column and clips its cells with an ellipsis (ANSI-aware, so colored cells keep their color and close cleanly), while <b>numeric</b> columns are right-aligned like tabular figures and never truncated. Narrow tables render byte-identical to before; the logic only engages on overflow or multi-row number columns. Delivered test-first: dedicated unit coverage for <code>_numeric_col</code>, <code>_clip_visible</code>, <code>_fit_widths</code>, and the integrated render keeps the mutation gate green.
