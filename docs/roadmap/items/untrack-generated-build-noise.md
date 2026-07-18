---
id: untrack-generated-build-noise
board: code
section: next
status: next
category: Hygiene · DX
complexity: S
impact: Med
wow: 1
note: unblocks Pages
order: 2
owner:
pr:
title: Untrack generated build noise
---
Over a hundred <code>mutants/**</code>, <code>__pycache__/*.pyc</code>
           and <code>.coverage</code> files are tracked despite being in
           <code>.gitignore</code> — they churn every diff and forced careful
           path-scoped <code>git add</code>s. Remove from the index.
