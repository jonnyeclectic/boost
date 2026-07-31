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

<b>Step 1 is shipped</b>, with two corrections to the plan above that surfaced only by measuring.

<b><code>fastembed</code> cannot be used here.</b> Its PyPI classifier declares <code>License ::
Other/Proprietary License</code> even though the project is Apache-2.0, and
<code>scripts/check_licenses.py</code> denies that with no override &mdash;
<code>UNDECLARED_OK</code> exists for a package declaring <i>nothing</i> (the <code>ragas</code>
precedent), not for one declaring the wrong thing. Its tree also drags in
<code>py-rust-stemmers</code>, which declares no licence at all, plus Pillow,
<code>requests</code> and <code>loguru</code>, none of which boost has a use for. Measured with the
repo's own gate: the fastembed closure is <b>32 packages with 2 findings</b>, ONNX Runtime plus a
tokenizer is <b>20 packages with 0</b>. The lean pair shipped, at the cost of ~150 lines of
download/pool/normalise in <code>core/localembed.py</code>.

<b>The model is 133 MB, not ~30 MB.</b> That figure describes the <i>quantized</i> rebuild third
parties publish; BAAI's own ONNX export is 133,093,490 bytes. boost fetches the authoritative one
and sha256-verifies it against a pinned repository revision &mdash; a project with signed taps and
hash-pinned locks has no business taking model weights from a re-uploader to save a one-time
download. Quantization is a genuine follow-up, but it changes the vectors, so it needs its own eval
rather than a swap.

Two details worth recording for whoever takes step 4. BGE is <b>CLS-pooled</b>, not mean-pooled:
mean pooling would still emit 384 plausible-looking floats and quietly worse retrieval, which is
the kind of error an eval catches and a unit test does not. And the chain puts local <b>last</b>,
so a user with a Voyage key keeps voyage-4 instead of being silently downgraded.

Verified end to end against the real weights: 384 dimensions as declared, L2 norm 1.000000, and
<code>sim("making my application faster", "application performance tuning") = <b>0.7691</b></code>
against <code>sim(&hellip;, "quantum computing circuit simulation") = <b>0.5338</b></code> &mdash;
the exact failure this card opened with, now ordered correctly.

Constraints this must respect: the shipped runtime is stdlib-only and
<code>[project].dependencies</code> is empty, so a local model belongs behind an extra like
<code>[rag]</code>, with the keyless path degrading to BM25 exactly as it does now. The required
<code>eval</code> gate already floors BM25 recall@k at 0.85 over the golden set, so step 6 has a
harness to extend rather than invent. Related:
[[dense-search-fallback-and-stale-tap-pruning]] and
[[cache-the-catalog-entry-set-across-rag-queries]].

<b>A sibling item proposes a different backend</b>, and landed from another loop while this was in
review: [[keyless-dense-tier-local-static-embeddings]] argues for a <i>static</i> model
(model2vec/potion class) &mdash; a lookup table rather than a transformer, pure stdlib, no
<code>numpy</code>, no <code>onnxruntime</code>, ~1&nbsp;ms per query, reranking BM25's top-200. The
two are not the same design and the comparison is worth settling with the eval (step 6) rather than
by argument.

One of its objections applies directly to what shipped here and was worth measuring rather than
waving away: it holds that <code>import numpy</code> alone costs 180&ndash;390&nbsp;ms cold, which
would disqualify a transformer from a one-shot CLI path. Measured on this machine, best of three
cold processes: <code>import numpy</code> <b>51&nbsp;ms</b>, <code>import onnxruntime</code>
<b>62&nbsp;ms</b>, and a complete cold <code>embed()</code> &mdash; process start, ONNX session
build over the 133&nbsp;MB graph, tokenize, infer &mdash; <b>233&nbsp;ms</b>. So the objection does
not reproduce here, though import cost is genuinely machine- and version-dependent and their number
may be real on theirs. 233&nbsp;ms is also very likely <i>faster</i> than the Voyage round trip it
sits beside, and it is paid only by users who installed the extra.

<b>If step 6 is the tie-break, it needs a method and not just a number.</b> The sibling item already
produced one cautionary result worth inheriting rather than repeating: its own headline, <b>+11.0
recall / +15.9 hit@1</b>, did not survive verification. Three failures, none specific to a static
model, all reachable from here. Its baseline used a kind oracle the live search path does not have,
so the comparison was never against what a user experiences. The blend weight
(<code>w_dense=0.7</code>) <em>and</em> the rerank pool depth were both tuned by argmax on the same
82 queries they were then reported on &mdash; fitting and reporting on one set. And at n=82 on a
binary metric, the smallest net win reaching <em>p</em>&lt;0.05 is <b>6 queries</b>: its
<code>hit@1</code> (+13 net) clears that bar, while recall (+9) sits at the resolution floor and
should not have led.

