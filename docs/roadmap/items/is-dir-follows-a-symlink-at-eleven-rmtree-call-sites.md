---
id: is-dir-follows-a-symlink-at-eleven-rmtree-call-sites
board: code
section: trust
status: shipped
category: Core · Bug
complexity: M
impact: Med
note: eleven guards use exists() or is_dir(), and both of those follow a link
order: 359
owner: loop/rmtree-link-guards
pr: 1007
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

<b>The decision the card left open &mdash; a link that resolves <em>inside</em> the base &mdash;
is settled as "remove the link and count it".</b> A link is a thing the user put there; removing
the link is what every one of these callers meant by "remove what is at this path", and it is what
<code>util.remove_items</code> had been doing correctly all along. The containment layer is
untouched and was never the gap: <code>scopes.contains</code> resolves both sides, so a
materialization pointing out of the project is still refused before anything is removed. A test
plants exactly that and asserts the outside directory survives byte-for-byte &mdash; a regression
guard on the containment layer, not evidence for this fix, since it passes against the old code
too. The test that fails without the change is its sibling, where the link stays <em>inside</em>
the project and so reaches the guard.

<b>Shipped as <code>util.remove_path</code></b> &mdash; unlink a symlink or a file, recurse into a
real directory, return False when there is nothing there. <code>util.remove_items</code> already
had those semantics inline and now calls it, so the helper is a promotion rather than an
invention. <b>Eleven guards are gone and thirteen call sites now go through it</b> &mdash; the
two counts differ and an earlier draft of this paragraph said "twelve guards", conflating them.
The eleven guarded sites are <code>registry.py</code> 271, 338, 356, 582 &middot;
<code>store.py</code> 1347, 2178 &middot; <code>bmad.py</code> 656, 693, 794, 814 &middot;
<code>pkg.py</code> 958. <code>configuration.py:390</code> (<code>boost tap --reclone</code>) is
the twelfth site and had <em>no</em> guard to remove, and the call added in
<code>registry.update</code>'s reclone branch is the thirteenth &mdash; a <em>new</em> call rather
than a swap, so it removes no guard either.

<b>The dangling-link direction turned out to be the half nobody had named.</b> A link whose target
is gone answers False to <em>both</em> <code>exists()</code> and <code>is_dir()</code>, so the
guard skipped it and the link survived &mdash; and the next writer to that path then failed with
<code>FileExistsError</code> for something that "does not exist". That is the shape at
<code>registry.add</code> and at the three <code>bmad</code> sites that clear a destination before
<code>copytree</code> or <code>move</code>.

<b>A fourth instance of the bug lived in <code>registry.update</code>, and it was the only one
with no way out.</b> <code>Tap.is_cloned</code> is <code>self.path.is_dir()</code>, which a dangling
link answers False to &mdash; so a tap whose clone was symlinked to a checkout that later moved
lands in the <code>elif not tap.is_cloned</code> branch, where <code>gitutil.clone_shallow</code>
was called with nothing in front of it &mdash; the branch reached precisely <em>because</em> the
path reads as absent, which is why a dangling link is the one input that breaks it. Git refuses to clone onto an existing link, so
<code>boost update</code> failed, <code>boost doctor</code> reported the tap not cloned and pointed
the user at <code>boost update</code>, and the loop closed. It now removes the path first.

<b><code>registry.remove</code> also got the catch-and-warn its own cache-file line already had.</b>
The ordering described above is why: config is saved before the delete, so an unhandled error
exited 70 with the tap de-registered and its clone still on disk, and nothing left pointing at the
directory. It now warns and names the path, exactly as the line below it does for the cache file.

Left alone deliberately: <code>store._remove_backup</code>, which hand-rolls the same
is-symlink-first shape but with <code>ignore_errors=True</code> semantics that
<code>remove_path</code> does not have; and the six calls with no existence guard, which do all
act on a directory the same function just created &mdash; <code>registry.py</code> 281, 285, 675
&middot; <code>configuration.py</code> 415 &middot; <code>store.py</code> 129, the last
suppressed. <b>An earlier draft of this paragraph claimed that description fitted only five of
them</b>; it fits all six. The thirteenth site is not one of them recategorised &mdash; it is a
call that did not exist before, added where <code>clone_shallow</code> had nothing in front of it
at all. Overlaps
<a href="#project-uninstall-deletes-any-in-repo-directory-the-lock-names">project-uninstall-deletes-any-in-repo-directory-the-lock-names</a>,
which still owns the wider question of what the lock is allowed to name.
