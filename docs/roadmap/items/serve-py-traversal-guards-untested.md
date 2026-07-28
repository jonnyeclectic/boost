---
id: serve-py-traversal-guards-untested
board: code
section: internals
status: shipped
category: Testing · Security
complexity: S
impact: Med
wow: 2
note: lowest coverage in core/
order: 38
owner: loop/serve-guard-coverage
pr: 282
title: <code>boost serve</code>'s own path-traversal guards are untested
---
<code>serve.py</code>'s defenses against a malicious catalog <code>skill_md</code> path
(<code>_is_within</code>, <code>_safe_join_within</code>, the <code>".." in rel.parts</code> check)
and its HTTP-handler failure modes are the least-covered lines in <code>core/</code> — 84.5% file
coverage, the lowest of any module — and no test actually feeds a <code>..</code>-containing path
through <code>skill_text()</code> to prove the guard fires. Add adversarial tests for the traversal
guards and for <code>_CatalogHandler</code>'s error paths.