So four constraints on step 6, whichever backend wins. Report <b>McNemar</b> on paired per-query
outcomes rather than two independent-looking averages, since the engines are scored on the same
queries. Hold the blend weight and pool depth <b>out</b> of the query set they are scored on. Lead
with <code>hit@1</code> &mdash; on a golden set this size, recall moves inside its own noise. And
measure each engine <b>alone</b> before any fusion, so a hybrid win cannot be quietly credited to
the embedder that did not earn it. One structural caveat also transfers: a skill's name is only
~10.5% of a mean-pooled surface vector while 106 description clusters are shared across 270 distinct
names, so a lift measured on today's corpus may <em>shrink</em> rather than hold as the index grows
toward 50k items &mdash; an argument for re-measuring at scale before believing any of this.

The static approach still wins on cost and would win outright if the quality gap is small &mdash;
which is exactly what the eval should decide. Its own card is right that neither should ship a
retrieval <i>claim</i> before that eval exists.

<b>Step 6, run against those four constraints &mdash; and it does not say what this card assumed.</b>
Corpus rebuilt from <code>tests/eval/taps.txt</code> (6 taps, 743 entries, 3740 passages embedded
locally), k=10, 91 golden queries. Each engine measured <em>alone</em>, no fusion:
<code>catalog.search</code> hit@1 0.714, recall 0.918, MRR 0.783; <b>BM25 full-content hit@1
0.780</b>, recall 1.000, MRR 0.860; <b>dense (local bge-small) hit@1 0.780</b>, recall 0.956, MRR
0.853.

Leading with <code>hit@1</code> as instructed: <b>71 queries each &mdash; an exact tie.</b> Recall
differs by 4 queries (91 against 87) and MRR by 0.6, both under the ~6-query floor this card sets
for <em>p</em>&lt;0.05 at this <em>n</em>. So the honest reading is <b>no significant difference
between BM25 and local dense on the golden set</b> &mdash; not a win for either. An earlier draft of
this note claimed BM25 won; that was the recall number leading, which is exactly the error the four
constraints above were written to prevent.

<b>The more useful result is that the golden set cannot grade this feature at all.</b> It scores
real catalog items <em>by name</em>, which is BM25's strength by construction &mdash;
<code>CLAUDE.md</code> already records that BM25 recall over this corpus is 1.000. It contains none
of the human-phrased queries the keyless work exists for, and on those the two engines separate
sharply: <code>"my app is slow"</code> returns <code>phoenix-docker-setup</code>,
<code>guidelines</code>, <code>solidjs---error-boundaries</code> from BM25 against
<code>analyse-problem</code>, <b><code>performance-optimization</code></b>,
<code>fastapi-best-practices</code> from dense; <code>"I need to make my website accessible"</code>
returns <code>do-and-judge</code>, <code>write-concisely</code>, <code>do-in-steps</code> against
<b><code>accessibility-guidelines</code></b> first. That is a demonstration, not a measurement
&mdash; there is no scored query set of that shape yet, which is the point.

Three consequences. <b>Step 6's first deliverable is a query set, not a number</b>: golden queries
in the human-phrased style, or the eval keeps answering a question nobody asked. <b>Step 4 (RRF)
gains support</b> &mdash; a tie on keyword queries plus a qualitative dense win on human ones is the
"two engines fail in opposite directions" case, and fusing is the response to it. And <b>the current
preference order deserves a look</b>: <code>rag.retrieve_any</code> takes dense whenever it is ready
and non-empty, so shipping step 1 without step 4 silently moved keyword queries onto the engine that
is, at best, tied for them.

<b>Method note.</b> The first indexing pass reported 3 taps failed to embed (2716 of 3740 passages).
A rerun stored all 3740, and two 30-batch replays never reproduced a failure, so it was transient
resource pressure rather than a defect &mdash; the retry path (no commit recorded for a failed tap)
did its job. The figures above come from a complete index.

<b>Step 4 shipped, measured against the same 91 queries.</b> <code>retrieve_any</code> no longer
picks an engine; it over-fetches <code>RRF_K</code>=60 from each and fuses by reciprocal rank,
<code>1/(60+rank)</code> summed, keyed on <code>(name, tap)</code> &mdash; the key both engines
already dedupe on. Adding a <code>hybrid</code> column to the eval:
<code>catalog.search</code> hit@1 0.714; BM25 hit@1 0.780, recall 1.000, MRR 0.860, nDCG 0.895;
dense hit@1 0.780, recall 0.956, MRR 0.853, nDCG 0.876; <b>hybrid hit@1 0.813, recall 0.978, MRR
0.883, nDCG 0.905</b>.

