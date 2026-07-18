---
id: BOOST-D02
board: design
track: color
status: done
impact: high
complexity: M
wow: 3
category: color
ref: "core/output.py:26–38"
order: 2
owner:
pr:
title: Terminal capability detection &amp; graceful degradation
---
<code>use_color()</code> is binary — color or nothing. Add a tier ladder: <b>truecolor</b> (<code>COLORTERM=truecolor/24bit</code>) → <b>256</b> → <b>16</b> → <b>none</b>, so the Aurora tokens snap to the nearest available color instead of vanishing. Keep the existing <code>NO_COLOR</code> honor, add a <code>BOOST_COLOR=always/auto/never</code> override, and treat <code>TERM=dumb</code> as none.
