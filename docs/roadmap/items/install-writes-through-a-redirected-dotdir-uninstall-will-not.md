---
id: install-writes-through-a-redirected-dotdir-uninstall-will-not
board: code
section: trust
status: planned
category: Core · Security
complexity: M
impact: Low
wow: 2
note: install gates on containment and writes through an in-repo symlinked dotdir; uninstall refuses to delete through one, so the copy is orphaned
order: 357
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
