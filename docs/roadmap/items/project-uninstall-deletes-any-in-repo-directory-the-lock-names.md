---
id: project-uninstall-deletes-any-in-repo-directory-the-lock-names
board: code
section: trust
status: shipped
category: Core · Security
complexity: S
impact: Med
wow: 3
note: a materialization path of src/core passes the containment check and is removed
order: 356
owner: loop/uninstall-local-dotdir-guard
pr: 1016
title: "<code>uninstall --local</code> deletes any in-repo directory the committed lock names"
---
<code>store.uninstall_project</code> re-derives every recorded materialization through
<code>scopes.resolve_in_base</code> and refuses anything outside the project &middot; the guard
works, and the verification of PR #998 confirmed a planted victim outside the repo survives every
escape attempt. What it does not check is that the path is an <em>agent skills directory</em>. A
lock row reading <code>{"path": "src/core"}</code> is inside the base, so it passes, and
<code>util.rmtree</code> removes the repo's source tree (store.py:1296-1300).

<code>.boost/skill-lock.json</code> is a committed file: whoever can land a commit can write that
row, and the victim runs one ordinary <code>boost uninstall &lt;skill&gt; --local</code>. That is a
narrower threat than it sounds &mdash; someone who can commit to your repo can also commit a
<code>Makefile</code> &mdash; but this is the one path where the damage happens under a boost
command the user typed, with boost's own containment check having already said yes.

<b>Shipped.</b> <code>store.project_skill_targets(base, name)</code> derives the whole legal set
&mdash; <code>_install_project_skill</code> writes
<code>&lt;base&gt;/&lt;dotdir&gt;/&lt;skills dir&gt;/&lt;name&gt;</code> and nothing else &mdash;
and <code>uninstall_project</code> now asks "is this a path an install writes?" rather than only
"is this inside the repo?". A row that is not in the set is returned in <code>refused</code> and
left on disk; <code>boost uninstall --local</code> names it <em>and prints the derived set
beside it</em>, because the row is in a committed file and a silent survival teaches the user
nothing. Printing the set rather than a <code>&lt;repo&gt;/&lt;agent
dotdir&gt;/skills/&lt;name&gt;</code> shape matters: the leaf comes from the agent's
<code>dir</code>, so for a renamed skills dir the old wording told the user their path was not
one an install writes directly above a shape that path matched.

<b>Two decisions the obvious fix gets wrong.</b> The set is built from
<code>known_agents()</code> filtered on <code>project_scope</code> and deliberately <em>not</em>
on <code>enabled</code>: an agent switched off after the install still has its copy in the repo,
and a legal set that forgot it would trade this delete bug for an orphan bug in the command whose
job is to clean up. And the lock entry is removed even when a row is refused &mdash; otherwise the
one doctored row pins the entry forever and the skill can never be uninstalled.

<b>The leaf name is part of the identity, and so is comparing strings.</b> Matching "under an
agent dotdir" would let <code>.claude/skills/&lt;other skill&gt;</code> through, so <code>boost
uninstall --local a</code> would take <code>b</code> with it. The comparison is against the exact
path, <em>unresolved</em>, and that half is load-bearing too: the legal path is a repo path, so a
commit can make <code>.claude/skills/&lt;name&gt;</code> a symlink to <code>src/core</code> and
file a row of <code>src/core</code>. Resolve both sides and they meet at the victim &mdash; the
whole bug, re-entered through the comparison instead of the containment check.

