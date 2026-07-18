---
id: prune-ignored-dirs-during-scan-dir-walk
board: code
section: internals
status: shipped
category: Performance
complexity: M
impact: Low-Med
wow: 2
note: single os.walk, prune in place, set membership
order: 12
owner: loop/prune-scan-walk
pr: 90
title: Prune ignored dirs during <code>scan_dir</code> walk
---
Two full <code>rglob</code> passes descend <b>into</b> <code>.git</code>/<code>node_modules</code> and only filter afterward, and the skill-dir membership test is O(files × skill_dirs) (<code>catalog.py:106,119–123</code>). Switch to an <code>os.walk</code> that prunes ignored dirs in place; index skill dirs in a set.
