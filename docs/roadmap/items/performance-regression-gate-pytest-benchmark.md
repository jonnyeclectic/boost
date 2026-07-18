---
id: performance-regression-gate-pytest-benchmark
board: code
section: dx
status: planned
category: Testing · Perf
complexity: M
impact: Med
wow: 3
note: scan &amp; registry
order: 6
owner:
pr:
title: Performance-regression gate — <code>pytest-benchmark</code>
---
Benchmark the hot paths — a catalog scan over a large skills tree, a
           registry load — and fail the build when a change regresses them past a
           threshold. Catches the <em>performance</em> bugs a correctness suite
           waves through: the O(n²) that only bites at scale.
