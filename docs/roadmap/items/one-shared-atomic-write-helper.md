---
id: one-shared-atomic-write-helper
board: code
section: internals
status: inflight
category: Robustness
complexity: S
impact: Med
wow: 2
note: 
order: 8
owner: loop/atomic-rag-save
pr:
title: One shared atomic-write helper
---
<code>journal._maybe_rotate</code> is a racy read-modify-write that concurrent appends can truncate mid-line; <code>rag._save</code> and <code>config.save</code> repeat the non-atomic pattern (<code>journal.py:63 · rag.py:252 · config.py:93</code>). Factor a single <code>atomic_write</code> into <code>core</code> and route all four through it.
