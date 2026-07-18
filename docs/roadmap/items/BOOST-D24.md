---
id: BOOST-D24
board: design
track: layout
status: proposed
impact: med
complexity: L
wow: 4
category: layout
ref: "core/output.py:table() · commands/taps.py"
order: 7
owner:
pr:
title: Width-aware shared <code>table()</code>
---
<code>out.table()</code> backs 28 call sites, and several still overflow: <code>taps</code> pads the NAME column to the widest repo (<code>K-Dense-AI/claude-scientific-skills</code> = 44 cols) and then prints full URLs, so wide catalogs wrap. The durable fix is to make <code>table()</code> itself width-aware — shrink the widest text column to the terminal and right-align numeric columns — instead of truncating per-caller. Higher blast radius (28 callers, many exact-output tests), so it needs a careful, test-first pass.
