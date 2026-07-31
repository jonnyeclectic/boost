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
owner: loop/content-hash-dedup
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

<b>The curve this card asked for.</b> The note above measured 0 duplicate slots over the pinned
6-tap corpus and said, correctly, that absence at 6 taps says nothing about 83. Re-measured over 77
tapped registries sampled across the shipped list, with the same 50 natural-language queries,
counting how many of the ten slots a user sees are second-or-later copies of a name already in that
same result list:

<code>6 taps</code>: 1,122 entries, 0.0% sharing a name, <b>0.00</b> duplicate slots/query &middot;
<code>12</code>: 14,194 entries, 77.8%, <b>4.28</b> &middot;
<code>25</code>: 16,633, 77.9%, 4.12 &middot;
<code>40</code>: 17,470, 74.7%, 3.88 &middot;
<code>60</code>: 29,137, 83.9%, 5.08 &middot;
<code>77</code>: 29,938 entries, 82.7% sharing a name, <b>4.94</b> duplicate slots/query.

So at realistic corpus size <b>roughly half the ten slots a user sees are repeat copies of a name
already in the list</b>, worst observed 9 of 10 (&ldquo;our full-text queries have got slow as the
index grew&rdquo;). The card's thesis holds, and more sharply than its own 56.3% figure suggested.

<b>But the driver is not tap count.</b> Entries jump 1,122 &rarr; 14,194 between 6 and 12 taps, so
the sample is not uniform: a single awesome-list-style rule registry contributes more entries than
the entire 6-tap eval corpus. Duplicate pressure is a step function of <em>which</em> registries are
tapped, not a smooth function of how many &mdash; it appears the moment one duplicate-heavy registry
is added and then stays flat at ~4-5 slots per query from 12 taps to 77. Any dedup benefit should be
reported against a stated tap set for that reason, and a user who taps only curated skill registries
may never see the problem at all.

<b>What this does not settle.</b> The measurement counts repeated <em>names</em>, which is the
symptom the card names, not content-identical bodies &mdash; two rules that share a name and
genuinely differ (the <code>admin-interface-rule</code> pair fixed in <code>#366</code>) are counted
here as duplicate slots but must <em>not</em> be merged. That is precisely why the card asks for
clustering on content hash rather than on name, and this curve is an upper bound on what dedup could
reclaim, not a target.

<b>Shipped: content-hash dedup, measured 4.94 &rarr; 0.60 duplicate slots per query</b> over the
77-tap corpus (worst case 9 of 10 &rarr; 4). The residual 0.60 is correct rather than leftover: those
are entries sharing a <em>name</em> whose bodies genuinely differ, which must stay separate.

Two measurements settled the design the card left open (&ldquo;content hash <em>or</em> canonical
name&rdquo;). Of 29,938 entries, <b>78.3% are byte-identical duplicates</b> &mdash; 14,153 distinct
bodies, largest cluster <b>40 copies</b> &mdash; while 82.7% share a name. That ~4.4% gap is real
distinct content, so name clustering would merge exactly the pairs <code>#366</code> proved must not
be merged. And clustering on content cannot make the opposite mistake here: the number of content
clusters spanning more than one name is <b>0</b>, so collapsing by body never merges two
differently-named items. Content hashing is strictly the safer of the two options the card offered,
which was not obvious before measuring.

The quality prior is <code>curated</code>: inside a cluster every copy is byte-identical, so the one
worth surfacing is the one from a tap the user marked trusted. The cluster keeps its best score when
that swap happens, so promoting the trusted copy never demotes the result.

Mechanically, the body hash is computed in <code>_make_docs</code> where the body is already read
&mdash; doing it at query time would mean re-reading ~30k files to answer one search &mdash; and
persisted per document (<code>INDEX_VERSION</code> 4 &rarr; 5). Dense hits carry no hash of their own
and do not need a second schema: <code>content_hashes()</code> serves one map to every engine from
the BM25 index, so the engines can never disagree about which copies are identical. Dedup runs inside
<code>retrieve</code> <em>and</em> at the <code>retrieve_any</code> seam, because fusion can
reintroduce a copy BM25 already dropped &mdash; the copies are distinct <code>(tap, path)</code>
keys, so RRF has no reason to treat them as one. Collapsing happens before <code>k</code> is applied,
or the duplicates would still consume the slots they were removed from.

Cost on the pinned eval corpus: <b>none</b> &mdash; 0.978 / 0.791 / 0.854 / 0.882, identical to
before, all four floors passing. That corpus has little content duplication, which is exactly why the
83-tap measurement had to exist.

<b>Still open:</b> a richer quality prior than <code>curated</code> (the card names stars, recency,
maintenance; only <code>curated</code> is available on an entry today), and
<code>core/typosquat.py</code>'s confusion machinery for near-identical rather than byte-identical
bodies. Both are refinements &mdash; the byte-identical case is 78.3% of the problem.
