---
id: hooks-list-drops-the-name-before-the-host
board: code
section: planned
status: shipped
category: UX · Bug
complexity: S
impact: Low
wow: 2
note: fixed — `name` now leads the table, so a narrow pane drops it after `host`, `scope`, `event` and `matcher`, never before
order: 326
owner: loop/hooks-name-drop
pr: 916
title: At a narrow pane <code>boost hooks list</code> drops <code>name</code>, the argument <code>hooks remove -n</code> takes, while <code>host</code> and <code>scope</code> survive
---
<b>Measured.</b> With the two hooks <code>boost bmad autopilot</code> installs (<code>bmad</code>, <code>bmad-route</code>), <code>COLUMNS=65 boost hooks list</code> prints <code>host scope event command</code>: the column dropped second, after <code>matcher</code>, is <code>name</code>, while <code>host</code> prints the same word on every row. <code>out.table</code> drops right to left, skipping <code>keep=</code>, and <code>name</code> sits in the middle of this table.

Protecting it is not the fix. PR 902 tried <code>keep=("command", "name")</code> and it re-opened the overflow that PR closed: when both protected columns together outgrow the pane, nothing is left that may drop, and the row prints past the edge (<code>bmad-route</code> plus a 72-cell command printed 84 wide at 80). <code>tests/functional/test_cli_hooks.py::test_list_fits_the_pane_with_a_long_name_and_command</code> pins that.

Candidate shapes, not decided: put <code>name</code> first in this table, so right-to-left dropping reaches it last; or give <code>out.table</code> a drop order separate from <code>keep=</code> (drop-last rather than never-drop). The name is always available in <code>boost hooks list --json</code> in the meantime.

<b>Shipped.</b> <code>name</code> is now the first column (<code>name host scope event matcher command</code>), so the right-to-left drop reaches it after every other droppable column, and <code>out.table</code> is unchanged: no new parameter for one caller, and the table now follows the order the fitter's own docs describe, identifier first and repeated chrome last. Measured at <code>COLUMNS</code> 40&ndash;100, piped and in a pty, with the autopilot's two hooks and a third whose command is 72 cells: wherever any column besides <code>command</code> prints, <code>name</code> is one of them, and the row never passes the pane except where the protected command alone is wider than it, the same widths as before. With the autopilot hooks alone, piped, <code>name</code> now prints at 52 widths out of 61, up from 27; with the long command, at 20, up from none. It can still be shortened with an ellipsis in a band of up to three cells before each drop, which is the fitter's existing shrink-before-drop rule. The column order changes at every width, and <code>boost hooks list --json</code> is the stable shape for scripts.
