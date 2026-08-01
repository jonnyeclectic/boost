---
id: roadmap-perf-budget-has-no-local-guard
board: code
section: internals
status: planned
category: Docs · Tooling
complexity: S
impact: Medium
wow: 3
note: adding two cards failed the Lighthouse budget twice, and nothing local warns before CI does
order: 86
owner:
pr:
title: Adding a roadmap card can fail a CI budget nothing local checks
---
<b>Writing two roadmap cards failed the Lighthouse performance budget, twice in a row.</b> Not
flakily &mdash; the job asserts <code>minScore 0.85</code> on the median of three runs, it passes
consistently on <code>main</code>, and a deliberate re-run of the failure reproduced it. The page had
grown by <b>9.7 KB and 86 tags, about 1.2%</b>. That is the whole margin: the board sits close enough
to its own floor that ordinary authoring breaches it.

<b>Every roadmap script reported clean first.</b> <code>build_roadmap.py --check</code>,
<code>a11y_check.py</code>, <code>check_anchors.py</code> and
<code>tests/unit/test_roadmap_fresh.py</code> all pass on a page that fails CI, because none of them
knows anything about layout cost. The signal arrives minutes later from a different workflow, and
because <code>lighthouse</code> is not a required check it is also easy to merge past &mdash; the
worst combination: too late to be useful, too quiet to be enforced.

<b>The mechanism is understood, which is what makes a local check feasible.</b> Card bodies inside a
closed <code>&lt;details&gt;</code> still ship and stay greppable but are never laid out or painted,
so the cost is the body text of <em>expanded</em> cards. That is directly countable from the item
files: on the tree that failed, seven cards contributed 38,831 characters of laid-out body.
Collapsing <code>declined</code> alongside <code>shipped</code> &mdash; a decline is a finished
investigation with a long write-up, the same cost shape &mdash; cut it to 20,227, <b>33% below
<code>main</code></b> while still adding two cards. So a budget assertion over that number would
have caught this before the push, in milliseconds, with no browser.

<b>What to decide.</b> Where the budget goes (a character or element ceiling, and at what value), and
whether it belongs in <code>a11y_check.py</code>, <code>perf_gate.py</code>, or
<code>build_roadmap.py --check</code> as a refusal like the block-element rule already added there.
Also worth settling whether <code>lighthouse</code> should be required, given it currently guards a
budget that the tree can silently violate.

<b>Provenance.</b> Hit while filing [[eval-corpus-is-one-strangers-repo]] and
[[eval-corpus-pins-have-no-refresh-path]]. The layout diagnosis it builds on is
[[roadmap-page-weight-grows-without-bound]] &mdash; <code>styleLayout</code> 705 ms and paint 393 ms
against 20 ms of script, which is why element count rather than transfer size is the thing to budget.
