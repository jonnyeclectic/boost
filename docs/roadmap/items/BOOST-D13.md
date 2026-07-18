---
id: BOOST-D13
board: design
track: motion
status: done
impact: low
complexity: S
wow: 3
category: ux
ref: "core/output.py:41 · commands/pkg.py"
order: 4
owner:
pr:
title: Framed success summary with next step
---
<code>ok()</code> prints a lone green check, then the command just ends. After <code>install</code>/<code>uninstall</code>, close with a small framed confirmation — what changed, where it landed, and the obvious next step (<code>boost info &lt;skill&gt;</code>) — so a completed action feels finished, not dropped.
