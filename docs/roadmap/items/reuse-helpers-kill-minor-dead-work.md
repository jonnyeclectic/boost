---
id: reuse-helpers-kill-minor-dead-work
board: code
section: internals
status: planned
category: Tech-debt
complexity: S
impact: Low
wow: 1
note: 
order: 20
owner:
pr:
title: Reuse helpers; kill minor dead work
---
<code>cmd_migrate</code> re-implements agent validation instead of calling <code>_check_agents</code>; <code>_user()</code> is copy-pasted between <code>configuration</code> and <code>team</code>; <code>cmd_simulate</code> parses the same frontmatter twice (<code>pkg.py:38,577 · configuration.py:39 · team.py:30</code>). Small, satisfying cleanups.
