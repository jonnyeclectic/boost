---
id: BOOST-D23
board: design
track: layout
status: done
impact: high
complexity: S
wow: 4
category: layout
ref: commands/discovery.py · cmd_trending
order: 6
owner:
pr:
title: <code>trending</code> had the same overflow as <code>search</code>
---
Grading the un-touched commands surfaced a sibling of D05: <code>boost trending</code> piped raw catalog descriptions straight into <code>table()</code>, so a single 300-char description blew the table across the pane. Fixed by clipping each description through <code>out.truncate()</code> to the width left after the name/installs/last columns — the same helper the search fix introduced.
