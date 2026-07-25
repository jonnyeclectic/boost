---
id: negative-limit-inverts-log-pulse-output
board: code
section: internals
status: planned
category: CLI ergonomics
complexity: S
impact: Low
wow: 1
note:
order: 36
owner:
pr:
title: Negative <code>-n</code> silently inverts <code>log</code>/<code>pulse</code> output
---
<code>boost log</code>/<code>boost pulse</code> accept <code>-n</code>/<code>--limit</code> as a bare
<code>type=int</code> with no positivity check, and the slicing does
<code>out[:n] if n else out</code> — a negative <code>n</code> becomes a Python negative slice, so
<code>-n -1</code> silently returns everything except the most recent event instead of erroring.
<code>discovery.py</code>'s <code>--limit</code> flags already share a <code>_positive_int</code>
validator that rejects values below 1; reuse it here.
