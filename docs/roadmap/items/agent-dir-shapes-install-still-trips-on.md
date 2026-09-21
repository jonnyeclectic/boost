---
id: agent-dir-shapes-install-still-trips-on
board: code
section: planned
status: planned
category: Robustness · Bug
complexity: S
impact: Low
wow: 2
note: Four agent-dir shapes a skill install still mishandles after the read-only-home fix; each behaves the same on c7dca95c…
order: 332
owner:
pr:
title: Agent-dir shapes a skill install still trips on: a parent with no search bit, a missing dir under a read-only parent, a blocked agent dropped from the lock's scope
---
<b>Found by the third review of <code>read-only-boost-home-with-no-cache-dir</code>.</b> None is a regression.
Each was measured behaving the same on <code>c7dca95c</code>.

<b>A parent with no search bit.</b> With an agent dir's parent at mode <code>0o600</code>,
<code>store.install</code> copies the skill into the store. It then crashes at exit 70 in
<code>linked_agents</code>, where <code>(adir / name).is_symlink()</code> raises
<code>PermissionError</code> outside <code>link_agents</code>' guard. The store dir is left
unrecorded. Treating an <code>OSError</code> there as "not linked" would close it.

<b>A missing skills dir under a read-only parent.</b> The install names a <code>chmod</code>
target that does not exist, and <code>doctor</code> and <code>heal</code> disagree about it.
<code>link_agents</code>' <code>PermissionError</code> branch should record the block from
<code>paths.refuses_writes(adir)</code> and word it through <code>link_refusal</code>. doctor's
agent-dir check should use the same function, so that it agrees with heal.

<b>A blocked agent drops out of the scope.</b> After an install skips an agent as blocked, the lock's
<code>agents</code> list leaves it out. <code>preserved_agent_scope</code> replays that list, so a
later <code>install --force</code> never retries the agent and never says so. Only
<code>boost sync</code> reports and repairs it.

<b>Callers that drop the result.</b> <code>boost import</code> (<code>install_from_path</code>),
<code>quarantine --release</code> and the unsideline paths (focus, profile, context, team) drop
<code>res.blocked</code> without a word, as they already drop <code>res.unwritable</code>.
<code>pkg._warn_unwritable(res)</code> is the existing reporter.
