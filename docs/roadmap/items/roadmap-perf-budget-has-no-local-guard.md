---
id: roadmap-perf-budget-has-no-local-guard
board: code
section: docsite
status: planned
category: Docs · Performance
complexity: S
impact: Medium
wow: 4
note: main passes this budget on run-to-run luck — its own three runs are 0.810, 0.840, 0.850
order: 86
owner:
pr:
title: The Lighthouse budget passes on noise, not on margin
---
<b>The roadmap page has not been under its performance budget. It has been winning a coin toss.</b>
Pulled from <code>main</code>'s own Lighthouse artifact, <code>roadmap.html</code> scores
<b>0.810, 0.840 and 0.850</b> across the three runs of a single job, against a
<code>minScore 0.85</code> assertion. It passes because <code>aggregationMethod: median-run</code>
selects one representative run &mdash; and on that job the selected one was the 0.850. Two of its
three runs are below the floor.

<b>This was found the hard way.</b> Adding cards to the board turned the check red at
<b>0.84, 0.84, 0.84</b> &mdash; unusually stable, reproduced by re-running the job. The obvious
reading was &ldquo;the new cards broke the budget&rdquo;, and two rounds of work followed from it:
collapsing <code>declined</code> bodies into <code>&lt;details&gt;</code>, which cut laid-out body
text <b>33% below main</b> and moved the score by <b>0.00</b>; and trimming <b>3,066 characters</b>
of card prose, which also moved it by <b>0.00</b>. Neither is a coincidence &mdash; the page's score
is simply not sensitive to a percent of content at this size. What the change actually did was make
the score <em>repeatable</em>, which removed the lucky draw the budget had been relying on.

<b>One real improvement came out of it.</b> <code>content-visibility: auto</code> on
<code>.rcard</code> moved 0.83&nbsp;&rarr;&nbsp;0.84 by skipping layout and paint for the ~195 cards
off screen, while keeping their text in the DOM for find-in-page, anchors and assistive tech. It is
kept on that measurement. The <code>&lt;details&gt;</code> collapse was reverted, because keeping a
change whose stated rationale the measurement had just falsified is worse than not making it &mdash;
the 705&nbsp;ms-<code>styleLayout</code> diagnosis behind
[[roadmap-page-weight-grows-without-bound]] no longer describes this page.

<b>Nothing local can see any of this.</b> <code>build_roadmap.py --check</code>,
<code>a11y_check.py</code>, <code>check_anchors.py</code> and <code>test_roadmap_fresh.py</code> all
pass on a page that fails CI, because none models render cost. And <code>lighthouse</code> is not a
required check, so the signal is both too late to act on and too quiet to enforce.

<b>What to decide.</b> Whether to make the assertion honest &mdash; assert the <em>worst</em> run
rather than the median, which would fail <code>main</code> today and state the real position; whether
to fix the page enough to clear 0.85 on every run; and what cheap local proxy could warn first, given
that neither laid-out text nor prose volume predicts the score. Also whether the check should be
required at all while it can be passed by resampling.
