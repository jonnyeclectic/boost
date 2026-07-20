---
id: atomic-skill-install-temp-dir-swap
board: code
section: internals
status: shipped
category: Robustness
complexity: M
impact: Med
wow: 3
note: 
order: 7
owner: loop/reconcile-stale-cards
pr:
title: Atomic skill install (temp-dir swap)
---
Already shipped: <code>core/store.py</code>'s <code>_copy_skill</code> stages the
           full copy in a temp dir on the same filesystem, then swaps it in with
           two atomic <code>os.replace</code> renames and rolls back to the original
           on any failure — the old rmtree-then-copytree window is gone. Covered by
           <code>test_copytree_failure_preserves_existing</code> and the flaky
           <code>os.replace</code> test in <code>tests/unit/test_store.py</code>.
