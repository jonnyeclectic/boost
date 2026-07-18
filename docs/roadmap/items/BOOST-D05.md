---
id: BOOST-D05
board: design
track: layout
status: done
impact: high
complexity: M
wow: 5
category: layout
ref: commands/discovery.py · search
order: 1
owner:
pr:
title: "Fix <code>search</code>: truncate &amp; width-clamp results"
---
Today <code>boost search</code> is the worst screen in the app: a single result can dump a <b>2,000-character description with literal, unrendered <code>\\n\\n</code> escapes</b>, while names are padded to a fixed 30 columns that waste half the row. Clamp each row to the live terminal width, collapse whitespace/escape artifacts, and ellipsize. This one fix turns a wall of noise into a scannable list.
