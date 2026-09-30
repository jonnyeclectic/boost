---
id: util-rmtree-chmods-a-symlink-target-outside-the-tree
board: code
section: trust
status: inflight
category: Core · Bug
complexity: S
impact: Med
wow: 3
note: the read-only retry hook follows a symlink and chmods the file it points at
order: 237
owner: loop/rmtree-symlink-hook
pr: 1003
title: "<code>util.rmtree</code>'s retry hook <code>chmod</code>s a symlink's target, outside the tree it is deleting"
---
<code>util.rmtree</code> installs an error handler so a read-only file cannot strand a delete: on
failure it <code>chmod</code>s the path and retries. The handler is handed the path that failed, and
when that path is a <em>symlink</em> the <code>chmod</code> follows it &middot; so deleting a
directory that happens to contain a link to a file elsewhere changes that file's permissions.

Measured, because the first draft of this card guessed at the shape and guessed wrong. The hook only
fires once a delete has already <em>failed</em>, and unlinking a symlink does not fail while its
parent directory is writable &middot; so in the ordinary case nothing happens at all: the link goes,
the target keeps its mode byte-for-byte. Make the parent read-only (<code>0o500</code>) and the
unlink fails, the hook <code>chmod</code>s the link, the target outside the tree goes
<code>0o400</code> &rarr; <code>0o200</code>, the retry fails again and <code>rmtree</code> raises.
The link is still there. So the only lasting effect of the hook on this path is the permission
change on a file it was never asked to touch &middot; the earlier claim that &ldquo;the delete
itself correctly removes only the link&rdquo; describes a run in which the hook never fires.

The containment guards do their job: <code>scopes.resolve_in_base</code> and <code>contains</code>
still refuse to remove anything outside the base, and the verification of PR #998 confirmed a planted
victim file survives every escape attempt byte-for-byte. What is not guarded is the
<em>permission change</em> on the way past, which happens before containment is ever consulted
because it is inside the retry hook.

Pre-existing and untouched by the project-scope work, but newly easier to reach: bare
<code>uninstall</code> can now act in an unmarked directory, so a repo copy that carries a symlink
into the user's home is one command away. The fix is small &middot; use
<code>os.chmod(..., follow_symlinks=False)</code> where the platform supports it, and otherwise skip
the retry entirely for a path that <code>os.path.islink</code> reports, since a symlink's own mode is
not what blocked the unlink. A test wants a link inside the tree pointing at a
<code>0o400</code> file outside it, asserting the target's mode is unchanged after the delete.

<b>Implementing it turned up a second, worse instance of the same bug, which this card did not
know about.</b> Hand <code>util.rmtree</code> a symlink <em>as its argument</em> and
<code>shutil.rmtree</code> refuses it by calling the error hook with <code>func</code> set to
<code>os.path.islink</code>. The old hook chmodded straight through the link and then called
<code>os.path.islink(path)</code>, which answers True without raising &middot; so the hook returned,
<code>rmtree</code> returned, and the caller was told a tree had been removed when nothing had.
Measured: link intact, target directory intact with its contents, target's mode 0o755 &rarr; 0o200.
Silent, and independent of any 0o500 &mdash; the first variant at least raises.

<b>The repair the card proposed was the wrong one.</b>
<code>os.chmod(..., follow_symlinks=False)</code> needs <code>lchmod</code>, which
<code>os.supports_follow_symlinks</code> does not report everywhere this runs (measured True on
darwin), so it buys a platform branch that cannot be exercised on the runner &mdash; an unkillable
mutant by construction. It is also treating a mode that was never the blocker: unlinking is gated by
the parent directory's write bit, not the link's own mode, which is why the retry fails a second
time in the first variant. Re-raising the exception the hook was handed is correct on both counts
and needs no branch.
