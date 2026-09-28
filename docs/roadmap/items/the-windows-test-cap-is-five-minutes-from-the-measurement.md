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
note: Two windows-3.14 jobs were killed at 30.4 and 30.3 min in one morning — both while pytest was still printing results, and the second one blocked a release.
---
<b>Found by watching the train release land, then again on main 82 minutes
later.</b> Every check on <code>release/train-2026-09-28</code> was green except
<code>tests (windows-latest, 3.14)</code>, which came back <code>cancelled</code>
after 30.4 minutes (run <code>36399947619</code>, job <code>108855169521</code>).
The log distinguishes a slow job from a wedged one, and this was slow: pytest's
last complete progress row lands at <code>09:22:22.18</code> at <code>99%</code>,
a partial row of eleven more results at <code>09:22:29.19</code>, and
<code>##[error]The operation was canceled</code> at <code>09:22:29.24</code>.
Eleven tests finished in the final seven seconds — the suite was still moving when
the cap fired.
<br><br>
<b>Then the merge commit did it again.</b> Run <code>36408455593</code> on
<code>008c5d41</code>, job <code>108882688603</code>: same cell, cancelled at 30.3
minutes, last full row <code>99%</code> at <code>10:43:27.71</code>, thirty-three
more results at <code>10:44:06.94</code>, cancelled 46 ms later. Two independent
samples, same shape, both still at work — and because <code>publish.yml</code>
triggers on <code>workflow_run</code> of a <i>completed, successful</i>
<code>ci</code>, the second one held the release back until the job was re-run by
hand. That is the cost of the flake stated precisely: not a red square, a blocked
publish.
<br><br>
<b>One cap, three very different machines.</b> The <code>tests</code> job sets
<code>timeout-minutes: 30</code> for all nine matrix cells. Over the last 40
<code>ci</code> runs (every attempt, not just the latest), the successful jobs
measure:
<br><br>
<code>ubuntu&nbsp;3.14&nbsp;4.0&nbsp;min · ubuntu&nbsp;3.13&nbsp;5.4 ·
ubuntu&nbsp;3.12&nbsp;5.8 · macos&nbsp;3.14&nbsp;7.4 · macos&nbsp;3.13&nbsp;7.5 ·
macos&nbsp;3.12&nbsp;8.8 · windows&nbsp;3.12&nbsp;19.3 ·
windows&nbsp;3.14&nbsp;19.4 · windows&nbsp;3.13&nbsp;20.7</code> (medians)
<br><br>
A median is the wrong number to size a timeout against, though, so the cap has to
be read against the <i>slowest run of each OS that still passed</i>: ubuntu 7.9,
macOS 10.3, Windows 24.6. That is 22.1 minutes of headroom for Linux, 19.7 for
macOS — and 5.4 for Windows. A Windows runner 1.25x slower than the worst one yet
measured is a red required check on a tree that is fine, which is exactly what
happened twice: 2 timeouts in 36 completed windows-3.14 attempts, both today.
(The other cancellations in that sample are concurrency-group cancels — none ran
longer than 13 minutes.)
<br><br>
<b>Fixed by giving Windows its own cap</b>, not by widening all nine:
<code>timeout-minutes: ${{ startsWith(matrix.os, 'windows') &amp;&amp; 45 || 30 }}</code>.
45 is 1.8x the slowest Windows run that ever <i>passed</i> (24.6 min) and about
1.5x the two that were killed, and the six Linux/macOS cells keep the
tight cap that is the point of having one — a genuinely hung Linux job still dies
in 30 minutes rather than 45. It is <code>startsWith</code> rather than
<code>== 'windows-latest'</code> because the condition and the <code>os:</code>
list are otherwise related only by spelling: pin that list to a dated label such
as <code>windows-2025</code> and the equality matches nothing, handing all nine
cells 30 again without failing anything.
<br><br>
<b>The gate that should have caught the value did not read it.</b>
<code>test_workflow_timeouts</code> caps every job's <code>timeout-minutes</code>
at 90 via <code>^&nbsp;&nbsp;&nbsp;&nbsp;timeout-minutes: (\d+)\s*$</code> — four
spaces of indent and a line that ends at the digits, so it skips any line it
cannot match, and the repo's single cap over the bound
(<code>shards.yml</code>/<code>build</code>, 330, with a trailing comment) was the
one the bound never saw. It now parses the branch operands of the expression form
structurally, refuses aloud any shape it was not taught, and evaluates the
condition against the job's real <code>os:</code> list, so a cap that has stopped
applying to any cell fails the test instead of passing it.
<br><br>
Two sibling holes closed with it. The companion
<code>test_every_job_declares_a_timeout</code> asked only whether the string
<code>timeout-minutes:</code> appeared anywhere in the job — which a
<i>step</i>-level cap satisfies at eight spaces of indent, so a job with no
job-level cap at all passed both guards. Both now ask the same question. And the
carve-out for an expression with no digits in it (<code>${{ inputs.cap }}</code>,
whose number genuinely lives elsewhere) was wide enough to swallow
<code>${{ cond &amp;&amp; vars.WIN_CAP || vars.CAP }}</code> — digit-free, but a
two-branch decision this file can see the shape of. It is now narrowed to a bare
context reference, and anything else raises.
