---
id: sync-repairs-a-disabled-agents-row-every-run
board: code
section: planned
status: planned
category: Robustness · Bug
complexity: S
impact: Low
wow: 1
note: a rule or workflow row for an agent later disabled in config makes sync print "re-materialized" on every run and keeps doctor at rc 1
order: 331
owner:
pr:
title: A rule or workflow row for a disabled agent makes <code>boost sync</code> claim the same repair on every run, and <code>doctor</code> never goes healthy
---
<b>Found while verifying</b> <code>unwritable-rule-or-workflow-dir-crashes-install</code>. A rule
or workflow keeps one materialization row per agent. <code>sync_plan</code> reads every row,
but the repair it runs is an install, and an install writes only to
<code>agents.materializing_agents()</code>. A row for an agent that is no longer enabled is never
written and never cleared, so it is "missing" again on the next run.

<b>Measured</b> in a disposable HOME. Install a rule with <code>~/.cursor/rules</code> at mode 500,
so the Cursor row is recorded as refused, then set <code>agents.cursor.enabled</code> to false. That
is a natural response when the dir was locked on purpose. <code>boost sync</code> then prints
<code>re-materialized rule team-conventions</code> on every run, and <code>boost doctor</code> stays
at rc 1 with "rule team-conventions was not written for cursor … <code>boost sync</code> writes it
once it is", a remedy that cannot work. This is not new with that change. On main, install the
rule, delete the Cursor file, disable Cursor, and run sync twice: it loops the same way for
any missing file of a disabled agent.

<b>Fix sketch:</b> have <code>sync_plan</code> and doctor skip rows for agents outside
<code>materializing_agents()</code> for that row's scope (and say once that the row belongs to a
disabled agent, with <code>boost uninstall</code> or re-enabling as the next step), or have
<code>sync_apply</code> claim a repair only when the rows it meant to fix are actually clean
afterwards. A test should run sync twice and assert the second run is "everything in sync".
