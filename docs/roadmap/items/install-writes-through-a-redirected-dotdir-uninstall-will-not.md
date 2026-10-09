---
id: install-writes-through-a-redirected-dotdir-uninstall-will-not
board: code
section: trust
status: shipped
category: Core · Security
complexity: M
impact: Low
wow: 2
note: install now refuses a target uninstall would refuse — same predicate both sides; doctor names rows a later symlink redirected
order: 357
owner: loop/install-redirected-dotdir
pr: 1056
title: "<code>install --local</code> writes through a redirected dotdir that <code>uninstall --local</code> will not remove"
---
A repo that commits <code>&lt;repo&gt;/.cursor &rarr; config/cursor</code> &mdash; an ordinary
dotfile layout, not an attack &mdash; gets two different answers from the two halves of the same
command. <code>_install_project_skill</code> gates its target with
<code>scopes.ensure_in_base</code>, which is containment only, so <code>boost install --local</code>
writes <code>config/cursor/skills/&lt;name&gt;</code> and records the row it spelled,
<code>.cursor/skills/&lt;name&gt;</code>. <code>boost uninstall --local</code> then refuses that row,
because <code>scopes.parent_matches_spelling</code> walks the parent for real and finds the
redirect. Boost's own copy is left on disk and the lock entry goes anyway, so a second uninstall
answers <em>not installed in this project</em>.

Reproduced on the commit that introduced the guard: install wrote through the symlink, uninstall
reported the row as <code>redirected</code>, and the directory survived.

<b>The uninstall side is right and is not the thing to change.</b> The benign layout and the attack
are byte-identical on disk: <code>.claude/skills &rarr; ../src</code> with a legally-spelled lock row
is the same two objects in the same two places, and nothing in the filesystem carries the intent
behind them. Creating through a redirect is safe; destroying through one hands an attacker with
merge rights an <code>rmtree</code> aimed wherever the symlink points. So the asymmetry stays, and
<code>uninstall</code> now names the row, says a symlink redirects it, and prints an
<code>rm -rf</code> that works &mdash; because <code>rm</code> follows the ancestor exactly as the
install did (shipped in #1016).

What is left is the other half: <b>install should not write somewhere uninstall cannot reach.</b>
The options are not equivalent and the choice needs measuring rather than guessing &mdash; refuse
the install outright (safe, breaks a layout that works today); record the <em>resolved</em> path in
the lock so uninstall's walk agrees (keeps the layout, but the lock then carries a path the repo
never spells, and a teammate whose clone resolves differently gets a row that matches nothing); or
record both and match on either (most forgiving, widest attack surface to re-audit). Whichever
lands, <code>boost doctor</code> should report a project whose lock rows no longer resolve to where
the install put them, since today nothing notices until an uninstall leaves a directory behind.

Related: <code>project-uninstall-deletes-any-in-repo-directory-the-lock-names</code>, which added
the walk and the <code>redirected</code> reporting this card inherits.

<b>Shipped: install refuses.</b> Of the three options, two loosen the delete guard: a resolved
row (<code>config/cursor/skills/&lt;name&gt;</code>) is outside the set
<code>project_skill_targets</code> derives, so uninstall would report it <code>refused</code> unless
it started resolving &mdash; the hole its docstring names &mdash; and recording both widens that
further. Refusing is the only option that leaves uninstall untouched, and it makes the two halves ask
one question: <code>scopes.ensure_spelled</code> calls the same
<code>parent_matches_spelling</code> uninstall does, in the up-front loop beside
<code>ensure_in_base</code>, so a redirected agent aborts the install before any copy or lock row is
written. The hint names the two ways out: replace the symlink with a real directory, or leave that
agent out with <code>--agent</code>. A symlink <em>above</em> the repo is still fine &mdash; the
walk anchors on the real base.

Measured on the card's layout (<code>.cursor &rarr; config/cursor</code>, cursor enabled): before,
<code>install --local</code> wrote <code>config/cursor/skills/brainstorming</code>, uninstall left it
and dropped the row, and a second uninstall answered <em>not installed in this project</em>; after,
install exits 1 naming <code>.cursor/skills/brainstorming</code> and its real target, and nothing is
written under the repo. <code>boost doctor</code> now flags a project row whose walk is redirected
(<code>integrity.project_redirected</code>) &mdash; a lock written before this, or a symlink committed
after an install &mdash; which <code>project_status</code> reported intact because the hash follows
the link.
