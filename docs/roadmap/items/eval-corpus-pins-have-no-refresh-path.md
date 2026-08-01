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
<b>Pinning the corpus traded one problem for its opposite, and the trade should be recorded rather
than discovered.</b> Before, <code>tests/eval/taps.txt</code> named twenty repositories and the gate
measured whatever they contained that morning &mdash; reproducible only by luck. Now every row
carries a commit SHA, so the gate measures exactly one snapshot: <b>2026-08-01</b>. That is the
point. The cost is that <em>nothing will ever move it</em>. There is no scheduled job, no reminder,
and no check that notices the pins ageing, so the default outcome is a corpus that is
indefinitely old while the ecosystem it is supposed to represent moves on.

<b>Why this is worth a card rather than a shrug.</b> The gate's job is to answer &ldquo;does the
right skill come back for a real question&rdquo;. Skills are written by other people, continuously
&mdash; the corpus grew by thousands of entries in the months before it was pinned. A frozen corpus
answers that question about a world that no longer exists, and does it with total confidence,
because every number is perfectly reproducible. Reproducible and representative are different
properties and this change bought the first with the second.

<b>The precedent already exists in this repo.</b> <code>lock-refresh.yml</code> solves the same
shape of problem for the hash-pinned toolchain: pins that must not drift on their own, but must not
rot either, so a monthly job re-resolves them and opens a pull request a human reviews. The same
shape fits here &mdash; re-resolve each row to its current upstream HEAD, regenerate
<code>tests/eval/baseline.json</code>, and open a PR whose diff is exactly &ldquo;here is what
moving the corpus does to the numbers&rdquo;. That diff is arguably more valuable than the refresh:
it is a direct measurement of how retrieval quality tracks a changing catalogue, which nothing
currently reports.

<b>What makes it not a copy-paste of that workflow.</b> A refreshed corpus changes the gate's
numbers, and the floors sit close enough to matter &mdash; measured 0.852 against a 0.78 floor, and
the numbers move the wrong way as the corpus grows, which
[[eval-corpus-is-96x-smaller-than-a-real-install]] measures as all four floors failing at 7&times;
the size. So an automated refresh can propose a corpus that turns the required gate red through no
fault of any change in this repository, and the PR has to make that legible instead of looking like
a routine bump. It also compounds with
[[eval-corpus-is-one-strangers-repo]]: re-resolving pins is exactly when a repository that has
disappeared upstream gets discovered, which is either the feature or the outage depending on how the
job reports it.

<b>Provenance.</b> The direct consequence of [[eval-corpus-was-not-actually-pinned]], noted while
writing it: that card's &ldquo;stated limits&rdquo; says moving a pin is now a deliberate edit and
calls the cost intended. It is intended, and it is also a thing nobody has been assigned.
