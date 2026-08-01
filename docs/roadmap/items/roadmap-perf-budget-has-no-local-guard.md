---
id: roadmap-perf-budget-has-no-local-guard
board: code
section: docsite
status: planned
category: Docs · Performance
complexity: S
impact: Medium
wow: 3
note: adding cards failed the Lighthouse budget three times, and nothing local warns before CI does
order: 86
owner:
pr:
title: Adding a roadmap card can fail a CI budget nothing local checks
---
<b>Adding roadmap cards failed the Lighthouse performance budget three times running.</b> Not flakily
&mdash; the job asserts <code>minScore 0.85</code> on the median of three runs, passes consistently
on <code>main</code>, and scored <b>0.83, 0.83, 0.83</b> on the first attempt for a page that had
grown <b>9.7&nbsp;KB and 86 tags, about 1.2%</b>. That is the whole margin.

<b>Every roadmap script reported clean first.</b> <code>build_roadmap.py --check</code>,
<code>a11y_check.py</code>, <code>check_anchors.py</code> and <code>test_roadmap_fresh.py</code> all
pass on a page that fails CI, because none models render cost. The signal arrives minutes later from
a different workflow, and <code>lighthouse</code> is not a required check &mdash; too late to be
useful, too quiet to be enforced.

<b>One fix was tried and measured wrong.</b> Collapsing <code>declined</code> bodies into
<code>&lt;details&gt;</code> alongside <code>shipped</code> cut laid-out body text <b>33% below
main</b> and moved the score by <b>0.00</b>. So the 705&nbsp;ms-of-<code>styleLayout</code> diagnosis
behind [[roadmap-page-weight-grows-without-bound]] no longer describes this page, and that change was
reverted rather than kept on a falsified rationale. <code>content-visibility: auto</code> on
<code>.rcard</code> did help &mdash; 0.83&nbsp;&rarr;&nbsp;0.84 &mdash; and the rest had to come out
of prose.

<b>What to decide.</b> What to budget now that laid-out text is not the driver (bytes? DOM nodes?),
at what ceiling, and whether it belongs in <code>a11y_check.py</code>, <code>perf_gate.py</code>, or
<code>build_roadmap.py --check</code> as a refusal like the block-element rule already there. Also
whether <code>lighthouse</code> should be required, given it currently guards a budget the tree can
silently violate.
