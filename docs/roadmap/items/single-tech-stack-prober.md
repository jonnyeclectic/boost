---
id: single-tech-stack-prober
board: code
section: internals
status: planned
category: Tech-debt
complexity: M
impact: Med
wow: 2
note: 
order: 13
owner:
pr:
title: Single tech-stack prober
---
Stack detection exists three times — <code>discovery.detect_stack</code>, <code>intelligence._local_stack</code>, <code>quality._STACK_MARKERS</code> (<code>discovery.py:74 · intelligence.py:359 · quality.py:55</code>) — and two already <code>import detect_stack</code> yet still carry a parallel marker table "as a fallback". Consolidate into one core prober.
