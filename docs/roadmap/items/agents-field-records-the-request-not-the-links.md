---
id: agents-field-records-the-request-not-the-links
board: code
section: internals
status: shipped
category: Bug
complexity: M
impact: High
wow: 3
note: the lock claimed one agent while three symlinks sat on disk, and every surface said healthy
order: 87
owner: loop/agent-scope-orphan
pr: 437
title: <code>agents</code> recorded the request, not what was linked
---
PR #311 split the lock into two fields and stated the contract in as many words:
<code>only_agents</code> is what the user <i>asked</i> for, and "<code>agents</code> keeps meaning what is
actually linked". <code>install</code> broke the second half. It wrote back
<code>res.linked</code> — only the links <b>that run</b> created — so
<code>boost install X --agent cursor --force</code> on a skill already linked into three agents
recorded a set of one. <code>link_agents</code> <i>skips</i> the agents outside the scope rather than
unlinking them, so all three symlinks stayed on disk: two orphans from one command.

Nothing could see it. The two halves of <code>sync_plan</code> miss it from opposite sides — the
missing-link sweep is narrowed to <code>only_agents</code> so it never visits an excluded agent, and
the stale-link sweep visits every agent dir but keys on the skill <i>name</i> being absent from
the lock. A live, boost-owned link outside a narrowing satisfies neither, so
<code>sync</code> printed "everything in sync"; <code>doctor</code> "0 broken links";
<code>verify</code> "lock file integrity OK"; and <code>health</code> counted the orphan as
<i>coverage</i> and printed a green tick.

For rules and workflows it was worse than invisible — it was <b>irreversible</b>.
<code>_install_rule</code> and <code>_install_workflow</code> rebuild <code>materializations</code>
from scratch, and <code>_uninstall_rule</code>/<code>_uninstall_workflow</code> are driven by that
list rather than by a directory sweep. So a narrowing re-install dropped the row for an agent whose
file it had left in place, and no boost command could ever remove it again: a managed block inside
the user's own <code>~/.claude/CLAUDE.md</code>, or a live slash command, permanently unclaimed.
Skills escaped that only by accident — <code>unlink_agents</code> sweeps every agent dir, so
<code>uninstall</code> cleaned up links the lock had stopped naming.

The fix was one field written wrongly, not a change of semantics: <code>only_agents</code> still
<b>replaces</b> on an explicit <code>--agent</code> (pinned by
<code>test_a_re_narrowing_replaces_the_old_declaration</code>, and untouched), while
<code>agents</code> is now read back off disk by <code>store.linked_agents()</code> — the same
<code>is_symlink()</code> test <code>unlink_agents</code> uses, so what an install records is
exactly what an uninstall will remove. Rules and workflows carry forward the materializations for
agents a run did not write to. The precedent was already in the file: the project-scope skill path
does exactly this eighty lines above, with a comment naming this failure mode
— "dropping them would leave real directories in the repo that no record claims, so uninstall would
skip them and sync would call them orphans".

With the record honest, the divergence becomes reportable. <code>sync_plan</code> gains
<code>out_of_scope_links</code> and <code>doctor</code> names it in one line of pure lock
arithmetic — it has to, because a "healthy" that contradicts the command it tells you to run is
worse than no check. Removal stays behind the existing <code>--prune</code> opt-in: these links
resolve and an agent is using them, so deleting one changes which agents can run a skill, which is
the same class of decision as deleting an orphaned store dir.
