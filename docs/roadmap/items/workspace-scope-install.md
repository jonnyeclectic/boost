---
id: workspace-scope-install
board: code
section: internals
status: planned
category: Install engine · Scope
complexity: L
impact: High
wow: 4
note: --global vs --local, project .claude/
order: 22
owner:
pr:
title: Workspace scope — <code>boost install --local</code> into the project
---
boost is user-global only: the store is <code>~/.agents/skills</code> and every
           install symlinks into home-level agent dirs (<code>~/.claude/skills</code>,
           <code>~/.cursor/skills</code>, <code>~/.windsurf/skills</code>). There is
           no per-project scope — <code>install</code> takes <code>--agent</code>
           (which agents) but no <code>--global</code>/<code>--local</code>. Add a
           workspace paradigm mirroring <code>npm</code> (local vs
           <code>-g</code>): <code>boost install &lt;skill&gt; --local</code> writes
           into the current repo's <code>.claude/skills/</code> (and the other
           agents' project dirs), and — paired with rule install — merges a rule
           into the project's <code>./CLAUDE.md</code> rather than the global one,
           so a team can commit its skills and rules with the repo. Needs a
           per-scope store/lock, scope resolution (walk up for the nearest
           project root), and <code>list</code>/<code>sync</code>/<code>uninstall</code>
           that understand both scopes.
