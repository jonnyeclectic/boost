---
id: localize-the-stored-bm25-snippet
board: code
section: internals
status: planned
category: Tech-debt · RAG
complexity: M
impact: Low
wow: 3
note: 
order: 17
owner:
pr:
title: Localize the stored BM25 snippet
---
<code>_make_docs</code> stores <code>piece[:200]</code> — the head of the best chunk — and <code>retrieve</code> surfaces it verbatim (<code>rag.py:154–172,337–341</code>), yet the docstrings promise the "best-matching passage". Center the snippet on the matched terms to improve display and the rerank context sent to the LLM.
