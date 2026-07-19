---
id: cache-the-catalog-entry-set-across-rag-queries
board: code
section: internals
status: shipped
category: Performance
complexity: M
impact: Med
wow: 3
note: 
order: 10
owner: loop/cache-entry-set
pr: 114
title: Cache the catalog entry-set across RAG queries
---
<code>rag.retrieve()</code> calls <code>all_entries()</code>, which reads &amp; <code>json.loads</code> <b>every tap cache on every search</b> to build the live map (<code>rag.py:323 · catalog.py:166–181</code>) — the BM25 index is mtime-cached, the entry set is not. Memoize the entry set on cache mtime the same way.
