---
id: eval-corpus-pins-have-no-refresh-path
board: code
section: internals
status: shipped
category: Eval · Correctness
complexity: S
impact: Medium
wow: 3
note: the corpus is now frozen at one August 2026 snapshot, and nothing will ever move it
order: 85
owner: loop/eval-corpus-refresh
pr: 431
title: Nothing refreshes the eval corpus pins, so the gate measures one frozen day
---
<b>Pinning traded one problem for its opposite, and the trade should be recorded rather than
discovered.</b> Before, <code>taps.txt</code> named twenty repositories and the gate measured
whatever they held that morning &mdash; reproducible only by luck. Now every row carries a SHA, so
the gate measures exactly one snapshot: <b>2026-08-01</b>. That is the point. The cost is that
nothing will ever move it &mdash; no scheduled job, no reminder, no check that notices the pins
ageing.

<b>Why that matters.</b> The gate asks &ldquo;does the right skill come back for a real
question&rdquo;, and skills are written by other people continuously; the corpus grew by thousands of
entries in the months before it was pinned. A frozen corpus answers that question about a world that
no longer exists, and answers it with total confidence because every number reproduces. Reproducible
and representative are different properties, and this change bought the first with the second.

<b>The precedent is in the repo.</b> <code>lock-refresh.yml</code> solves the same shape for the
hash-pinned toolchain: a monthly job re-resolves and opens a PR a human reviews. Here that would
re-resolve each row to current upstream HEAD and regenerate <code>baseline.json</code>, and the diff
would be a direct measurement of how retrieval quality tracks a changing catalogue &mdash; which
nothing currently reports, and is arguably worth more than the refresh.

<b>Why it is not a copy-paste.</b> A refreshed corpus moves the gate's numbers, and they move the
wrong way as it grows &mdash; [[eval-corpus-is-96x-smaller-than-a-real-install]] measures all four
floors failing at 7&times; the size. So the job can propose a corpus that turns a required gate red
through no fault of any change here, and its PR has to make that legible rather than look routine. It
also compounds with [[eval-corpus-is-one-strangers-repo]]: re-resolving is exactly when a vanished
repository gets discovered, which is the feature or the outage depending on how it reports.

<b>Provenance.</b> The direct consequence of [[eval-corpus-was-not-actually-pinned]], whose stated
limits call this cost intended. It is intended, and it is also unassigned.

<b>What shipped.</b> <code>scripts/eval_corpus.py --refresh</code> moves every row to current
upstream HEAD, re-measures its entry count, and rewrites <code>taps.txt</code>;
<code>.github/workflows/eval-corpus-refresh.yml</code> runs it monthly and opens a PR, the same
shape <code>lock-refresh.yml</code> uses for the toolchain. The refresh deliberately does
<em>not</em> run the eval: moving the corpus and judging what the move did are different
decisions, and one step that did both would be making the second one silently.

<b>The PR body is the deliverable, not the SHA diff.</b> The job scores the refreshed corpus in
its own <code>continue-on-error</code> step and leads the body with the verdict, because the
numbers can legitimately go down &mdash; [[eval-corpus-is-96x-smaller-than-a-real-install]]
measures all four floors failing at 7&times; the size &mdash; so a refresh can turn a required
gate red through no fault of any change in the diff. A failing job would surface that to nobody,
so the failure has to arrive as a PR that says, in a warning block, that this is the measurement
rather than a defect to fix by editing the diff. A test pins the refresh job to the <em>same
four floors</em> the required gate uses, since a drifted floor would make that banner
confidently wrong in either direction.

<b>First run, measured rather than predicted.</b> Against the corpus pinned one day earlier:
<b>4 of 20</b> repositories had moved, the corpus went <b>10,152 &rarr; 10,162</b> entries
(<code>+10</code>, all in the repo that is already 62% of it), and the gate scored
<code>0.852 / 0.473 / 0.605 / 0.657</code> &mdash; <b>identical to three decimals</b>, all four
floors PASS. That is one day of drift, so it is a demonstration that the path works rather than
evidence about how fast the corpus ages; the point of the monthly cadence is that nothing else
in this repository reports that number at all.

<b>The vanished-repo case is handled by the same run.</b> A refresh is the only thing that ever
asks whether those twenty repositories still exist. <code>--refresh</code> exits <b>75</b>
(EX_TEMPFAIL) naming the repo, so the scheduled job failing with &ldquo;X is gone&rdquo; is the
intended discovery signal &mdash; and, unlike the old failure mode described in
[[eval-corpus-is-one-strangers-repo]], it blocks no pull request.

<b>One thing found while building it.</b> The job was called <code>refresh</code>, which collides
with <code>lock-refresh.yml</code>'s job of the same name. GitHub keys required checks on the
name alone, so that is an ambiguity a check can never be required through &mdash;
<code>scripts/check_required_checks.py</code> caught it locally.
