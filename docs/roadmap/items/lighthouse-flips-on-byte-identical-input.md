---
id: lighthouse-flips-on-byte-identical-input
board: code
section: docsite
status: planned
category: CI · Bug
complexity: M
impact: High
wow: 4
note: the same roadmap.html scored 0.78 and passed, then 0.78 and failed — the gate now decides on runner noise
order: 314
owner:
pr:
title: The performance gate flips on byte-identical input
---
<code>lighthouse</code> asserts <code>categories.performance &ge; 0.80</code> on
<code>docs/roadmap.html</code>. That page now scores <b>0.76&ndash;0.78</b>, so the
assertion is decided by whichever way runner timing falls, not by the page. <b>Two commits
on one branch, whose <code>docs/roadmap.html</code> is byte-identical
(<code>sha256 42bdc4f7&hellip;</code>, 784,560&nbsp;bytes both), got opposite verdicts</b>
&mdash; <code>c75f4a9f</code> failed, <code>037a2468</code> passed, 60 seconds apart. The
same oscillation is visible on other branches in the run history:
<code>loop/missing-json</code> failed at <code>2a5231cb</code> and passed at
<code>1c949b7d</code>; <code>loop/audit-retrieval-search-onboarding</code> failed twice
then passed.

Three earlier cards closed real findings here &mdash;
<code>lighthouse-ci-on-the-pages-site</code> installed the budgets,
<code>lighthouse-scored-a-page-nobody-is-served</code> fixed a harness sending 3.27x the
bytes Pages sends, and <code>roadmap-page-weight-grows-without-bound</code> found it was
<em>never the bytes</em> but 705&nbsp;ms of <code>styleLayout</code>, and bought headroom
by letting 55.5% of elements skip it. That headroom has since been spent: the board was
407.6&nbsp;KB when that card was written and is <b>787&nbsp;KB</b> now. So this is not a
re-file of any of them &mdash; it is what happens after their fix, and the symptom is
different in kind: a gate that cannot decide rather than a page that is slow.

Why it matters more than two hundredths of a score: a check that fails on input it just
passed is a check people learn to re-run rather than read, and the next real regression
arrives looking exactly like the last false one. <code>lighthouse</code> is advisory, not
required, which is what has let it drift this far unnoticed. Fix &mdash; decide which
guarantee is wanted, then make the gate express it: assert the median of the three runs
rather than the worst, or floor at a value the page actually clears and put a separate
bound on the growth that is eating the margin, so the number that moves is the one being
regressed. Lowering the floor alone just relocates the coin flip.
