---
id: untrack-generated-build-noise
board: code
section: shipped
status: shipped
category: Hygiene · DX
complexity: S
impact: Med
wow: 1
note: already fixed in #60
order: 2
owner: loop/roadmap-hygiene-stale-cards
pr: 60
title: Untrack generated build noise
---
Shipped in <b>#60</b>. The generated <code>mutants/**</code>,
<code>__pycache__/*.pyc</code> and <code>.coverage</code> files were removed from
the index (verified: <code>git ls-files</code> now tracks zero of them), so they
no longer churn every diff or force path-scoped <code>git add</code>s.
