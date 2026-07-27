---
id: journal-rotation-race-and-handle-leak
board: code
section: internals
status: shipped
category: Concurrency · Bug
complexity: M
impact: Med
wow: 2
note:
order: 31
owner: loop/journal-rotation
pr: 275
title: Journal rotation has a lost-update race between concurrent processes
---
<code>_maybe_rotate</code> reads the whole pulse file and atomically replaces it with a truncated
snapshot — but two concurrent boost processes (explicitly expected per this repo's parallel-loop
model) can both read, then both write their own snapshot, and whichever writes last silently
discards any event the other appended in between. <code>rotation_healthy()</code> also opens the
file with a bare <code>p.open()</code> and never closes it, relying on GC instead of a
<code>with</code> block like every other open in the module. Rotate under a lock (or an
append-only rename scheme), and close the handle explicitly.
Shipped with <code>util.try_lock()</code>, a portable <code>O_CREAT | O_EXCL</code> advisory
lock that needs neither <code>fcntl</code> (absent on Windows) nor <code>msvcrt</code> (absent
everywhere else). It <em>yields False rather than waiting</em>: a process that cannot take it
just returns, because another one is already trimming and blocking would trade a rare lost
update for a common stall. A lock older than five minutes is stolen, so a process killed
mid-rotation cannot wedge the feed forever. Inside the lock the file is re-read (the count
that got us there was taken outside it) and anything appended since is carried into the new
file instead of dropped. <code>log()</code> stays lock-free — <code>O_APPEND</code> writes of
one short record do not tear, and making every command contend on a lock to protect an
advisory feed would be the wrong trade.
Writing the test for a torn append turned up a third defect neither the card nor the code
had noticed: a single invalid byte in the feed raised <code>UnicodeDecodeError</code>, which
is a <code>ValueError</code> and sails straight past the <code>except OSError</code> guard —
so one bad byte crashed <em>every command that logs</em>, permanently. Both reads decode with
<code>errors="replace"</code> now.
