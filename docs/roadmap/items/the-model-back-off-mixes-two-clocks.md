---
id: the-model-back-off-mixes-two-clocks
board: code
section: planned
status: shipped
category: Search · Bug
complexity: S
impact: Medium
wow: 3
note: The record that exists to stop a 133 MB fetch was dated by one clock and read against another…
order: 343
owner: loop/backoff-mtime-clock
pr: "975"
title: The model back-off dated its record by the filesystem clock and read it against the process clock
---
<b>Found by a red <code>tests (windows-latest, 3.12)</code> leg on an unrelated dependency PR.</b>
<code>localembed</code> records a failed fetch or load of the local embedding model so the next
<code>boost search</code> does not pay the 133 MB download again — measured at ~3.6 s a search against
0.1 s. <code>last_failure()</code> dated that record by <code>p.stat().st_mtime</code>, the
<i>filesystem's</i> clock, while <code>backing_off()</code> measured its age against
<code>time.time()</code>, the <i>process's</i>, and discards anything dated in the future as a clock
set back.
<br><br>
The two clocks are the same on macOS and Linux and are not on Windows: under Python 3.12
<code>time.time()</code> is the coarse <code>GetSystemTimeAsFileTime</code> (~15.6 ms) while NTFS
stamps the write from a precise one. So a marker written moments earlier read as future-dated, the
back-off was thrown away, and the next process fetched anyway — which is exactly what the CI leg
caught: <code>test_the_next_process_does_not_fetch_either</code> counted two fetches where one was
pinned. Reproduced on macOS by forcing 16 ms of skew: <code>backing_off()</code> flips True → False.
<br><br>
<b>Fixed.</b> <code>_note_failure</code> writes <code>at</code> into the record, so writer and reader
use one clock; the mtime stays as the fallback for a marker written before the field existed. A
skew tolerance was the other option and is not available — <code>backing_off(now=at - 1) is
False</code> is pinned deliberately, because honouring a future-dated record holds the model back for
however far ahead the clock is.
<br><br>
Four tests, two of which fail against the old module: the record carries its own clock, a marker
whose mtime runs an hour ahead still holds back, a legacy marker with no <code>at</code> still dates
from its file, and an <code>at</code> that is not a number falls back to the mtime — parametrised
over <code>"yesterday"</code>, <code>None</code>, <code>True</code> and <code>nan</code>, because in
Python a bool <i>is</i> an int and every comparison against <code>nan</code> is False, which would
read the half-open window as expired and re-fetch on every search.
