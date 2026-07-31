---
id: near-duplicate-items-eat-the-result-slots
board: code
section: pipeline
status: inflight
category: Search · Ranking
complexity: M
impact: High
wow: 4
note: 56.3% of entries share a name
order: 71
owner: loop/entry-key-collision
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


<b>The key half is shipped; the ranking half is not.</b> This card names two things to get right,
and the second &mdash; <code>(tap, name)</code> is not a unique key &mdash; turned out to be a
correctness bug rather than a ranking one, so it was fixed first and separately.

Both engines built <code>live = {(name, tap): entry}</code> as a dict comprehension, so the last
entry silently won. Reproduced on the pinned 6-tap corpus: 743 entries collapse to 694 pairs, leaving
<b>49 entries (6.6%) unreachable</b> &mdash; the card's 14.0% at 83 taps, at small scale. It is not
only that a copy is hidden: a query matching a shadowed entry's <em>body</em> was reported under the
surviving entry's name, description and path. The clearest pair, same tap and same name, is two
genuinely different rules:
<code>docs/rules/backend/nodejs/express-mongodb/admin-interface-rule.mdc</code> and
<code>docs/rules/backend/nodejs/fullstack-mern-guide/admin-interface-rule.mdc</code>.

<code>rag.entry_key</code> is now the single identity function shared by BM25, dense and RRF, keyed
on <code>(tap, skill_md)</code> &mdash; 743/743 distinct here and 11,147/11,147 on the 83-tap
install, exactly as this card predicted. Both index versions are bumped, and <code>dense.build</code>
now wipes on a version change: it compared only provider/model/dim, and since
<code>_ensure_schema</code> uses <code>CREATE TABLE IF NOT EXISTS</code> an existing store would have
crashed on the first insert with &ldquo;no column named path&rdquo;.

Measured cost: <b>none</b>. Over the pinned corpus BM25 scores 1.000 / 0.780 / 0.860 / 0.895 both
before and after, so recovering 49 entries did not disturb ranking. Several fixtures were modelling
data a real catalog cannot produce &mdash; every entry sharing <code>skill_md="s"</code>, two skills
at one path &mdash; and were corrected.

<b>Still open:</b> the ranking half. Clustering on content hash, picking a winner with a quality
prior, and the 83-tap re-measurement of the fusion bound are all untouched. Note the two are
independent: dedup <em>merges</em> copies that are genuinely the same, whereas this fix stops copies
that were never the same from being merged by accident.
