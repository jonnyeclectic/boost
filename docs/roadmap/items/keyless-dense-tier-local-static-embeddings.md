---
id: keyless-dense-tier-local-static-embeddings
board: code
section: pipeline
status: planned
category: Search · Retrieval
complexity: L
impact: High
wow: 5
note: spike done: the perf claims were 6-22x conservative, but rerank added +0 at real scale
order: 73
owner:
pr:
title: Semantic search for users who will never set an API key
---
Dense retrieval today needs the <code>[rag]</code> extra <em>and</em> a
<code>VOYAGE_API_KEY</code>/<code>OPENAI_API_KEY</code> <em>and</em> a built
store. Most users will do none of that, so the default experience is BM25
forever. The keyless path is a <b>local static embedding model</b> —
<code>potion-retrieval-32M</code> class, MIT, model2vec family — which is not a
transformer: the entire weight file is one lookup table, so inference is
tokenize → gather rows → mean-pool → L2-normalize.
Measured locally, pure stdlib: <b>~1 ms to embed a query</b> (mmap + bisect over
sorted keys), 12.8 MB of int8 vectors for 50k items at 256-d, and <b>~20 ms to
rerank BM25's top-200</b>. No numpy, no <code>sqlite-vec</code>, no ANN index,
no new runtime dependency. <code>import numpy</code> alone costs 180–390 ms
cold, which disqualifies it from a one-shot CLI query path; the BM25 prefilter is
what makes the stdlib version viable, since a full 50k brute-force scan is 1.5 s
in pure Python. Pool depth is justified by measurement: BM25 recall saturates at
0.890 by depth 200 and gains nothing at 400, so reranking the top-200 gives up
essentially nothing versus scanning everything.
<b>Why this and not a shipped Voyage index.</b> A precomputed Voyage index is
inert without a Voyage <em>query</em> vector, and the only keyless way to get one
is a maintainer-run anonymous embedding endpoint — an unauthenticated free
embeddings API backed by the maintainer's card, which also ships every user query
off-machine and breaks offline. A local model is deterministic, so the artifact
becomes a <em>cache</em> rather than a correctness dependency: a newly tapped
repo can be embedded on the user's own machine. Doc-side is the asymmetry worth
shipping for — 29 ms/doc in pure Python is ~24 min for 50k single-core, versus
seconds in CI with numpy.
<b>Do not ship this before the eval and dedup items.</b> The headline claim
(+11.0 recall / +15.9 hit@1) did <em>not</em> survive verification: its baseline
used the kind oracle the real search path lacks, and both the blend weight
(<code>w_dense=0.7</code>) and the pool depth were argmax'd on the same 82
queries they were reported on, by 2-query margins. On a binary metric at n=82
the smallest net win reaching p&lt;0.05 is 6 queries; <code>hit@1</code> (+13 net
queries) holds up, recall (+9) sits at the resolution floor. And the structural
risk is real: the name is only ~10.5% of a mean-pooled surface vector while 106
description clusters are shared across 270 distinct names, so the lift may
<em>shrink</em> toward 50k rather than hold. Sequence: fix the gate, dedup, fix
the index format, then re-measure with McNemar and a held-out blend weight,
leading with <code>hit@1</code>. Test entry-level dense <em>alone</em> before the
blend, ship 512-d not 256-d (the whole case for 256-d was one query), keep
Voyage/OpenAI as the opt-in ceiling, and keep BM25 as the floor. The model table
cannot go in the default wheel — the shipped runtime is 0.79 MB and every merge
to main cuts a release, so +17.4 MB × ~24 releases/day exhausts PyPI's 10 GB
project quota in under a month; it needs a separate, rarely-released data
package behind an extra.
<b>Related, and partly overtaken:</b> [[keyless-semantic-search-for-everyone]] shipped a keyless
path using a <i>transformer</i> (BGE via ONNX Runtime, in the <code>[rag]</code> extra) while this
item was open. That does not settle the question this card asks &mdash; a static lookup table is
still far cheaper, and this card's discipline about not shipping a retrieval claim before the eval
still stands. What it does change is the baseline: "keyless" is no longer the differentiator, so the
case for a static model now rests on <b>cost</b> (~1&nbsp;ms and no runtime dependency, against a
measured 233&nbsp;ms cold and 34&nbsp;MB of wheels) rather than on availability. Status left alone
deliberately &mdash; this is another loop's item to own.


