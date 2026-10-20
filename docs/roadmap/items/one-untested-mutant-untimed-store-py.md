---
id: one-untested-mutant-untimed-store-py
board: code
section: trust
status: shipped
category: CI · Mutation gate
complexity: S
impact: High
wow: 2
note: one exit-33 mutant dropped store.py's time; the pack ran 3.4x out of balance
order: 376
owner: fix/mutation-headroom
pr: 
title: "One untested mutant erased store.py's measured time, and a balanced pack ran 21.8 to 75+ minutes"
---
On CI run 39357937728 (head <code>525611de</code>, cold cache) the sixteen mutation shards ran
<b>21.8 to 73.4 min</b>, and <code>mutation-shard (14)</code> was cancelled at the 75-minute cap
on two pushes. All of this happened on a pack whose weights agreed to 0.01%, with
<code>plan --explain</code> printing a 29.3-minute median and a 56.0 tail.

<b>The cause was the weights.</b> <code>mutation_shards.py weights</code> records a file's time
only when every mutant has a duration. mutmut gives a mutant with no covering test exit code 33
and never runs it, so that mutant never has a duration. One such mutant in <code>store.py</code>
was enough: the 2026-10-19 refresh (<code>a3092119</code>) committed <code>store.py</code> with no
time. Its 6,592 mutants were imputed at the 2.6 s repo mean, and a new <code>_copy_tree</code>
(120 mutants at a median 72 s, because 97 survive) went unweighted. Shard 12's mutation
phase took 66.7 min, which matches its own measured mutant time / 4 (65.7). The planner had given
it about 24.

<b>Fix.</b> Exit-33 mutants no longer count toward completeness (a <code>None</code> code still
does). The weights were rebuilt from that run, which now times all 68 files (26 <code>_inside</code> mutants that neither source run reached are imputed at store.py's own 7.11 s rate): 136.4M ms, and
<code>store.py</code> alone is 53.1M. <code>FIXED_MINUTES</code> was re-measured cold at 7.1
(median of 15 jobs). The cap went 75 &rarr; 120. <code>_copy_tree</code>'s tail alone is
75.1 min, so no split gets under 75, and at sixteen the pack's tail is 83.0, which is 69% of 120.
Killing <code>_copy_tree</code>'s survivors is what would shrink that unit.
