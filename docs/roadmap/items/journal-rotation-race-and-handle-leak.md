---
id: journal-rotation-race-and-handle-leak
board: code
section: internals
status: planned
category: Concurrency · Bug
complexity: M
impact: Med
wow: 2
note:
order: 31
owner:
pr:
title: Journal rotation has a lost-update race between concurrent processes
---
<code>_maybe_rotate</code> reads the whole pulse file and atomically replaces it with a truncated
snapshot — but two concurrent boost processes (explicitly expected per this repo's parallel-loop
model) can both read, then both write their own snapshot, and whichever writes last silently
discards any event the other appended in between. <code>rotation_healthy()</code> also opens the
file with a bare <code>p.open()</code> and never closes it, relying on GC instead of a
<code>with</code> block like every other open in the module. Rotate under a lock (or an
append-only rename scheme), and close the handle explicitly.
