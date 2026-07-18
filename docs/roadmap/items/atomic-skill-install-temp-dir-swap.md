---
id: atomic-skill-install-temp-dir-swap
board: code
section: internals
status: planned
category: Robustness
complexity: M
impact: Med
wow: 3
note: 
order: 7
owner:
pr:
title: Atomic skill install (temp-dir swap)
---
<code>_copy_skill</code> does <code>rmtree(dest)</code> then <code>copytree()</code> (<code>core/store.py:108–131</code>); an interrupt between the two leaves a missing or half-copied skill, and the lock is written afterward — so a mid-copy failure leaves store and lock <b>disagreeing</b>. Copy to a temp dir and atomically swap into place.
