---
id: BOOST-D11
board: design
track: motion
status: done
impact: med
complexity: M
wow: 4
category: motion
ref: core/output.py · new progress()
order: 2
owner:
pr:
title: Determinate progress bars for batch ops
---
Multi-item commands — <code>reindex</code>, <code>update</code>, <code>sync</code>, <code>snapshot</code> restore — give no sense of "how far in." Add a gradient-filled progress bar (<code>N/total</code> + ETA) for anything looping over a known count, so long operations read as intentional rather than hung.
