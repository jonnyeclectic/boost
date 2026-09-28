---
id: the-windows-test-cap-is-five-minutes-from-the-measurement
board: code
section: internals
status: shipped
owner: loop/windows-test-timeout
pr: "986"
category: CI · Flake
complexity: S
impact: Medium
wow: 2
order: 352
title: The tests job caps every OS at 30 minutes, and Windows spends 25 of them
note: The release train's windows-3.14 job was cancelled at 99% of the suite, one minute from green, with the whole train behind it.
---
<b>Found by watching the train release land.</b> Every check on
<code>release/train-2026-09-28</code> was green except <code>tests (windows-latest,
3.14)</code>, which came back <code>cancelled</code> after 30.4 minutes. The job log
says what that was: the last line pytest printed before
<code>##[error]The operation was canceled</code> is a partial
<code>99%</code> row. It was not hung and it was not failing — it ran out of wall
clock about a minute from finishing, and a blocked release train waited on a
re-run for it.
<br><br>
<b>One cap, three very different machines.</b> The <code>tests</code> job sets
<code>timeout-minutes: 30</code> for all nine matrix cells. Over the last 40
<code>ci</code> runs (every attempt, not just the latest), the successful jobs
measure:
<br><br>
<code>ubuntu&nbsp;3.14&nbsp;3.9&nbsp;min · ubuntu&nbsp;3.13&nbsp;5.3 ·
ubuntu&nbsp;3.12&nbsp;5.7 · macos&nbsp;3.14&nbsp;7.4 · macos&nbsp;3.13&nbsp;7.5 ·
macos&nbsp;3.12&nbsp;8.1 · windows&nbsp;3.14&nbsp;18.4 ·
windows&nbsp;3.12&nbsp;19.1 · windows&nbsp;3.13&nbsp;20.6</code> (medians)
<br><br>
So the cap is roughly eight times the Linux median and about 1.5 times the Windows
one. Counted against the <i>slowest</i> run that still passed — 24.6 minutes, on
windows 3.14 — Linux has 22 minutes of headroom and Windows has 5.4. A runner
1.25x slower than the worst one already measured is a red required check on a tree
that is fine, which is exactly what happened: 1 timeout in 36 completed
windows-3.14 jobs.
<br><br>
<b>Fixed by giving Windows its own cap</b>, not by widening all nine:
<code>timeout-minutes: ${{ matrix.os == 'windows-latest' &amp;&amp; 45 || 30 }}</code>.
45 is 1.8x the measured Windows worst case, and the six Linux/macOS cells keep the
tight cap that is the point of having one — a genuinely hung Linux job still dies
in 30 minutes rather than 45. Raising the cap is the honest fix here precisely
because the log proves the suite was still making progress; a hang would have
called for a different one, and widening the timeout would only have made it
slower to find out.
