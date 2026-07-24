---
id: split-oversized-command-modules
board: code
section: internals
status: inflight
category: Maintainability
complexity: L
impact: Med
wow: 2
note: 
order: 15
owner: loop/split-cmds
pr:
title: Split oversized command modules
---
<code>quality.py</code> (15 cmds / 1,264 lines) mixes audit regexes, conflict NLP, decay scoring, fingerprinting, a health dashboard and now tap-provenance; <code>intelligence.py</code> and <code>configuration.py</code> are similarly overloaded. Split along cohesive seams to shrink blast radius. First seam: lift the safety/integrity/provenance commands (<code>audit</code>, <code>verify</code>, <code>attest</code>, <code>quarantine</code>, <code>trust</code>) into their own module with a shared helper module.
