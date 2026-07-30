---
id: keyless-semantic-search-for-everyone
board: code
section: internals
status: next
category: Retrieval · Architecture
complexity: L
impact: High
wow: 5
note: the vector store was never the problem — only turning text into vectors needs a key
order: 0
owner:
pr:
title: Semantic search is gated behind an API key it does not need
---
boost's flagship retrieval is invisible to almost everyone who installs it. <code>boost search "my
app is slow"</code> on the five default taps returns <code>dnanexus-integration</code>,
<code>tamarind</code>, <code>cirq</code>, <code>molfeat</code> &mdash; bioinformatics and quantum
computing, nothing about performance. That is BM25 doing exactly what BM25 does when a human types
like a human, and it is what every keyless user experiences.

<b>The vector database was never the problem.</b> Vectors already live on the user's own machine in
sqlite-vec (<code>~/.boost/cache/rag_vectors.sqlite</code>), refreshed per tap against the commit it
was built from. Nothing is hosted and nothing needs to be. The <em>only</em> API-bound step is
turning text into vectors: <code>embed.provider()</code> returns <code>"voyage"</code> with
<code>VOYAGE_API_KEY</code> set, <code>"openai"</code> with <code>OPENAI_API_KEY</code>, and
otherwise <code>None</code> &mdash; at which point everything degrades to BM25. So the real dilemma
("every user rebuilds the index, or someone hosts and pays for it") is false in both halves.

Six steps, and the first two carry most of the value.

<b>1 &mdash; A local ONNX provider, as the third link in a chain built for it.</b> Extend
<code>embed.provider()</code> to Voyage &rarr; OpenAI &rarr; <b>local</b> &rarr; BM25, using ONNX
Runtime on CPU with a small model (<code>bge-small-en-v1.5</code>, 384-dim, ~30&nbsp;MB once). The
sqlite-vec store, the per-tap commit cache and KNN search are all untouched &mdash; only the
text&rarr;vector call changes. This removes the key, the signup and the card for <em>every</em>
user, and Voyage stays a free quality upgrade for anyone who adds one.

<b>2 &mdash; Prebuild per-registry shards in CI.</b> Embedding the full catalogue (~28k items,
~150M tokens) on a laptop is an hour-plus, which no one will wait for. A workflow embeds each
registry and publishes vectors as GitHub Release artifacts keyed on the registry's git commit
&mdash; the cache key the code already uses &mdash; so <code>boost tap</code> fetches the catalogue
<em>and</em> its shard. This is how Homebrew, npm and crates.io index a moving world.

<b>3 &mdash; Local delta top-up.</b> When a tap runs ahead of its published shard, or is a team or
private registry CI has never seen, embed just those files on the spot. This is the structural
answer to an unbounded ecosystem: shards cover the popular registries, the local model makes the
long tail self-serve, and cost scales with what each user taps rather than with the size of the
whole ecosystem. Without it, every uncatalogued registry is a dead end for a keyless user.

<b>4 &mdash; Fuse the two engines with reciprocal rank fusion.</b> Confirmed against the shipped
code: <code>rag.retrieve_any()</code> picks <em>one</em> engine &mdash; dense when it is ready and
returns a non-empty result, BM25 otherwise. There is no hybrid path today. RRF changes that to "run
both, fuse by rank": <code>score = 1/(60+rank_bm25) + 1/(60+rank_dense)</code>. Fusing on
<b>ranks, not scores</b>, is the point &mdash; a BM25 score and a cosine similarity are on
incomparable scales, and rank fusion sidesteps calibration entirely. The two engines fail in
opposite directions and this corpus needs both: registries are full of exact identifiers
(<code>EAS</code>, <code>pptx</code>, skill names) where BM25 is strongest and embeddings weakest,
while sloppy queries are where BM25 returns quantum computing. <code>retrieve_any</code> is the
single seam every retrieval path already passes through, CLI and MCP alike, so it is one function.

The tradeoffs are real and should be measured rather than assumed: rank fusion discards confidence,
so plain RRF can trail pure dense on purely semantic queries; "why did this rank third?" gains a
two-part answer; and both engines must index the same chunks (they already share chunking). Ship
the k=60 default, benchmark it, and tune only if the eval says so.

<b>5 &mdash; A hosted demo</b> on free tiers, so the experience is reachable without installing
anything. <b>6 &mdash; Publish the eval</b>: BM25 vs local dense vs Voyage dense vs hybrid on the
existing golden set, with recall@k and MRR. That last one settles step 4 with data instead of
argument &mdash; and if pure dense wins on this corpus, that is the result worth publishing.

<b>Scope note.</b> This is an epic, not a single change. Step 1 is the one that removes the wall and
is worth landing alone; steps 2&ndash;3 are what make it fast enough to be real; step 4 is ~20 lines
in one function and independently shippable; 5 and 6 are separable. Expect this card to decompose
into per-step items as each is picked up &mdash; the value of keeping it whole here is that the
steps only make sense against each other.

Constraints this must respect: the shipped runtime is stdlib-only and
<code>[project].dependencies</code> is empty, so a local model belongs behind an extra like
<code>[rag]</code>, with the keyless path degrading to BM25 exactly as it does now. The required
<code>eval</code> gate already floors BM25 recall@k at 0.85 over the golden set, so step 6 has a
harness to extend rather than invent. Related:
[[dense-search-fallback-and-stale-tap-pruning]] and
[[cache-the-catalog-entry-set-across-rag-queries]].
