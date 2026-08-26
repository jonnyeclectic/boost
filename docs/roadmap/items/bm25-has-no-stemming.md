---
id: bm25-has-no-stemming
board: code
section: pipeline
status: next
category: Search · Retrieval
complexity: M
impact: High
wow: 4
note: boost search brainstorm finds nothing while brainstorming finds it; 15.7% of catalog names are unreachable by their own stem
order: 127
owner:
pr:
title: <code>boost search brainstorm</code> finds nothing, and <code>brainstorming</code> finds it
---
<b>The symptom, in two commands against the same five-skill tap.</b>
<code>boost search brainstorming</code> returns the skill.
<code>boost search brainstorm</code> returns <b>zero</b> matches and sends the user to
<code>boost discover</code> to search all of GitHub for something already sitting in their
catalogue. <code>boost chat "what helps me brainstorm"</code> has the same hole and answers with
two unrelated skills. <code>core/rag.tokenize</code> lowercases, splits on non-alphanumerics and
drops a small stopword list — there is no stemming and no prefix fallback, so
<code>brainstorm</code> and <code>brainstorming</code> are simply different terms.

<b>Measured on the 461 tap caches on this machine: 29,607 distinct item names, 9,739 distinct
name tokens.</b> <b>4,663 of those names (15.7%)</b> carry a token whose stem finds nothing —
counting only stems that appear at least five times elsewhere in the corpus, so each is
demonstrably a word people type rather than an artefact of naive suffix stripping. The worst are
not exotic: <code>pattern</code> misses <b>474</b> names ending <code>-patterns</code>,
<code>skill</code> misses <b>252</b> ending <code>-skills</code>, <code>implement</code> misses
161, <code>event</code> 115, <code>error</code> 112, <code>webhook</code> 109,
<code>agent</code> 83, <code>market</code> 81 named <code>-marketing</code>. A user searching
this catalogue for <code>skill</code> cannot reach a quarter of a thousand items named for it.

<b>It is invisible from a developer install, which is why it survived.</b> This machine has the
<code>[rag]</code> extra and a built dense store, so search reports <code>hybrid RRF (BM25 +
dense)</code> and the embeddings absorb the morphology: <code>webhook</code> returns 51 matches
and <code>webhooks</code> returns 47. The gap is only visible on the always-on, zero-dependency
BM25 path — which is what every user without the extra runs, what
<code>search</code> prints <code>semantic search is off</code> for, and what the required
<code>eval</code> gate floors. There is no <code>--engine</code> flag, so a maintainer cannot
easily reproduce a plain user's result.

<b>Two fixes, and they are not the same size.</b> A <b>zero-match prefix fallback</b> — on 0
hits, retry against vocabulary tokens by prefix — touches no index format, needs no baseline
regeneration, and fires only where BM25 currently returns nothing, so it cannot move a single
eval metric; it fixes the exact observed symptom in both <code>search</code> and
<code>chat</code>. A <b>real stemmer</b> is the better answer and costs an index-format bump plus
a regenerated <code>tests/eval/baseline.json</code>, and would move all four floored metrics.
Either lands in <code>core/rag.py</code>, so the tests must kill mutants, not merely cover lines.
