---
id: mutation-hardening-core-store-py
board: code
section: shipped
status: shipped
category: Testing · Bug
complexity: M
impact: High
wow: 3
note: 25 mutants killed
order: 1
owner:
pr:
title: Mutation hardening — <code>core/store.py</code>
---
Cut mutmut survivors 54&nbsp;→&nbsp;29 and uncovered a latent
           timestamp-preservation bug the old tests masked (second-precision
           <code>now_iso()</code> collisions hid <code>installed_at</code>/<code>tags</code>
           preservation mutants).
