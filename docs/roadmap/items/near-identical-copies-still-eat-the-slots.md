---
id: near-identical-copies-still-eat-the-slots
board: code
section: planned
status: inflight
owner: loop/near-duplicate-collapse
category: Search · Ranking
complexity: M
impact: High
wow: 4
note: collapse implemented and wired in (PR); the real-corpus safety bound is still unmeasured
order: 131
title: Near-identical copies survive content-hash dedup and take the whole result page
---
<a href="#near-duplicate-items-eat-the-result-slots">Content-hash dedup</a> shipped and worked:
<code>rag.dedupe_by_content</code> took duplicate result slots from <b>4.94 to 0.60 per query</b>
over a 77-tap corpus. That card closed naming one thing still open &mdash; <em>near-identical
rather than byte-identical clustering, where <code>core/typosquat.py</code>'s confusion machinery
would apply</em> &mdash; and buried it under a <code>shipped</code> status where nobody would claim
it. This card is that remainder, with a measurement that makes it look considerably worse than
&ldquo;refinement&rdquo;.

<b>Observed on a real 466-tap install</b> with hybrid RRF serving (658,131 chunks): for the query
<code>exa search</code>, every one of the top ten rows is <code>exa-search</code>, and the
descriptions are what give the
shape away &mdash; one Japanese (<code>Exa MCPによるウェブ、コード、企業調査</code>), two Chinese
(<code>通过Exa MCP进行神经搜索</code>), five English variants of <code>Neural search via Exa MCP</code>,
plus <code>Use Exa MCP for current web&hellip;</code> and <code>AI-powered web search&hellip;</code>.
All ten are <code>★ curated</code>. The footer reads
<code>51 matches &middot; ranked by hybrid RRF (BM25 + dense)</code>.

<b>Every one of those passed dedup correctly.</b> They are not byte-identical: they are the same
skill in Japanese, in Chinese, and in five English phrasings across different registries. The body
digest differs, so <code>dedupe_by_content</code> keeps them all &mdash; which is exactly the
behaviour <code>#366</code> proved must be preserved, since two entries sharing a name can be
genuinely different rules. The shipped fix is not misbehaving. It simply does not reach this shape.

<b>What the 0.60 residual actually was.</b> The prior card described its leftover as &ldquo;entries
sharing a <em>name</em> whose bodies genuinely differ, which must stay separate&rdquo; &mdash; true
as stated, and it reads as a rounding error. At 466 taps the same residual is a full result page.
The gap between 0.60 and 10.0 is worth understanding before designing anything: the 77-tap
measurement used 50 natural-language queries averaged, and an <em>average</em> hides the shape here.
Duplicate pressure was already known to be a step function of <em>which</em> registries are tapped
rather than how many; near-identical pressure looks like a step function of <b>which query</b> &mdash;
harmless across a query set, total on any query that lands on a widely-mirrored skill. Re-measure
per-query maxima, not means.

<b>The hard part is the safety proof, not the clustering.</b> Content hashing was adoptable because
one count settled it: of 14,153 distinct bodies, clusters spanning more than one name numbered
<b>zero</b>, so collapsing could not merge two different skills. Near-identical clustering has no
such free proof &mdash; any similarity threshold loose enough to merge a Japanese translation with
its English original is loose enough to merge two genuinely different skills that share boilerplate.
Establish the equivalent bound first (over a real corpus, at the chosen threshold, count clusters
spanning more than one <em>meaning</em>) or the fix trades a visible problem for a silent one.

<b>Three things to get right.</b> <em>Translations are the motivating case and the hardest</em>: they
share almost no tokens with the original, so token-overlap similarity will not find them while an
embedding will &mdash; and the vectors are already on disk, which makes this cheaper here than it
would be anywhere else. <em>Collapse before <code>k</code></em>, and at both the
<code>retrieve</code> and <code>retrieve_any</code> seams, for the reason the shipped dedup already
documents: fusion reintroduces copies either engine dropped, because the copies are distinct
<code>(tap, skill_md)</code> keys and RRF has no reason to treat them as one. <em>The existing
quality prior carries over unchanged</em> &mdash; <code>rag.source_rank</code> orders on the user's
<code>curated</code> flag first and shipped <code>confidence</code> second, and choosing among
near-identical copies is the same question as choosing among identical ones: where should the user
install from.

<b>Not to be confused with <code>#629</code></b>, which deduplicated vector <em>storage</em> (one
row per distinct embedding, 39.7% repeats reclaimed). That is a disk-size fix beneath the index and
changes no ranking; this is about which rows reach the user's screen.

<b>2026-08-31, in flight.</b> <code>dense.collapse_near_duplicates</code> implements the clustering:
it compares each surviving hit's chunk-0 embedding &mdash; the vector already on disk for
<code>name + description + opening of body</code>, per the &ldquo;vectors are already on disk&rdquo;
point above &mdash; against a conservative <code>NEAR_DUP_THRESHOLD = 0.96</code>, and applies the
same <code>source_rank</code> preference the byte-identical pass uses to choose which copy survives.
It is wired at the seams the card names: inside <code>rag.retrieve</code> (both the fast index path
and the explicit-entries path) and inside <code>rag.retrieve_any</code>'s fused and dense-only
branches, always over an over-fetched pool before <code>k</code> is taken, never on the raw
<code>k</code>-sized page. It degrades to a no-op whenever the dense store is not ready, is not
quantized, or carries no vector for an entry &mdash; two unknowns are never treated as a match, same
rule the byte-identical pass follows for a missing content digest. Unit tests cover the clustering
logic directly against a hand-built store (no <code>sqlite-vec</code> extension required, since
<code>vec_raw</code> is an ordinary table) plus the wiring at every seam; an end-to-end test against a
real <code>dense.build()</code> store is included but ran only in CI, not in this sandbox.

<b>What is still open, and why this stays <code>inflight</code> rather than <code>shipped</code>.</b>
The card's own hard part &mdash; &ldquo;establish the equivalent bound first&rdquo;, i.e. counting how
many near-duplicate clusters span more than one <em>name</em> at the chosen threshold, over a real
corpus &mdash; has not been run. <code>scripts/measure_near_duplicate_bound.py</code> now exists to
compute exactly that count against any already-built dense store, but the session that wrote it had
no dense store to point it at: taps and PyPI package installs were both unavailable from that sandbox
(no <code>[rag]</code> extra, so no local build to measure against). Running it against the pinned
eval corpus, and ideally a real multi-hundred-tap install, is the remaining step before
<code>NEAR_DUP_THRESHOLD</code> can be trusted rather than merely asserted conservative. The PR also
could not run <code>make check</code> locally for the same reason (no PyPI access in that sandbox);
it relies on CI, which does install the <code>[rag]</code> extra for the dense-covering tests
(<code>ci.yml</code>'s own comment: &ldquo;sqlite-vec so dense.py's mutants are covered by the dense
tests&rdquo;), to be the real verification.
