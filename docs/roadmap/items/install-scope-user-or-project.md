---
id: install-scope-user-or-project
board: code
section: internals
status: inflight
category: Install engine · UX
complexity: M
impact: High
wow: 3
note: rules/workflows were user-global only
order: 27
owner: loop/install-scope
pr:
title: <code>boost install --scope user|project</code> for rules/workflows
---
Rule and workflow install always materialized into user-global agent config
           (<code>~/.claude/CLAUDE.md</code>, <code>~/.cursor/rules</code>, …), so a
           rule meant for one repo leaked into every session. Add
           <code>--scope project</code>: materialize into the current repo instead —
           <code>&lt;repo&gt;/.cursor/rules/</code>, <code>&lt;repo&gt;/.claude/commands|agents/</code>,
           and, since Claude reads per-repo memory from the root and has no rules
           folder, <code>&lt;repo&gt;/CLAUDE.local.md</code> (the personal, git-ignored
           file). The chosen scope + base dir are recorded in the lock so
           <code>update</code>/<code>sync</code> re-materialize back into the same
           repo rather than wherever they happen to run. Default stays
           <code>--scope user</code> (unchanged behavior). Uninstall already reverses
           by recorded path, so it works for either scope.
