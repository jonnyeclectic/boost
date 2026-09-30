---
id: is-dir-follows-a-symlink-at-eleven-rmtree-call-sites
board: code
section: trust
status: planned
category: Core · Bug
complexity: M
impact: Med
note: eleven guards use exists() or is_dir(), and both of those follow a link
order: 359
pr:
title: "Eleven <code>util.rmtree</code> call sites guard with <code>exists()</code> or <code>is_dir()</code>, which a symlink satisfies"
wow: 2
---
<code>Path.is_dir()</code> and <code>Path.exists()</code> follow symlinks, so a link pointing at a
directory passes both. Eleven callers use one of them as the guard before
<code>util.rmtree</code>:

<code>registry.py</code> 271, 338, 356, 582 &middot; <code>store.py</code> 1347, 2178 &middot;
<code>bmad.py</code> 656, 693, 794, 814 &middot; <code>pkg.py</code> 958.

Exactly one call site guards correctly &mdash; <code>pkg.py:2195</code>, the snapshot restore, with
<code>child.is_dir() and not child.is_symlink()</code> &middot; so the distinction was known once
and was not applied anywhere else. Exactly one of the eleven,
<code>registry.py:338</code>, sits under <code>suppress(OSError)</code>; the other ten now let the
error out. Six further calls have no existence guard at all
(<code>registry.py</code> 281, 285, 675 &middot; <code>configuration.py</code> 390, 415 &middot;
<code>store.py</code> 129, the last of them suppressed).

<b>An earlier draft of this card said "three", naming only the two in <code>store.py</code> and the
one in <code>pkg.py</code>.</b> That is the whole reason the count is spelled out above: a
follow-up scoped to three would have left eight sites carrying the identical guard. The same draft
attributed <code>pkg.py:958</code> to a <code>boost prune</code> command, which does not exist
&mdash; there is no <code>prune</code> row in <code>cli.COMMANDS</code>; the call is inside
<code>cmd_sync</code> under <code>if args.prune</code>, so the command is
<code>boost sync --prune</code>.

Until the <code>rmtree</code> retry hook was fixed, reaching any of them was silent: nothing was
deleted and the link's target had its mode rewritten outside the tree. The hook now re-raises, so
the same input surfaces as an <code>OSError</code> &middot; the right direction, and still not the
right ending. Demonstrated end to end at <code>registry.py:582</code>
(<code>boost untap</code>) with the tap's clone directory replaced by a link to a directory outside
the tap:

<b>Before:</b> exit 0, tap de-registered, clone left on disk, and the outside directory silently
chmodded 0o755 &rarr; 0o200. <b>After:</b> the same de-registration and the same clone left on
disk, no foreign chmod, but a raw <code>OSError</code> that <code>registry.remove</code> does not
turn into a <code>BoostError</code> &middot; so the CLI writes a crash report and exits 70.

Strictly better on the filesystem and worse to read, and the inconsistent end state &mdash; tap
dropped from <code>config.json</code>, clone still present &mdash; is the same in both and belongs
to <code>registry.remove</code>'s ordering rather than to the guard.

What is missing is a decision about a link that resolves <em>inside</em> the base: remove the link
and count it, or refuse with a message naming the path. The containment layer is not the gap
&mdash; <code>scopes.resolve_in_base</code> refuses a path resolving outside the base, and PR
#998's verification confirmed a planted victim survives every escape attempt byte-for-byte.
Overlaps
<a href="#project-uninstall-deletes-any-in-repo-directory-the-lock-names">project-uninstall-deletes-any-in-repo-directory-the-lock-names</a>,
which owns the wider question of what the lock is allowed to name &middot; whichever lands first
should take the guard with it.
