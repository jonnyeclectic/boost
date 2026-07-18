---
id: BOOST-D06
board: design
track: layout
status: done
impact: med
complexity: M
wow: 4
category: layout
ref: core/output.py · new panel()
order: 2
owner:
pr:
title: Glass-panel box primitives
---
The web system frames everything in rounded glass; the CLI frames nothing. Add rounded box-drawing primitives (<code>╭─╮ │ ╰─╯</code>) with dim <code>--line</code> borders and an optional title, mirroring the web <code>.glass</code>/<code>.window</code> surfaces. Reusable chrome for <code>doctor</code>, <code>info</code>, <code>snapshot</code> and success summaries.
