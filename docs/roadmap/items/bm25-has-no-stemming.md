---
id: bm25-has-no-stemming
board: code
section: pipeline
status: inflight
category: Search · Retrieval
complexity: M
impact: High
wow: 4
note: a term with no postings is now replaced by the commonest term it prefixes; a term that has postings is never touched, which is what keeps the eval floors still
order: 127
owner: loop/bm25-stem-fallback
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

<b>What shipped: per-term expansion, not per-query.</b> The obvious design — widen only when the
whole query returns zero hits — was drafted and rejected, because it does not fix the reported
case. <code>boost chat &ldquo;what helps me brainstorm&rdquo;</code> already returns non-empty
results from its other words, so a zero-hit trigger never fires and chat stays broken.
Expansion is therefore per-term: a term with <b>no</b> posting list is replaced by the commonest
term it prefixes, found by an index-backed range scan (<code>term &gt; ? AND term &lt; ?</code>,
upper bound <code>term + "~"</code> because <code>~</code> outranks every character
<code>tokenize</code> can emit — a bound of <code>"z"</code> silently loses
<code>analy</code> &rarr; <code>analyze</code>). Measured after: <code>search brainstorm</code>
returns the skill, and the chat question promotes it from <em>absent</em> to <b>rank 1</b>.

<b>The invariant is the whole safety argument, and it is a test rather than a comment.</b>
<em>A term that has postings is never expanded.</em> <code>_bm25</code> already skips a term with
no posting list, so expansion can only add signal where there was exactly none — meaning any
query whose terms all exist ranks byte-identically and the four retrieval floors cannot move.
<code>test_a_term_that_has_postings_is_never_expanded</code> pins it against a corpus where
<code>pattern</code> and <code>patterns</code> both exist, so a build that dropped the guard
rewrites a query that already worked and fails. Nine hand-written mutants were run against the
new lines and all nine died, including that one.

<b>Still open: a real stemmer.</b> This fallback cannot help where a term exists but is the wrong
inflection — a user typing <code>patterns</code> still will not reach an item named
<code>pattern</code>, because <code>patterns</code> has postings of its own and is left alone.
Closing that means conflating terms that both exist, which changes established rankings and costs
an index-format bump plus a regenerated <code>tests/eval/baseline.json</code>.
