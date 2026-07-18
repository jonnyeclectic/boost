---
id: unify-tilde-two-copies-have-a-boundary-bug
board: code
section: internals
status: inflight
category: Correctness
complexity: S
impact: Med
wow: 2
note: 
order: 9
owner: loop/unify-tilde
pr:
title: Unify <code>_tilde()</code> — two copies have a boundary bug
---
Eight command modules each define <code>_tilde</code>; the <code>quality</code> and <code>intelligence</code> versions use <code>startswith(home)</code> with no separator check (<code>quality.py:78</code>), so <code>/Users/bob-backup</code> wrongly contracts to <code>~-backup</code>. Collapse to one helper in <code>core/paths</code>.
