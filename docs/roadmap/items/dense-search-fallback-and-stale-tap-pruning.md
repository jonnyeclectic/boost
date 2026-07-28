---
id: dense-search-fallback-and-stale-tap-pruning
board: code
section: internals
status: shipped
category: Bug
complexity: M
impact: Med
wow: 2
note:
order: 30
owner: loop/dense-fallback-and-prune
pr: 293
title: Dense search's empty result skips the BM25 fallback
---
<code>_retrieve_any</code> treats any non-<code>None</code> dense result as final, but
<code>dense.retrieve()</code> returns <code>[]</code> (not <code>None</code>) whenever every KNN
neighbor gets filtered by kind mismatch or staleness — silently short-circuiting the documented
"everything degrades to BM25" contract. Compounding it, <code>dense.build()</code>'s incremental
path only prunes chunks for taps still present in the current entry set, so a tap removed via
<code>boost tap remove</code> leaves ghost vectors in <code>rag_vectors.sqlite</code> forever,
crowding the KNN pool on every future query. Distinguish "dense unavailable" from "dense had zero
live hits," and prune removed taps on every build, not just changed ones.
