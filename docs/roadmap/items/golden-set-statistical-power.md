---
id: golden-set-statistical-power
board: code
section: health
status: inflight
category: Quality · Retrieval eval
complexity: M
impact: High
wow: 4
note: 43 → deeper, per-kind
order: 4
owner: loop/goldenset
pr:
title: Grow &amp; diversify the golden set for statistical power
---
The golden set (<b>43</b> queries / 8 stacks / 7 skills) is small enough that
engine comparisons don't yet reach significance — the paired t-test lands at
<code>p≈0.11–0.26</code> on the pinned corpus, so BM25's numeric lead over the
heuristic can't be called statistically real. Expand and diversify it: many more
labelled queries with balanced per-kind coverage (skill / rule / workflow),
harder near-miss distractors, and judgments for the still-unevaluated surfaces
(<code>search --smart</code>, <code>detect_stack</code>). Tighter confidence
intervals mean comparisons that actually reach significance and a gate that
catches subtler regressions. The single highest-leverage extension of the eval
harness.
