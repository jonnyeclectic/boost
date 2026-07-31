---
id: near-duplicate-items-eat-the-result-slots
board: code
section: pipeline
status: planned
category: Search · Ranking
complexity: M
impact: High
wow: 4
note: 56.3% of entries share a name
order: 71
owner:
pr:
title: Near-duplicate items consume the top-10, and it gets worse with every tap
---
Measured on a real 83-tap install: 11,147 catalog entries carry only 6,997
unique names — <b>1.593 copies per name, and 56.3% of entries share a name with
another entry</b>. <code>rule</code> appears in 47 taps, <code>code-reviewer</code>
in 18, <code>prompt-engineer</code> in 15, <code>security-auditor</code> and
<code>incident-responder</code> in 13 each. Roughly 18% of bodies are
byte-identical, in clusters of up to 8. Because <code>rag.retrieve</code> keys
its <code>best</code> map on <code>(name, tap)</code> and then takes
<code>ranked[:k]</code>, N copies of one item across N registries consume N of
the ten slots a user sees.
<b>This is the ranking problem that grows with the catalog</b>, and no retrieval
engine fixes it: byte-identical bodies produce byte-identical vectors, so a dense
reranker cannot separate them and reciprocal-rank fusion actively reinforces the
agreement. Adding distractor taps was measured driving base
<code>recall@10</code> <em>down</em> 0.902 → 0.872. Dedup is model-free, needs no
download and no new dependency, and its benefit scales up as the corpus grows
rather than washing out.
Two things to get right. First, cluster on content hash (or canonical name)
rather than name alone, and pick a winner with a quality prior — source trust,
stars, recency, maintenance — so the surviving copy is the one worth installing;
<code>core/typosquat.py</code> already has confusion machinery to build on.
Second, <b><code>(tap, name)</code> is not a unique key</b>: it collides on 1,557
of 11,147 entries (14.0%), worst case <code>('survivorforge/cursor-rules',
'rule')</code> ×47. Anything keyed on it — a cache, a shipped artifact, a lock
row — silently binds data to the wrong entry. Use <code>(tap, skill_md)</code>,
which is 11,147/11,147 distinct.
