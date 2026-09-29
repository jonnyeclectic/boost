---
id: is-dir-follows-a-symlink-at-three-rmtree-call-sites
board: code
section: trust
status: planned
category: Core · Bug
complexity: S
impact: Med
note: Path.is_dir() and .exists() both follow links, so the guard admits a link
order: 359
title: "Three <code>util.rmtree</code> call sites guard with <code>is_dir()</code>, which a symlink satisfies"
wow: 2
---
<code>Path.is_dir()</code> and <code>Path.exists()</code> follow symlinks, so a link pointing at a
directory passes both. Three callers use one of them as the guard before
<code>util.rmtree</code>: <code>store.uninstall_project</code> (<code>not path.is_dir()</code> on a
path the project lock names), <code>store.uninstall</code> (<code>dest.exists()</code> on the
canonical store directory), and <code>boost prune</code> in <code>commands/pkg.py</code>
(<code>target.is_dir()</code>). A fourth, the snapshot restore in the same file, already gets it
right with <code>child.is_dir() and not child.is_symlink()</code> &middot; so the distinction was
known once and was not applied consistently.

Until the <code>rmtree</code> retry hook was fixed, reaching any of the three was silent and
destructive-adjacent: nothing was deleted and the link's target had its mode rewritten outside the
tree. The hook now re-raises, so the same input surfaces as an <code>OSError</code> instead &middot;
which is the right direction and still not the right ending. <code>uninstall_project</code> would
abort mid-loop having removed some materializations and not others, and report a raw
<code>OSError</code> rather than a <code>BoostError</code> with a hint, for a store the user can
actually repair.

The containment layer is not what is missing here. <code>scopes.resolve_in_base</code> refuses a
path that resolves outside the base, and PR #998's verification confirmed a planted victim survives
every escape attempt byte-for-byte. What is missing is a decision about a link that resolves
<em>inside</em> the base: remove the link and count it, or refuse with a message naming the path.
Overlaps
<a href="#project-uninstall-deletes-any-in-repo-directory-the-lock-names">project-uninstall-deletes-any-in-repo-directory-the-lock-names</a>,
which owns the wider question of what the lock is allowed to name &middot; whichever lands first
should take the guard with it.