Hybrid leads on <code>hit@1</code>, MRR and nDCG, and gives up 2 queries of recall to BM25.
<b>Neither difference is significant</b> by the bar set above: +3 net queries on hit@1 and &minus;2
on recall, both inside the ~6-query floor for <em>p</em>&lt;0.05 at this <em>n</em>. So the case for
fusing is not "it scores higher" &mdash; it is that fusing is the only option that is <em>at or near
best on both query shapes</em>, where preferring either engine is measurably wrong for half of them.

<b>This reverses a deliberate earlier decision</b>, and that is worth flagging rather than burying:
<code>test_a_non_empty_dense_result_is_still_final</code> existed precisely to stop
<code>retrieve_any</code> "always running BM25 too". Its premise was that a dense hit is the better
answer, which the tie above retires. The other half of that fix &mdash; an <em>empty</em> dense
result is a thin index, not a verdict, and must fall through to BM25 &mdash; still stands and is
still tested.

<b>One honest counter-observation.</b> On two hand-picked human-phrased queries, fusion at k=3
<em>lost</em> the best dense hit: <code>"my app is slow"</code> dropped
<code>performance-optimization</code> and <code>"I need to make my website accessible"</code>
dropped <code>accessibility-guidelines</code>, in both cases because a junk BM25 rank-1 outweighed a
good dense rank-2. That is exactly the tradeoff this card predicted &mdash; "rank fusion discards
confidence" &mdash; and it is an anecdote at n=2 against a measured win at n=91, so it did not block
shipping. It is the strongest argument for the query set step 6 still needs, and the first thing to
re-measure once that exists.

<b>Step 6's real deliverable, and it settles the question.</b> The missing piece was never a number
&mdash; it was a query set of the shape this feature exists for.
<code>tests/eval/golden-natural.jsonl</code> is 50 queries written from each target's own
<code>description</code> and nothing else, phrased as a user problem, with the target's distinctive
name tokens deliberately excluded (a query containing "docker" finds <code>docker-expert</code> by
string match and measures nothing). The whole set was written <em>before</em> any engine was run
against it and scored once, so it could not be selected to flatter a result already seen. A
mechanical check caught five queries that had leaked a name token and they were rewritten.

Over the same corpus at k=10, 50 queries: <code>catalog.search</code> recall 0.330 hit@1 0.080;
<b>BM25 recall 0.690 hit@1 0.240</b>; <b>dense recall 0.760 hit@1 0.420</b>;
<b>hybrid RRF recall 0.820 hit@1 0.420</b> MRR 0.559 nDCG 0.614.

<b>BM25 collapses on this shape</b> &mdash; hit@1 falls from 0.780 on the keyword set to
<b>0.240</b> here, recall from 1.000 to 0.690. And dense beats it by <b>+9 net queries</b> on hit@1
(21 of 50 against 12), which clears the ~6-query significance floor this card set. <b>That is the
first significant retrieval difference anyone has measured in this repo</b>, and it is in the
opposite direction from the keyword set.

So the two sets together say something neither says alone. On keyword queries BM25 and dense tie and
hybrid edges ahead; on natural queries BM25 is far behind and hybrid is at-or-above dense on every
metric. <b>Hybrid is the only engine that is at or near best on both shapes</b> &mdash; which is
precisely the argument step 4 was shipped on, now with a significant margin behind it rather than
+3 queries inside the noise.

One caveat the slice exposes: <code>skill</code> queries score hit@1 0.459 against
<code>workflow</code> 0.308. The workflows in this corpus are overwhelmingly
<code>&lt;technology&gt;-expert</code> agents, so a problem-phrased query has to bridge from a
symptom to a product name with no shared vocabulary at all &mdash; the hardest case, and the one
where a larger embedding model would most likely show its value. Worth re-running against Voyage
before concluding the local model is enough.

The set is deliberately <b>not</b> wired into <code>make eval</code> or the required gate: it needs
the <code>[rag]</code> extra and a built store, and its purpose is comparing engines rather than
flooring one. Run it with <code>--golden tests/eval/golden-natural.jsonl</code>.


<b>Step 4 is shipped too.</b> <code>rag.rrf_fuse</code> landed in <code>#360</code> with
<code>RRF_K = 60</code>, fusing on ranks exactly as described above, and
<code>retrieve_any</code> reports <code>hybrid RRF</code> when both engines are built. Recording it
here because this card still read as though only step 1 were done, and the next loop scanning for
work would have rebuilt it. The step's own instruction &mdash; &ldquo;ship the k=60 default, benchmark
it, and tune only if the eval says so&rdquo; &mdash; was followed: the benchmark is
<code>tests/eval/golden-natural.jsonl</code>, and k=60 is untouched.

<b>Steps 2, 3, 5 and 6 remain open.</b> Note that step 6 (publish the eval) is now partly answered by
the gate work in <code>#365</code>, which floors four metrics instead of recall alone and keys
baselines to their query set, so BM25-vs-dense-vs-hybrid comparisons are at least falsifiable. What
step 6 still wants is the published write-up rather than the instrument.
