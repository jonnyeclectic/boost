---
id: uninstall-has-no-confirmation-prompt
board: code
section: internals
status: planned
category: UX · Bug
complexity: S
impact: High
wow: 3
note:
order: 32
owner:
pr:
title: <code>boost uninstall</code> has no confirmation prompt
---
<code>boost uninstall</code> deletes a skill's store directory and lock entry straight through
<code>shutil.rmtree()</code> with zero confirmation — every other destructive command
(<code>snapshot restore</code>, <code>cohort delete</code>, <code>profile delete</code>,
<code>untap</code>, <code>replay rollback</code>, <code>bmad uninstall</code>) gates on
<code>out.confirm()</code> first. Add the same <code>out.confirm()</code> (bypassable via the
existing <code>BOOST_ASSUME_YES</code>/<code>--yes</code> convention) before the <code>rmtree</code>.