<b>Unblocked, and the case for it got stronger.</b> This card says &ldquo;do not ship this before the
eval and dedup items&rdquo;. Both have now landed: the eval gate floors four metrics over a
realistic-sized corpus with baselines keyed to their query set, and content-hash dedup has merged.

The new evidence is a timing measurement. Building the <em>shipped</em> ONNX keyless store over 743
entries (3,740 chunks, <code>bge-small-en-v1.5</code> on CPU) took <b>4,431 s &mdash; 74 minutes</b>,
about 1.2 s per chunk. This card's static-embedding proposal claims ~29 ms/doc in pure Python. If
that holds it is a difference of more than an order of magnitude on the doc side, which is exactly
the cost that makes prebuilt shards mandatory today. Worth measuring the model2vec path directly
before committing &mdash; but the gap it claims to close is now a measured number rather than an
estimate.

<b>Spike done &mdash; the prerequisites this card set have all shipped, so the measurement it asked
for was finally runnable.</b> It says &ldquo;do not ship before the eval and dedup items&rdquo;;
dedup landed in <code>#370</code>, the index format in <code>#367</code>/<code>#371</code>, the
published eval in <code>#373</code>. What follows is <code>potion-retrieval-32M</code> (MIT, 63,091
&times; 512 F32 lookup table &mdash; confirmed a single tensor, no transformer) driven by a
hand-written pure-stdlib loader: WordPiece &rarr; gather rows &rarr; mean-pool &rarr; L2, mmap'd,
no numpy.

<b>The two unverified performance claims were not just right, they were conservative.</b> Query
embedding measured <b>0.16&nbsp;ms</b> against the card's <code>~1&nbsp;ms</code>. Document
embedding measured <b>1.34&nbsp;ms</b> on a synthetic 105-token doc and <b>3.27&nbsp;ms</b> on 300
real catalogue entries (median 61 tokens), against the card's <code>~29&nbsp;ms</code>.

<b>That reverses one of this card's design arguments.</b> The doc-side cost was the reason prebuilt
artifacts looked mandatory: &ldquo;29&nbsp;ms/doc in pure Python is ~24&nbsp;min for 50k
single-core&rdquo;. At the measured 3.27&nbsp;ms it is <b>2.7&nbsp;min</b> &mdash; roughly the time
a first <code>boost tap --defaults</code> already takes. Local embedding is therefore viable on the
user's own machine, and shipped shards become a genuine optimisation rather than a requirement. (Not
to be confused with the ONNX <code>bge-small</code> path measured at ~1.2&nbsp;s/chunk in
<code>keyless-semantic-search-for-everyone</code>; that number stands, and the gap between them
<em>is</em> the case for the static model.)

<b>But reranking bought nothing at real scale, which is the result that matters.</b> Over the 50
natural-language golden queries against a real <b>71,655-entry</b> catalogue, reranking BM25's
top-200 by cosine scored <code>hit@1</code> <b>2/50</b> &mdash; identical to BM25's own
<b>2/50</b>, a net change of <b>+0 queries</b> where this card's own statistics note says 6 net
queries is the smallest win reaching p&lt;0.05. On two hand-checked pairs the ordering was right but
the margin was thin (related 0.154 vs unrelated 0.097).

<b>Stated limits, because this does not settle the question.</b> The document vector was built from
<code>name + description</code> truncated to 1,500 characters, not the full body the real dense path
indexes, so this measures a weaker representation than the one being proposed. No blend was tried
&mdash; pure rerank, no <code>w_dense</code> &mdash; and this card explicitly asks for a held-out
blend weight and McNemar. What it does establish is that the <em>cheap</em> version of the idea does
not pay for itself, so the remaining work is representation and blending, not inference speed.

<b>An unrelated finding fell out of it, and it is the more important one.</b> BM25 scored
<code>hit@1</code> <b>0.040</b> here against the <b>0.340</b> published in <code>#373</code>. Both
are correct: the published figure is measured over the pinned 6-tap eval corpus of <b>743</b>
entries, and this run used a real 77-tap install &mdash; <b>96&times; larger</b>. Golden targets are
all present and rank 7th, 8th, 38th, 163rd rather than 1st. The eval corpus is not a scale model of
a real install, and the gate's floors describe a catalogue two orders of magnitude smaller than the
one users have. Tracked separately in [[eval-corpus-is-96x-smaller-than-a-real-install]].

