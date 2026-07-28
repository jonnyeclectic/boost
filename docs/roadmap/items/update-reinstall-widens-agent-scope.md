---
id: update-reinstall-widens-agent-scope
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Med
wow: 2
note:
order: 33
owner: loop/keep-agent-scope
pr: 288
title: <code>update</code>/<code>reinstall</code> silently widen a skill's agent scope
---
A skill installed with <code>--agent</code> narrowing (e.g. <code>boost install foo --agent
claude-code</code>) records that subset in the lock, but <code>boost update</code>/
<code>boost reinstall</code> force-reinstall via <code>store.install(entry, force=True)</code>
without passing <code>only_agents</code> — so <code>link_agents</code> relinks into every currently
enabled agent and silently overwrites the lock's narrower agent list. Pass
<code>only_agents=lk.get("agents")</code> on both force-reinstall paths, matching what the
rule/workflow update path already does for scope.