<b>A path is a string <em>and</em> a place, and the first revision only checked the string.</b>
Set membership is equal <em>by construction</em> when the row is spelled as the legal path, so a
committed <code>&lt;repo&gt;/.claude/skills &rarr; src</code> left the row
<code>.claude/skills/&lt;name&gt;</code> passing every check while denoting
<code>src/&lt;name&gt;</code>: <code>is_dir()</code> follows the ancestor, <code>rmtree</code>
takes the victim, and the probe printed <code>refused=[]</code>. The leaf is honest and the
ancestor is not, which is precisely what a leaf-only guard cannot see &mdash; this card's own bug,
one component up, shipped open in the first revision and found by the verification pass.
<code>scopes.parent_matches_spelling</code> walks the parent for real and compares it against
where the spelling says it should be, anchored on <code>realpath(base)</code>. Both sides real: a
repo can sit <em>under</em> a symlink without containing one &mdash; a checkout below
<code>/tmp</code>, a home behind an automount, a worktree reached through a convenience link
&mdash; and resolving the walk but not the base compares real against nominal, matches nothing,
and refuses every row of that repo. Its test builds the link itself rather than leaning on the
runner's <code>$TMPDIR</code>, which pytest resolves before a test sees it; an earlier draft of
this paragraph claimed the opposite, and re-measuring the table is what caught it.

<b>Three refusal lists, because they need different words.</b> <code>refused</code> is a
contained row that is not a path an uninstall removes here; <code>escaped</code> is one
containment stopped outright, which may well be a path an install writes with the lie in the
filesystem rather than the string; <code>redirected</code> is a row <em>in</em> the derived set
whose walk a committed symlink bends. An escaped row used to fall through every branch to a bare
<code>continue</code> &mdash; no deletion, and no output either, so the most hostile row in the
set was the one that left no trace. A redirected row is worse than silent: folded into
<code>refused</code> it printed "not a path boost removes here" three lines above a list
containing that exact string, because it is in that list <em>by construction</em>. It now says a
symlink redirects the path and prints an <code>rm -rf</code> that works, since <code>rm</code>
follows the ancestor the way the install did.

<b>And that row is where install and uninstall disagree, deliberately.</b>
<code>_install_project_skill</code> gates on <code>scopes.ensure_in_base</code> &mdash;
containment only &mdash; so <code>install --local</code> writes straight through a committed
<code>&lt;repo&gt;/.cursor &rarr; config/cursor</code>, and uninstall then will not delete through
it, leaving boost's own copy behind. The benign layout and the attack are byte-identical on disk,
so nothing distinguishes the intent: creating through a redirect is safe and destroying through
one is not, and that is the right way round. Fixing the install side is
<code>install-writes-through-a-redirected-dotdir-uninstall-will-not</code>. The two tests that
set that layout up are skipped on Windows, where <code>install</code> cannot stage a copy
through a relative directory symlink at all &mdash; the guard is still covered there by the two
ancestor tests, which symlink after the install rather than before it. And the success line is now gated on a count of what actually came off disk, not on
<code>unlinked</code>: an all-refused uninstall printed "removed from &lt;repo&gt;" over an empty
removal, which is the green panel this whole change exists to stop the user trusting &mdash; and
gating it on the <em>agent</em> list then told the same lie backwards, since a lock row need not
name an agent and the delete is not gated on one. It still exits 0, because the lock entry does
go; <code>uninstall</code> has no <code>--json</code>, so the warning lines are the whole signal a
scripted caller gets.

<b>The cost, stated.</b> The legal set comes from <em>this</em> machine's agent table while the
lock is committed and read on others, so config drift refuses a directory a real install wrote:
an agent hand-added on a teammate's machine, or one whose <code>dir</code> was renamed since. The
copy stays in the repo and the lock entry goes, so the user is told by path and has to remove it
by hand. That is deliberate. The alternative that would cover drift &mdash; checking the path's
<em>shape</em> rather than deriving it &mdash; reads the dotdir back out of the lock, which is the
attacker-controlled input the guard exists not to trust.

Related: <code>util-rmtree-chmods-a-symlink-target-outside-the-tree</code>, and
<code>is-dir-follows-a-symlink-at-eleven-rmtree-call-sites</code>, which brought
<code>util.remove_path</code> in. Its
<code>test_a_materialization_naming_a_plain_file_is_left_alone</code> deferred the wider "what may
a lock row name?" question by name, and this change had quietly made that test vacuous &mdash; it
pointed at <code>pyproject.toml</code>, which the new identity check refuses two guards before the
type check it exists to pin. It now names a legal path holding a plain file, so the guard is what
saves the file again.
