---
id: sync-relinks-into-every-agent-ignoring-scope
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Med
wow: 2
note: the half of the scope leak PR #288 deliberately left open
order: 34
owner: loop/sync-agent-scope
pr:
title: <code>sync</code> relinks a narrowed skill into every agent
---
<code>store.preserved_agent_scope</code> (PR #288) stopped <code>update</code> and
<code>reinstall</code> widening a skill installed with <code>--agent</code> narrowing, but
<code>sync_plan()</code> was a second, independent path to the same leak: it walked
<code>agents.enabled_agents()</code> for <b>every</b> locked skill and reported a
<code>missing_link</code> for any agent the skill was not linked into — the lock's recorded
scope was never consulted. <code>sync_apply</code> then dutifully linked them, so a
single <code>boost sync</code> undid the narrowing that <code>install --agent</code> asked for and
rewrote the lock to match.

It was left out of #288 because the fix is a real trade-off, not an oversight:
<code>boost sync</code> is also how a <i>newly enabled</i> agent picks up skills installed
before it existed, and honouring the lock's <code>agents</code> list would silently break that —
<code>agents</code> records what is linked <i>right now</i>, so reading it as a scope would
freeze every existing skill out of any agent enabled later.

Resolved by separating the two questions. A new <code>only_agents</code> field records what the
user <i>asked</i> for, written only by an explicit <code>--agent</code> and carried forward across
<code>update</code>/<code>reinstall</code>; <code>agents</code> keeps meaning what is actually linked.
<code>sync_plan</code> filters through <code>scoped_agents()</code>, which <b>fails open</b> — an entry
with no declaration, which is every entry written before this field existed, still fans out to
every enabled agent. So narrowing is honoured and the newly-enabled-agent path is untouched.
