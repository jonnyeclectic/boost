---
id: lint-tap-misscopes-rule-workflow-entries
board: code
section: internals
status: planned
category: Bug
complexity: S
impact: Med
wow: 2
note:
order: 34
owner:
pr:
title: <code>lint --tap</code> mis-scores rule/workflow entries as broken
---
<code>boost lint --tap</code> builds its target list without filtering by kind, so rule/workflow
catalog entries (which have no <code>SKILL.md</code>) always report "missing SKILL.md," and
repo-root items get scored against the entire tap directory instead of their actual file. Running
it against any tap that mixes rules/workflows with skills makes every rule/workflow entry show a
bogus error and a garbage score. Skip or special-case non-skill kinds, mirroring the kind-branching
already used elsewhere in <code>pkg.py</code>.
