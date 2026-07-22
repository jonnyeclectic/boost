---
id: layering-guard-import-linter
board: code
section: dx
status: inflight
category: Quality · Architecture
complexity: M
impact: Med
wow: 4
note: core/ ↛ commands/
order: 3
owner: loop/layering
pr:
title: Layering guard — <code>import-linter</code>
---
Enforce the architecture boost already assumes: <code>core/</code> must
           never import <code>commands/</code>, and the CLI depends inward only.
           <code>import-linter</code> turns that contract into a CI check, catching
           the cross-layer imports that slowly erode a clean engine — a structural
           smell no line-level linter can see.
