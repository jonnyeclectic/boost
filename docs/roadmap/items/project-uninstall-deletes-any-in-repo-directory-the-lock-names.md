---
id: project-uninstall-deletes-any-in-repo-directory-the-lock-names
board: code
section: trust
status: inflight
category: Core · Security
complexity: S
impact: Med
wow: 3
note: a materialization path of src/core passes the containment check and is removed
order: 356
owner: loop/uninstall-local-dotdir-guard
pr:
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

The fix is to narrow the check from &ldquo;inside the base&rdquo; to &ldquo;inside the base
<em>and</em> under a known agent dotdir&rdquo;: install only ever writes
<code>&lt;base&gt;/&lt;agent dotdir&gt;/skills/&lt;name&gt;</code>, so the set of legal paths is
small, enumerable from <code>agents</code>, and can be derived rather than trusted. Anything else
in the list is skipped with a warning naming the row, not removed. Newly easier to reach than it
was: bare <code>uninstall</code> can now act in an unmarked directory, so a cloned repo carrying a
<code>.boost/</code> no longer needs a VCS marker for the command to find it. Related:
<code>util-rmtree-chmods-a-symlink-target-outside-the-tree</code>.
