---
id: BOOST-D21
board: design
track: system
status: done
impact: med
complexity: M
wow: 4
category: tooling
ref: docs/demo.tape · Makefile
order: 3
owner:
pr:
title: Scripted demo recording (VHS / asciinema)
---
There's a <code>docs/demo.tape</code> + <code>demo.gif</code>, but no repeatable way to re-record once the aesthetic changes — and <code>tmux</code> isn't even installed in the dev box. Add a <code>make demo</code> that drives a scripted session (VHS tape or asciinema, optionally split-pane via tmux) and refreshes the GIF, so the README and portfolio always show the current look.
