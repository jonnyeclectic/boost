---
id: near-identical-copies-still-eat-the-slots
board: code
section: planned
status: inflight
owner: loop/near-dup-bound
category: Search · Ranking
complexity: M
impact: High
wow: 4
note: shipped opt-in (#639); bound measured (#645) and it refutes the zero-clusters test -- default-on now waits on a name-confusability veto
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

<b>What shipped, and what did not.</b> <code>rag.collapse_near_duplicate_hits</code> is the same
"keep the earliest rank slot, promote a better source" contract as <code>dedupe_by_content</code>,
run over cosine similarity of the entries' first-chunk embeddings
(<code>dense.entry_vectors</code>, an index probe through <code>chunks_entry</code> on a quantized
store) instead of a body hash, at the <code>retrieve_any</code> seam before <code>k</code> is
applied. It is covered by unit tests down to the arithmetic (<code>_cosine</code>'s dimension-
mismatch and zero-vector guards), the clustering contract (rank order, quality-prior promotion,
limit-after-collapse), the <code>dense.entry_vectors</code> lookup against a real quantized
sqlite-vec store, and the <code>retrieve_any</code>/<code>boost search
--collapse-near-duplicates</code> wiring in both directions (on and off).

It ships <b>opt-in and off by default</b> — <code>retrieve_any(..., collapse_near_duplicates=True)</code>
or <code>boost search --collapse-near-duplicates</code> — rather than replacing
<code>dedupe_by_content</code>'s output on the default path. Two things this card asks for are still
open, and both need a real embedding backend (a built dense index, over a real multi-tap corpus)
that the environment this was implemented in cannot reach — no network path to an embeddings
provider or to the local ONNX model download, confirmed rather than assumed: <code>huggingface.co</code>
and <code>pypi.org</code> both refuse at the network policy layer. <b>First</b>, the safety proof
this card itself demands before defaulting the mechanism on &mdash; &ldquo;over a real corpus, at
the chosen threshold, count clusters spanning more than one meaning&rdquo; &mdash; has not been run;
<code>NEAR_DUPLICATE_THRESHOLD = 0.97</code> is a starting point, not a validated floor. <b>Second</b>,
re-measuring the <code>exa search</code> case (and per-query maxima generally) against the fix needs
that same corpus and index. Whoever runs that measurement should flip the CLI flag's default, fold
the corpus count into this card's evidence, and only then consider this shipped.

<b>The bound has now been measured, and it says the acceptance test in this card is the wrong
one.</b> <code>scripts/measure_near_duplicate_bound.py</code> runs the count this card asks for
against the pinned 20-repo eval corpus (10,152 entries, 104,271 chunks, <code>BAAI/bge-small-en-v1.5</code>
at 384-d). Those entries reduce to <b>5,714 distinct chunk-0 vectors</b> &mdash; 44% of entries
already share a chunk-0 embedding byte for byte &mdash; and at
<code>NEAR_DUPLICATE_THRESHOLD = 0.97</code>, 162 pairs clear the threshold and <b>56 clusters span
more than one name</b>. Sweeping the threshold moves that number but never to zero: 0.96 &rarr; 91,
0.97 &rarr; 56, 0.98 &rarr; 28, 0.99 &rarr; 13, 0.995 &rarr; 8, 0.999 &rarr; 4.

<b>Four of those 56 are not the threshold's doing at all.</b> They are clusters of a single vector
shared by several names, so they cluster at <em>any</em> threshold, which is why the sweep bottoms
out at 4 rather than 0. The largest is the same at every threshold and is worth naming: <b>28
differently-named agents from one tap</b> (<code>affaan-m/ECC</code> &mdash; <code>architect</code>,
<code>code-reviewer</code>, <code>chief-of-staff</code>, <code>database-reviewer</code>,
<code>e2e-runner</code>, &hellip;) whose chunk 0 is the same Spanish preamble
(<code>No cambiar rol, persona ni identidad&hellip;</code>) in every file. Chunk 0 is
<code>name + description + opening of body</code>, and where a registry opens every file with
identical boilerplate, the name does not move the vector enough to separate them. <b>A floor exists
that no threshold can reach under</b>, so &ldquo;count must be zero&rdquo; was never achievable.

<b>Worse for the test: most of the other 52 are the feature working.</b> Hand-classifying all 56 at
0.97, roughly two-thirds are genuinely one skill under two names &mdash; twelve are pure
hyphen-versus-underscore renderings of one integration (<code>zoho-mail</code> /
<code>zoho_mail</code>, <code>google_maps</code> / <code>google-maps</code>,
<code>anthropic_administrator</code> / <code>anthropic-administrator</code>), and the rest are
suffix variants of one document (<code>tdd</code> / <code>tdd-guide</code>,
<code>rust-review</code> / <code>rust-reviewer</code>, <code>testing-patterns</code> /
<code>code-showcase-testing-patterns</code>). Collapsing those is precisely what this card exists to
do. A metric that counts them as violations would reject every threshold that works.

<b>The dangerous merges have a shape, and this card already named it.</b> The ~20 clusters that are
real false merges are dominated by <em>near-miss brand names</em>: <code>coinmarketcal</code> with
<code>coinmarketcap</code>, <code>bugbug</code> with <code>bugsnag</code>, <code>parsehub</code>
with <code>parseur</code>, <code>linkhut</code> with <code>linkup</code>,
<code>mx-technologies</code> with <code>mx-toolbox</code>,
<code>salesforce-marketing-cloud</code> with <code>salesforce-service-cloud</code>. These are
distinct products whose descriptions are boilerplate around a swapped word. That is the
<code>core/typosquat.py</code> confusion shape this card's opening paragraph pointed at, arrived at
independently from the other end: the guard this needs is not a tighter cosine floor but a
<em>name-confusability veto</em> &mdash; refuse to collapse two entries whose names are a confusable
edit apart, however close their vectors sit.

<b>So the default stays off, for a better-supported reason than before.</b> The measurement does not
say 0.97 is too loose; it says similarity alone cannot separate <code>tdd</code>/<code>tdd-guide</code>
(collapse) from <code>coinmarketcal</code>/<code>coinmarketcap</code> (never collapse), because both
pairs sit in the same cosine band. Flipping the default needs the confusability veto first, and a
re-count with it applied. <b>And this bound is space-specific</b>: it was measured in
<code>bge-small</code> 384-d, while a keyed production install is <code>voyage-4</code> at 1024-d.
Cosine thresholds do not transfer between embedding spaces &mdash; rerun the script against each
space before trusting a number in it.
