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
<b>A scale bound, and one claim checked.</b> This card holds that reciprocal-rank fusion
"actively reinforces the agreement" between duplicate copies. That is a claim about
<code>rag.rrf_fuse</code> as shipped in <code>#360</code>, so it was worth measuring rather than
assuming. Over the <em>pinned 6-tap eval corpus</em> &mdash; 743 entries, 693 unique names, so
<b>12.7%</b> of entries share a name against the 56.3% measured on the 83-tap install &mdash; and
the 50 natural-language queries in <code>tests/eval/golden-natural.jsonl</code>: repeated-name slots
consumed in the top-10 were <b>0 for BM25, 0 for dense and 0 for hybrid</b>. Querying <em>directly</em>
at a duplicated item (<code>code-reviewer</code> appears in 3 taps here, <code>judge</code> and
<code>guidelines</code> in 2) returned exactly <b>one</b> copy in the top-10 under all three engines.

So at this scale fusion is <b>neutral</b>, not amplifying &mdash; it consumes no more duplicate slots
than either engine alone. That does not contradict this card: absence at 6 taps says nothing about
83, where <code>rule</code> spans 47 registries and 18% of bodies are byte-identical. What it adds
is a lower bound and a mechanism note. Duplicates survive fusion because
<code>rrf_fuse</code> keys on <code>(name, tap)</code>, exactly as <code>rag.retrieve</code> already
does, so copies in different taps remain distinct keys under every engine; fusion neither merges nor
multiplies them. If the amplification appears at 83 taps it will be because both engines
<em>rank</em> the copies adjacently, not because fusion treats them specially &mdash; which points
the fix at deduplication before ranking rather than at the fusion rule.

Worth re-measuring on the 83-tap install with the same script (<code>rrf_fuse</code> is public) to
turn this bound into a curve.

