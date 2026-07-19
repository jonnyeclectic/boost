---
id: localize-the-stored-bm25-snippet
board: code
section: internals
status: shipped
category: Tech-debt · RAG
complexity: M
impact: Low
wow: 3
note: query-centered snippets
order: 17
owner: loop/localize-bm25-snippet
pr:
title: Localize the stored BM25 snippet
---
<code>_make_docs</code> stored <code>piece[:200]</code> — the head of the best
chunk — and <code>retrieve</code> surfaced it verbatim, yet the docstrings
promised the "best-matching passage": when the matched terms sat past the
chunk's first 200 chars, the shown snippet (and the rerank context fed to the
LLM) missed them entirely. Now the index stores a larger head of the matched
chunk (<code>SNIP_STORE</code>) and <code>retrieve</code> windows a
<code>SNIP_WIDTH</code>-char passage <em>centered on the first query term</em>,
with ellipsis markers on trimmed edges (<code>_passage</code>). Ranking is
untouched — the eval harness confirms <code>recall@10</code> holds at
<code>0.919</code> — and the index grows a bounded ~34% (an
<code>INDEX_VERSION</code> bump forces the one-time reindex); storing whole
chunks instead cost ~70%.
