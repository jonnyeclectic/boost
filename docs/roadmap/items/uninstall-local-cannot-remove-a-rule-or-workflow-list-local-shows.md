---
id: uninstall-local-cannot-remove-a-rule-or-workflow-list-local-shows
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Med
wow: 3
note: list --local prints the repo's rule; uninstall --local says it is not installed
order: 355
owner:
pr:
title: "<code>uninstall --local</code> cannot remove a rule or workflow that <code>list --local</code> shows"
---
<code>boost install &lt;rule&gt; --local</code> works, and since PR #998 <code>boost list
--local</code> prints the rule it installed. <code>boost uninstall &lt;rule&gt; --local</code>
then exits 1 with &ldquo;<code>&lt;rule&gt; is not installed in this project</code>&rdquo; and the
hint <code>see what is with `boost list --local`</code> &middot; which is the command that just
showed it. There is no way to undo the install through the scope flag that performed it.

The cause is one line: <code>store.uninstall_project</code> (store.py:1291) reads
<code>projectlock.get_skill</code> and nothing else, because a project lock holds a
<code>skills</code> key alone. A rule or workflow installed <code>--local</code> is recorded in
the <em>user</em> lock tagged <code>scope: project</code> with a <code>base</code>, so the
project lock genuinely has no row &middot; but the user lock does, and bare <code>boost
uninstall &lt;rule&gt;</code> finds it and works. So the item is removable; only the flag that
names where it lives is not.

Two candidate fixes, and the choice is a design decision rather than a typo. Either
<code>uninstall_project</code> falls through to the user lock for a row whose <code>scope</code>
is project and whose <code>base</code> is this repo (<code>scopes.owned_by</code> already answers
exactly that question, and is what <code>list --local</code> now uses), or <code>--local</code>
refuses a non-skill with a message that says <em>use bare <code>uninstall</code></em> rather
than claiming the thing is not installed. The first is what a reader expects; the second is one
line. Either way the current message is wrong on its facts, which is the part that must not
survive. A test wants a rule installed <code>--local</code>, asserted present in <code>list
--local</code>, then removed by <code>uninstall --local</code> with the context file checked for
the stripped block. Found while verifying
<code>audit-project-scope-seams-uninstall-verify-list-info-reinstall-dis</code>.
