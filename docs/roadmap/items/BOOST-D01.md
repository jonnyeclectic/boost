---
id: BOOST-D01
board: design
track: color
status: done
impact: high
complexity: S
wow: 4
category: color
ref: "core/output.py:15–38"
order: 1
owner:
pr:
title: 24-bit Aurora palette in <code>output.py</code>
---
The whole CLI runs on eight legacy SGR codes (<code>RED</code>…<code>CYAN</code>) that don't match the brand at all — the front door paints section headers in generic <code>[33m</code> yellow. Add truecolor <code>rgb()</code> helpers mapping the exact web tokens: cyan <b>#22d3ee</b>, violet <b>#a855f7</b>, pink <b>#f472d0</b>, green <b>#4ade80</b>, yellow <b>#facc15</b>, plus <code>--text</code>/<code>--text-3</code> greys. One map recolors everything.
