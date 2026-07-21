---
id: ranx-significance-monitor
board: code
section: health
status: planned
category: Quality · Retrieval eval
complexity: S
impact: Med
wow: 3
note: p-value, not point delta
order: 5
owner:
pr:
title: Significance-tracked engine comparison (ranx monitor)
---
Tier 1b (the <code>ranx</code> paired t-test, <code>--stats</code>) only runs on
demand today. Wire it into a scheduled CI monitor — like the
<code>eval-explain</code> workflow — that tracks whether BM25's lead over the
heuristic, and any new engine's lead over BM25, is <em>statistically
significant</em> rather than merely numerically higher, and flags when a change
erases a previously-significant win. Stays out of the required stdlib gate (ranx
is an opt-in <code>[eval]</code> dependency); it's a non-blocking monitor, so a
noisy p-value can never block a merge. Turns "recall went up 0.02" into "the
improvement is real (or isn't)."
