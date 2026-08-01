---
id: eval-corpus-pins-have-no-refresh-path
board: code
section: internals
status: planned
category: Eval · Correctness
complexity: S
impact: Medium
wow: 3
note: the corpus is now frozen at one August 2026 snapshot, and nothing will ever move it
order: 85
owner:
pr:
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
