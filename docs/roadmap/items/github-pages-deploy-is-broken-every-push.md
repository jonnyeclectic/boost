---
id: github-pages-deploy-is-broken-every-push
board: code
section: shipped
status: shipped
category: Bug · Infra
complexity: S
impact: High
wow: 2
note: root cause removed in #60
order: 1
owner: loop/roadmap-hygiene-stale-cards
pr: 60
title: GitHub Pages deploy is broken every push
---
Fixed by <b>#60</b>: the bogus <code>mutants/None</code> gitlink (a stray mutmut
artifact with no <code>.gitmodules</code> entry) that made Pages' submodule
checkout abort with <code>fatal: No url found for submodule path 'mutants/None'</code>
is gone. Verified: the Pages "build and deployment" now completes successfully and
the site serves — the boards live at
<code>jonnyeclectic.github.io/boost/docs/roadmap.html</code> (200), since Pages
publishes from the repo root.
