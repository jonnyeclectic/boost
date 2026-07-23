---
id: workspace-scope-install
board: code
section: internals
status: shipped
category: Install engine · Scope
complexity: L
impact: High
wow: 4
note: --local, committable repo lock
order: 22
owner: loop/workspace
pr: 211
title: Workspace scope — <code>boost install --local</code> into the project
---
boost was user-global by construction: one store at
           <code>~/.agents/skills</code>, symlinked into every home-level agent
           dir. Right for the skills <em>you</em> use everywhere, wrong for the
           ones a <em>team</em> agrees on. Shipped the npm
           <code>--save</code> half: <code>boost install &lt;skill&gt; --local</code>
           (<code>= --scope project</code>) writes into the repo's own
           <code>.claude/skills/</code>, <code>.cursor/skills/</code>, … and
           records a committable per-repo lock at
           <code>.boost/skill-lock.json</code>. Real directories, never
           symlinks — a link into the author's <code>~/.agents/skills</code>
           arrives dangling on a teammate's machine, which is the exact problem
           committing skills is meant to solve. Two separate locks, because
           ~40 call sites resolve a locked skill to
           <code>~/.agents/skills/&lt;name&gt;</code>, which a project skill does
           not have. Scope resolution walks up for the nearest project root, so
           installing from <code>src/deep/nested</code> lands in the repo instead
           of scattering a <code>.claude/</code> three levels down;
           <code>list --local</code>, <code>uninstall --local</code> and
           <code>sync</code> all understand both scopes, and <code>sync</code>
           re-materializes what a fresh clone is missing while never deleting a
           directory boost did not write.
