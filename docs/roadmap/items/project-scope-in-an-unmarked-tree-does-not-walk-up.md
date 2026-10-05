---
id: project-scope-in-an-unmarked-tree-does-not-walk-up
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: (c) shipped; (a) built, reproduced as a regression and withdrawn — it orphans the rules and workflows recorded below the lock it walks up to, and engages for one item kind of three
order: 236
owner: loop/project-scope-walks-up
pr: 1034
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
cheapest and the most honest; (a) looked worth pairing with it for every command after the first.

<b>(c) shipped alone &middot; (a) was built, reproduced as a regression, and withdrawn.</b> The lock
walk exists (<code>scopes.project_lock_root</code>) but is <em>advisory</em>: it lets the warning name
the project above you, and decides no destination. Putting it in the resolution path broke two things
the sketch above did not anticipate. First, <b>it orphans the records below it</b> &middot; a rule or
workflow installed with <code>--local</code> lives in the <em>user</em> lock against an absolute
<code>base</code>, and <code>--local</code> eligibility is <code>scopes.owns</code> against the base
resolved <em>now</em> &mdash; so one <code>install &lt;skill&gt; --local</code> at <code>proj</code>
made a rule at <code>proj/src</code> invisible to <code>list --local</code> and unremovable by
<code>uninstall --local</code>, from <code>proj/src</code> as much as from <code>proj</code>, with the
refusal naming the directory the user was standing in and the two error messages giving mutually
unsatisfiable instructions. Second, <b>it engages for one kind of three</b> &middot;
<code>_install_rule</code> and <code>_install_workflow</code> write no
<code>.boost/skill-lock.json</code> at all, so a tree holding only those never gains the marker, which
is also why the warning (c) adds can never be silenced there. Both are pinned by
<code>test_a_rule_below_an_ancestor_lock_is_still_removable_locally</code>, which fails the moment the
walk is put back. Making the walk safe means giving rules and workflows a project boundary of their
own, and that is a different card.

Found by the adversarial verification of PR #998, which reproduced it end to end. <code>$HOME</code>
is still never a project and deletion is still gated by <code>resolve_in_base</code>, so this is a
wrong-directory bug, not a safety one.
