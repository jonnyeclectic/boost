---
id: autonomous-ship-workflow-and-isolated-worktree
board: code
section: shipped
status: shipped
category: Infra · DX
complexity: L
impact: High
wow: 4
note: 
order: 6
owner:
pr:
title: Autonomous ship-workflow &amp; isolated worktree
---
The loop now runs commit → PR → green CI → squash-merge → release in a
           dedicated <code>~/boost-loop</code> git worktree (own venv for mutmut),
           and modern <strong>git&nbsp;2.55</strong> replaced a 2017 build that
           fatally choked on the global <code>zdiff3</code> config.
