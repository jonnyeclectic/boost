---
id: identifier-columns-shrink-to-a-name-no-command-accepts
board: code
section: planned
status: shipped
category: UX · Bug
complexity: M
impact: Low
wow: 2
note: In the few columns before out.table drops a column, the widest one that can shrink is squeezed with an ellipsis, and in hooks list that is the name remove -n takes…
order: 329
owner: loop/identifier-columns
pr: 937
title: Just before <code>out.table</code> drops a column, it shrinks the widest one with an ellipsis. In <code>hooks list</code> that is often <code>name</code>, and <code>bmad-r…</code> is not a name <code>hooks remove -n</code> accepts.
---
<b>Measured</b> on the branch that moved <code>name</code> to the front of <code>boost hooks list</code>, with the autopilot's hook names (<code>bmad</code>, <code>bmad-route</code>) piped at <code>COLUMNS</code> 40–100. <code>name</code> now shows at 52 widths, where it showed at 27. At 24 of those it is shortened, e.g. <code>bmad-r…</code>, in the widths 49–51, 57–59, 65–67, 74–79 and 83–91, the card's own width of 65 included. Before the reorder the same happened at 13 of 27.

The cause is the fitter's shrink-before-drop rule (<code>output._fit_columns</code>). Before it drops a column, it shrinks the widest one that can still shrink, down to <code>_MIN_COL</code>. For prose that is the right trade. For an identifier, a clipped value is worse than an absent one, because it reads like data and is not: <code>boost hooks remove -n bmad-r…</code> removes nothing. <code>keep=</code> cannot express "may drop, never shrink". It means never drop and never shrink, and two such columns together can outgrow the pane, the overflow PR 902 closed.

Likely fix: <code>out.table</code> takes a third class of column, <i>whole or absent</i>. The fitter never shrinks it and drops it in right-to-left order like any other column. <code>hooks list</code> would mark <code>name</code>, and <code>taps</code> and <code>list</code> would mark their NAME columns, the other arguments people copy. Measure every caller before and after: wide panes must stay byte-identical.
