---
id: uninstall-has-no-confirmation-prompt
board: code
section: internals
status: shipped
category: UX · Bug
complexity: S
impact: High
wow: 3
note:
order: 32
owner: loop/uninstall-confirm
pr: 266
title: <code>boost uninstall</code> has no confirmation prompt
---
<code>boost uninstall</code> deletes a skill's store directory and lock entry straight through
<code>shutil.rmtree()</code> with zero confirmation — every other destructive command
(<code>snapshot restore</code>, <code>cohort delete</code>, <code>profile delete</code>,
<code>untap</code>, <code>replay rollback</code>, <code>bmad uninstall</code>) gates on
<code>out.confirm()</code> first. Shipped: a single prompt naming every skill about to go,
before anything is touched, plus <code>-y/--yes</code> and the existing
<code>BOOST_ASSUME_YES</code> bypass.
<strong>The prompt is gated on <code>sys.stdin.isatty()</code>, not just on the flag.</strong>
<code>out.confirm()</code> returns its <code>default</code> — <code>False</code> — when stdin is
not a terminal, so the obvious <code>if not out.confirm(...)</code> would have turned
<code>boost uninstall x</code> in every CI step, Makefile and Dockerfile into a silent no-op
exiting 1. Guarding a destructive command must not break the callers that cannot see the
guard; a regression test drives the command with a non-TTY stdin and no
<code>BOOST_ASSUME_YES</code> to hold that line.
