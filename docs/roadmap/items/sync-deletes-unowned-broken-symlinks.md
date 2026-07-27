---
id: sync-deletes-unowned-broken-symlinks
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Med
wow: 2
note:
order: 29
owner: loop/sync-symlink-ownership
pr: 273
title: <code>sync --apply</code> deletes any broken symlink, not just boost's own
---
<code>sync_plan</code> flags every broken symlink under an enabled agent dir as stale regardless of
whether it points into boost's store — the <code>points_into_store</code> check only runs on the
live-link branch — and <code>sync_apply</code> unconditionally unlinks everything in
<code>stale_links</code>. A user's own unrelated broken symlink sitting in
<code>~/.claude/skills</code> gets deleted by <code>boost sync --apply</code> with no ownership
check. Only treat a broken symlink as boost-managed if its raw <code>readlink()</code> target
resolves under the store dir. Shipped as <code>store.points_into_store()</code>, applied to
broken and live links alike. Two things turned up while fixing it. <code>boost clean</code>
carried the identical overreach — it unlinked every broken symlink under an agent dir with no
ownership test at all — so it now shares the same helper; fixing only <code>sync</code> would
have left boost contradicting itself. And the original check was a substring test
(<code>str(store_dir) in str(target)</code>), which also matches siblings like
<code>~/.agents/skills-backup</code>; the comparison is component-wise now, and a relative
<code>readlink()</code> target is resolved against the link's own directory before it is judged.
Comparing properly is what exposed a Windows bug the sloppy check had been hiding: since 3.8
<code>os.readlink()</code> there returns the reparse point's substitution path, which carries the
<code>\\?\</code> extended-length prefix, so boost's own link reads back as a
<em>different drive</em> and stopped matching the store at all. Every Windows leg of the matrix
went red on it. The prefix is stripped before comparison, and the behaviour is pinned on every
platform via <code>ntpath</code>, which imports fine on POSIX.
