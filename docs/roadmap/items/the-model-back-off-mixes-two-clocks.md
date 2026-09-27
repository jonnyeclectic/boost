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
<b>Fixed in three rounds, each one found by a test rather than argued for.</b>
<b>1.</b> <code>_note_failure</code> writes <code>at</code> into the record, so writer and reader use
one clock. That repairs every marker written from then on and nothing already on disk — and a marker
already on disk is one of the three things the mtime fallback serves, alongside a marker that will
not parse and an <code>at</code> that is not a number. So the bug moved into the fallback rather than
out of the module, and <code>tests (windows-latest, 3.12)</code> said so again:
<code>test_a_legacy_marker_falls_back_to_its_mtime</code> failed there with <code>assert False is
True</code> out of <code>backing_off()</code> while every other leg passed.
<br><br>
<b>2.</b> The fallback is a <i>proxy</i> for when the record was written, read off the filesystem's
clock and judged against the process's, so a reading that runs ahead of now is granted a grace and
taken as now. <b>3.</b> That grace is <b>bounded</b> (<code>MTIME_GRACE</code>, one second against
the ~15.6 ms the case needs), and the bound is the part that is easy to leave out. Clamping
unconditionally — <code>min(mtime, now)</code>, which is what round 2 shipped — recomputes
<code>at</code> as <code>now</code> on every read, so the age never reaches
<code>RETRY_AFTER</code>, no attempt is ever made, and nothing can replace the record: a home
directory restored with <code>rsync -t</code> from a fast box, or an exFAT mount stamping in the
wrong timezone, would sit on BM25 until the wall clock caught up, clearable only by
<code>boost reindex --dense</code>. Past the bound the stale date is honoured and one attempt gets
through — and that attempt is the cure, because it rewrites the marker with an <code>at</code> from
<code>time.time()</code>, after which the filesystem's clock never decides this again.
<br><br>
A skew tolerance in <code>backing_off</code> itself is still not available:
<code>backing_off(now=at - 1) is False</code> is pinned deliberately, because honouring a
future-dated <i>recorded</i> <code>at</code> would hold the model back for however far ahead the
clock is. The two paths differ on purpose — zero tolerance for a number that came from
<code>time.time()</code> and can only be ahead by being wrong, a bounded grace for one read off a
genuinely different clock.
<br><br>
<b>The guard on <code>at</code> needed the same treatment.</b> Rejecting <code>nan</code> and
stopping there left the value next door: <code>inf</code> passes every check and makes each age
<code>-inf</code>, which reads as expired and re-fetches on every search — the exact outcome the
<code>nan</code> clause exists to prevent. A 400-digit JSON integer is a valid Python <code>int</code>
that <code>float()</code> refuses with <code>OverflowError</code>, raised from a function whose
contract is to return <code>None</code> rather than throw, on the search path. And 1e30 is finite,
so it is past every guard by design — a timestamp is not wrong for being large — which makes it
<code>boost doctor</code>'s problem, where <code>datetime.fromtimestamp</code> raises three
different ways; doctor now drops the "last tried" clause rather than becoming the failure it is
reporting.
<br><br>
Seven tests. Four fail against <code>main</code>: the record carries its own clock, a marker whose
mtime runs an hour ahead still holds back, a legacy marker a tick ahead still holds back, and doctor
survives an undateable stamp. The other three each kill a specific earlier draft — the unbounded
clamp (a legacy marker dated far ahead expires and then migrates), dropping the fallback entirely (a
legacy marker still dates from its file), and the <code>nan</code>-only guard (an <code>at</code>
that is not a <i>finite</i> number falls back to the mtime, parametrised over <code>"yesterday"</code>,
<code>None</code>, <code>True</code>, <code>nan</code>, <code>inf</code>, <code>-inf</code> and
<code>10**400</code> — in Python a bool <i>is</i> an int, and each of the last three fails a
different way).
