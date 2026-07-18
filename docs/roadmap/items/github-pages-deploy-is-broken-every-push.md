---
id: github-pages-deploy-is-broken-every-push
board: code
section: next
status: next
category: Bug · Infra
complexity: S
impact: High
wow: 2
note: docs site down
order: 1
owner:
pr:
title: GitHub Pages deploy is broken every push
---
Root cause found: a bogus <code>mutants/None</code> gitlink (a stray
           mutmut artifact) was committed with no <code>.gitmodules</code> entry,
           so Pages' submodule checkout aborts with
           <code>fatal: No url found for submodule path 'mutants/None'</code>.
           Fix: stop tracking <code>mutants/</code>.
