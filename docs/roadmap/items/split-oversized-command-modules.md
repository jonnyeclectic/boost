---
id: split-oversized-command-modules
board: code
section: internals
status: planned
category: Maintainability
complexity: L
impact: Med
wow: 2
note: 
order: 15
owner:
pr:
title: Split oversized command modules
---
<code>quality.py</code> (14 cmds / 1,051 lines) mixes audit regexes, conflict NLP, decay scoring, fingerprinting and a health dashboard; <code>intelligence.py</code> and <code>configuration.py</code> are similarly overloaded. Split along cohesive seams to shrink blast radius and sharpen mutation-gate targeting.
