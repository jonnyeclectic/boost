---
id: BOOST-D03
board: design
track: color
status: done
impact: med
complexity: M
wow: 5
category: color
ref: core/output.py · new gradient()
order: 3
owner:
pr:
title: Gradient text renderer — the signature move
---
The brand <em>is</em> the cyan→violet→pink <code>--grad</code>. Interpolate it per-character across a string so headings, the <code>boost</code> wordmark and hero counts shimmer in the terminal exactly like the web hero. A pure-Python lerp over the three stops; falls back to a single accent color when truecolor is unavailable.
