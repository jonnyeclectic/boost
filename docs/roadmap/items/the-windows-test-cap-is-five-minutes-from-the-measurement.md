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
title: One 30-minute cap for nine matrix cells, and only Windows is anywhere near it
note: A release train's windows-3.14 job was killed at 30.4 min while pytest was still printing results — 5.4 minutes of headroom against the worst run that ever passed.
---
<b>Found by watching the train release land.</b> Every check on
<code>release/train-2026-09-28</code> was green except <code>tests (windows-latest,
3.14)</code>, which came back <code>cancelled</code> after 30.4 minutes (run
<code>36399947619</code>, job <code>108855169521</code>). The log distinguishes a
slow job from a wedged one, and this was slow: pytest's last complete progress row
lands at <code>09:22:22.18</code> at <code>99%</code>, a partial row of eleven more
results at <code>09:22:29.19</code>, and
<code>##[error]The operation was canceled</code> at <code>09:22:29.24</code>. Eleven
tests finished in the final seven seconds — the suite was still moving when the cap
fired.
<br><br>
<b>One cap, three very different machines.</b> The <code>tests</code> job sets
<code>timeout-minutes: 30</code> for all nine matrix cells. Over the last 40
<code>ci</code> runs (every attempt, not just the latest), the successful jobs
measure:
<br><br>
<code>ubuntu&nbsp;3.14&nbsp;3.9&nbsp;min · ubuntu&nbsp;3.13&nbsp;5.3 ·
ubuntu&nbsp;3.12&nbsp;5.7 · macos&nbsp;3.14&nbsp;7.4 · macos&nbsp;3.13&nbsp;7.5 ·
macos&nbsp;3.12&nbsp;8.2 · windows&nbsp;3.14&nbsp;18.8 ·
windows&nbsp;3.12&nbsp;19.1 · windows&nbsp;3.13&nbsp;20.5</code> (medians)
<br><br>
A median is the wrong number to size a timeout against, though, so the cap has to
be read against the <i>slowest run of each OS that still passed</i>: ubuntu 7.9,
macOS 10.3, Windows 24.6. That is 22.1 minutes of headroom for Linux, 19.7 for
macOS — and 5.4 for Windows. A Windows runner 1.25x slower than the worst one yet
measured is a red required check on a tree that is fine, which is exactly what
happened: 1 timeout in 37 windows-3.14 attempts.
<br><br>
<b>Fixed by giving Windows its own cap</b>, not by widening all nine:
<code>timeout-minutes: ${{ startsWith(matrix.os, 'windows') &amp;&amp; 45 || 30 }}</code>.
45 is 1.8x the measured Windows worst case, and the six Linux/macOS cells keep the
tight cap that is the point of having one — a genuinely hung Linux job still dies
in 30 minutes rather than 45. It is <code>startsWith</code> rather than
<code>== 'windows-latest'</code> because GitHub is migrating that label to
<code>windows-2025</code>, and an equality test that silently stops matching hands
every cell 30 again without failing anything.
<br><br>
<b>The gate that should have caught the value did not read it.</b>
<code>test_workflow_timeouts</code> floors every job's <code>timeout-minutes</code>
at 90 via <code>^ timeout-minutes: (\d+)\s*$</code> — an anchor that skips any line
it cannot match, so the repo's single cap over the bound
(<code>shards.yml</code>/<code>build</code>, 330, with a trailing comment) was the
one the bound never saw. It now parses the branch operands of the expression form
structurally, refuses aloud any shape it was not taught, and evaluates the
condition against the job's real <code>os:</code> list, so a cap that has stopped
applying to any cell fails the test instead of passing it.
