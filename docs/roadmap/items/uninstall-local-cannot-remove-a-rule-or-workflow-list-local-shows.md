---
id: uninstall-local-cannot-remove-a-rule-or-workflow-list-local-shows
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Med
wow: 3
note: shipped — the fall-through, plus a refusal that names where the item really is
order: 355
owner: loop/uninstall-local-rules
pr: 1021
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
survive. Found while verifying
<code>audit-project-scope-seams-uninstall-verify-list-info-reinstall-dis</code>.

<b>Shipped: the fall-through, and the message fixed anyway.</b> Reproduced first — a real
<code>install house-style --local</code> materializes five rows (<code>CLAUDE.local.md</code>,
<code>GEMINI.md</code>, <code>AGENTS.md</code>, <code>.cursor/rules/*.mdc</code>,
<code>.windsurf/rules/*.md</code>), <code>list --local --kind rule</code> prints it, and
<code>uninstall --local</code> exited 1 saying it was not installed.
<code>store.project_materialized</code> now looks the name up in the rule and workflow sections
of the user lock and admits a row only when <code>scopes.owns</code> says this repo claims it;
<code>uninstall_project</code> hands that row to the same
<code>_uninstall_rule</code>/<code>_uninstall_workflow</code> bare <code>uninstall</code> has
always called.

<b>Why those functions get none of the guards the skill path has.</b> Everything in
<code>uninstall_project</code>'s derived-legal-set machinery exists because the <em>project</em>
lock is a committed file — a path out of it is input. The user lock is not committed, and is the
same file bare <code>boost uninstall</code> already reads, so the fall-through adds no path boost
could not already be asked to delete. What <code>--local</code> does is <b>narrow</b>
eligibility, never widen it.

<b>Three details that were not free.</b>
<code>scopes.owns</code> is the single-entry form of the filter <code>list --local</code> uses,
not a second opinion about it — the two commands disagreeing about whose a row is <em>is</em> this
bug.
Ownership is asked of the rule and workflow sections <em>directly</em>, never through
<code>lockfile.find_any</code>, which answers with the first section holding the name: a
user-scope skill called <code>x</code> would outrank a project rule called <code>x</code> this
repo owns, and <code>--local</code> would go on refusing the row <code>list --local</code> shows.
And <code>_remove_all_or_nothing</code> now returns a count of <em>files</em> after its
de-duplication rather than rows. The two agree on the default agent table &mdash; five rows at
five distinct paths, since <code>rules.CONTEXT_FILES</code> gives each context-file agent its
own name at project scope &mdash; and diverge on what the de-duplication exists for: two agents
configured at one dir, or a dotdir symlinked to another. Counting rows there would report a file
removed twice.

<b>The message was useless in two of its three states</b>, which is not the same as wrong: a rule
in the user&rsquo;s own config really is not installed in this project. It reported the one fact
the reader already had and withheld the one they needed, and its hint sent them to
<code>list --local</code>, which correctly shows nothing. Both branches now name where the item
really is: a user-scope rule says so and points at bare <code>uninstall</code>; a row owned by
another checkout names that checkout, and both carry the command that removes it from there. The
genuinely-absent branch is kept byte-identical &mdash; it is the one state where naming where the
item is instead is no help, because it is nowhere.
