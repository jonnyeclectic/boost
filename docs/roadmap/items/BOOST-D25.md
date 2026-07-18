---
id: BOOST-D25
board: design
track: commands
status: done
impact: med
complexity: L
wow: 3
category: ux
ref: cliparse.py (BoostArgumentParser) · all 10 command files
order: 6
owner:
pr:
title: Branded usage &amp; error output
---
Grading confirmed this hits <b>every command with a required argument</b> — <code>boost uninstall</code>, <code>boost snapshot</code> and more all dump raw, unstyled <code>argparse</code>: a multi-line usage block with a bare <code>error:</code>, nothing like the branded top-level dispatch (which already routes through <code>Error:</code> + a difflib "did you mean"). The durable fix is a shared <code>BoostArgumentParser</code> subclass whose <code>error()</code>/usage route through the Aurora output layer, adopted across the ~50 per-command parsers — a broad, test-first sweep, so logged rather than rushed.
