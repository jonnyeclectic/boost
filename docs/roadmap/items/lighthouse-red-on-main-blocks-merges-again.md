---
id: lighthouse-red-on-main-blocks-merges-again
board: code
section: docsite
status: planned
category: Docs · Performance
complexity: M
impact: High
wow: 1
note: main's head fails lighthouse (roadmap.html perf 0.75/0.74/0.75 vs the 0.80 floor) — blocks merge on any PR that touches docs/roadmap.html
order: 75
owner:
pr:
title: <code>lighthouse</code> is red on <code>main</code> again — <code>roadmap.html</code> is back over its performance floor
---
<b>The required <code>lighthouse</code> check currently fails on <code>main</code>'s own head</b>
(<code>0f04b23</code>), which makes it a blocking, base-branch problem rather than something any one
PR did: <a href="https://github.com/jonnyeclectic/boost/actions/runs/34159604475">run 34159604475</a>,
triggered by the merge of #757, scored <code>docs/roadmap.html</code> performance
<b>0.75, 0.74, 0.75</b> across all three Lighthouse runs against the <code>minScore 0.80</code> floor
— found while landing #812, whose own diff only flips one card's <code>status</code>/<code>note</code>
fields and cannot plausibly move the score that much.

<b>This is the second time this exact failure shape has shipped.</b>
<a href="#roadmap-page-weight-grows-without-bound">roadmap-page-weight-grows-without-bound</a> fixed
the identical symptom once already — <code>build_roadmap.py</code> now wraps a
<code>shipped</code> card's body in a closed <code>&lt;details&gt;</code>, which at the time dropped
6,316 laid-out elements to 3,017 (55.5% skipped) and cleared the floor. That card's own diagnosis
still applies: the mechanism is <code>styleLayout</code>/<code>paintCompositeRender</code> time on a
large DOM, not transferred bytes, so <code>dom-size</code> reads 0 in the Lighthouse report but is
<em>unweighted</em> in the performance category — chasing kilobytes here is the trap that card already
named.

<b>What's different this time, for whoever picks this up:</b> the board has kept growing past the
<code>&lt;details&gt;</code> fix's headroom — every merged card still adds a
<code>&lt;summary&gt;</code> plus whatever `planned`/`inflight` (unexpandable) content it carries, and
`planned`/`next`/`inflight` cards render fully expanded by design (they're the ones a reader acts on).
Re-measure element count and the TBT/LCP/CLS breakdown the way the shipped card did (its own numbers:
TBT 0.58 × 30%, LCP 0.69 × 25%, FCP 0.47 × 10%, SI 0.93 × 10%, CLS 1.00 × 25%) before choosing a lever
— likely candidates in order of cost: collapse the (currently always-expanded) `planned`/`next`
section bodies behind <code>&lt;details&gt;</code> too, once a board reaches some card-count threshold; paginate
`planned` by category; or move the long tail of `planned` cards (432 at last count, most a single
paragraph) to a separate page linked from a summary table. Do not raise the Lighthouse floor — same
argument the shipped card made: the floor is calibrated and honest, and a page that outgrows it should
get smaller, not re-graded.

<b>Not claimed:</b> a root-cause element count or timing breakdown for the current failure — the
tapped-out reproduction from the previous card's own "not claimed" note applies again (no Chrome in a
CLI sandbox); CI's own <code>lighthouse</code> job and its uploaded artifact are the source of truth.
Filed while landing #812, which stood down on this exact failure rather than fixing it inline (out of
scope for a `boost preview` bugfix, and the fix needs re-measurement first, not a guess).
