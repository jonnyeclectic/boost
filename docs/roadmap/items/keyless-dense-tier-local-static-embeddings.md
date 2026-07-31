---
id: keyless-dense-tier-local-static-embeddings
board: code
section: pipeline
status: planned
category: Search · Retrieval
complexity: L
impact: High
wow: 5
note: semantic search with no key, no billing, no deps
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

