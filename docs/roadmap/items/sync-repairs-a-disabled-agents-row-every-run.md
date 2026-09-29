---
id: sync-repairs-a-disabled-agents-row-every-run
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Low
wow: 1
note: fixed — every check that reads a materialization row now asks first whether boost still writes that agent, so a disabled one is named once instead of reported as rot
order: 331
owner: loop/sync-disabled-agent-rows
pr: 997
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
The same fix must also cover <code>store.unwritable_agent_dirs()</code>, which reads the same
rows: a refused row of a disabled agent keeps its locked dir in doctor's issues and in sync's
warnings, with a <code>boost sync</code> remedy that never writes there.

<b>Shipped.</b> <code>store.materialization_is_written(kind, entry, m)</code> is the one
question every reader now asks: it answers <code>True</code> for a row with no
<code>agent</code> (nothing to test, and reporting a real gap beats silently dropping one),
and otherwise tests the row's agent against the write set for that row's own scope — a
project row against <code>project_agents</code>, not the user-scope set — and against the
narrower <code>workflow_agents</code> for a workflow, since an agent can have a verified
rules format and no command format at all (<code>codex</code> does). Four readers were
wrong in the same way and all four take it: <code>sync_plan</code>'s two loops,
<code>_materialized_dirs</code> (so <code>unwritable_agent_dirs</code> stops naming a
disabled agent's locked dir, whose <code>chmod u+w</code> remedy ends in a write never
attempted), and doctor's three materialization loops.

<b>The row is not dropped</b>, and that is deliberate rather than a shortcut:
<code>_refused_materializations</code> carries untouched rows forward on purpose, because a
rule's row is what makes its managed <code>CLAUDE.md</code> block removable later —
<code>_uninstall_rule</code> is record-driven. So the fix belongs at check time, not at
install time. Doctor says it once, as a <b>note</b> rather than an issue — the user disabled
the agent after installing, which is their decision, and both ways out are theirs to pick:
re-enable the agent and <code>boost sync</code>, or <code>boost uninstall</code> the item to
drop the record. The "fully materialized" count line gained <i>for every enabled agent</i>,
or it reads as a flat contradiction of the note above it.

<b>Verified both directions.</b> Reproduced first on the real CLI in a disposable HOME —
three consecutive <code>boost sync</code> runs each claimed the same repair, and doctor's own
advertised remedy (<code>boost reinstall</code>) left the issue identical, so the fault was
never "sync is slow to converge". Twelve tests cover it (nine unit, three functional),
parametrized over rule and workflow: sync converges on the second run, re-enabling the agent
makes the row repairable again in one run, a refused row's locked dir drops out of doctor and
comes back when the agent does, and a workflow row is judged by the narrower set. Neutering
the helper to <code>return True</code> fails eight of the nine — the ninth is the no-agent
row, whose expected answer is <code>True</code> either way.
