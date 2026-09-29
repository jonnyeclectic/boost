---
id: project-scope-in-an-unmarked-tree-does-not-walk-up
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: install --local from a subdirectory of an unmarked project creates a second lock there
order: 236
owner:
pr:
title: "Project scope in an unmarked tree does not walk up, so <code>src/</code> becomes its own project"
---
<code>scopes.resolve_base</code> walks up for a VCS marker and, finding none, falls back to the
directory it started in &middot; <em>without</em> walking up. So in a project that is not a git/hg/svn
checkout, every subdirectory is its own project: <code>install brainstorming --local</code> run from
<code>proj/src</code> writes <code>proj/src/.boost/skill-lock.json</code> and <code>proj/src/.claude/skills/</code>,
even when <code>proj/.boost/skill-lock.json</code> already exists; and <code>list --local</code>,
<code>info</code>, <code>doctor</code>, <code>verify</code> and bare <code>uninstall</code> run from
<code>proj/src</code> cannot see what was installed at <code>proj</code>. <code>mkdir .git</code> fixes
both, which is what makes it easy to miss.

This is not the reader/writer split that <code>fix(scope)</code> closed &middot; readers and writers now
agree, and that is the point: they agree on the <em>cwd</em> rather than on the project.
<code>project_root</code>'s docstring says walking up is the whole point ("<code>install --local</code>
run from <code>src/deep/nested</code> must write into the repo's <code>.claude/skills</code>, not create
a stray one three levels down"), and that promise is simply not kept once the marker is absent.

The fix is a choice, not a bug fix, which is why it is its own card. Option (a): make the fallback
walk up for an existing <code>.boost/skill-lock.json</code> &middot; but a lock-file marker cannot
help the very first install, which is the one that creates it. Option (b): let the fallback walk up to
the nearest ancestor that is not <code>$HOME</code> &middot; too greedy, it would swallow unrelated
sibling directories. Option (c): keep today's behaviour and say so &middot; have
<code>install --local</code> warn once when it is about to create a project in a directory with no VCS
marker, naming the directory, so the second lock is a decision rather than a surprise. (c) is the
cheapest and the most honest; (a) is worth pairing with it for every command after the first.

Found by the adversarial verification of PR #998, which reproduced it end to end. <code>$HOME</code>
is still never a project and deletion is still gated by <code>resolve_in_base</code>, so this is a
wrong-directory bug, not a safety one.
