---
id: extension-free-tests-core-dense-py
board: code
section: shipped
status: shipped
category: Testing · Coverage
complexity: M
impact: High
wow: 3
note: 42 tests · +71pts coverage
order: 4
owner:
pr:
title: Extension-free tests — <code>core/dense.py</code>
---
The dense-vector RAG backend's whole test module is
           <code>skipif</code>-gated on the <code>[rag]</code> sqlite-vec C
           extension, so on the default zero-dependency install
           <em>every</em> degradation and ranking path went untested
           (17.6%&nbsp;→&nbsp;89% coverage). New tests force
           <code>_load()&nbsp;→&nbsp;None</code> and drive the SQL helpers and
           <code>retrieve()</code>'s cosine reducer through in-memory/fake
           connections — killing mutants on every machine, extension or not.
