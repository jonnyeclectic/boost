---
id: sync-deletes-unowned-broken-symlinks
board: code
section: internals
status: planned
category: Bug
complexity: S
impact: Med
wow: 2
note:
order: 29
owner:
pr:
title: <code>sync --apply</code> deletes any broken symlink, not just boost's own
---
<code>sync_plan</code> flags every broken symlink under an enabled agent dir as stale regardless of
whether it points into boost's store — the <code>points_into_store</code> check only runs on the
live-link branch — and <code>sync_apply</code> unconditionally unlinks everything in
<code>stale_links</code>. A user's own unrelated broken symlink sitting in
<code>~/.claude/skills</code> gets deleted by <code>boost sync --apply</code> with no ownership
check. Only treat a broken symlink as boost-managed if its raw <code>readlink()</code> target
resolves under the store dir.
