---
id: hooks-list-drops-the-name-before-the-host
board: code
section: planned
status: planned
category: UX · Bug
complexity: S
impact: Low
wow: 2
note: At a narrow pane `boost hooks list` drops `name` — the argument `hooks remove -n` takes — while `host` and `scope` survive…
order: 326
owner:
pr:
title: At a narrow pane <code>boost hooks list</code> drops <code>name</code>, the argument <code>hooks remove -n</code> takes, while <code>host</code> and <code>scope</code> survive
---
<b>Measured.</b> With the two hooks <code>boost bmad autopilot</code> installs (<code>bmad</code>, <code>bmad-route</code>), <code>COLUMNS=65 boost hooks list</code> prints <code>host scope event command</code>: the column dropped second, after <code>matcher</code>, is <code>name</code>, while <code>host</code> prints the same word on every row. <code>out.table</code> drops right to left, skipping <code>keep=</code>, and <code>name</code> sits in the middle of this table.

Protecting it is not the fix. PR 902 tried <code>keep=("command", "name")</code> and it re-opened the overflow that PR closed: when both protected columns together outgrow the pane, nothing is left that may drop, and the row prints past the edge (<code>bmad-route</code> plus a 72-cell command printed 84 wide at 80). <code>tests/functional/test_cli_hooks.py::test_list_fits_the_pane_with_a_long_name_and_command</code> pins that.

Candidate shapes, not decided: put <code>name</code> first in this table, so right-to-left dropping reaches it last; or give <code>out.table</code> a drop order separate from <code>keep=</code> (drop-last rather than never-drop). The name is always available in <code>boost hooks list --json</code> in the meantime.
