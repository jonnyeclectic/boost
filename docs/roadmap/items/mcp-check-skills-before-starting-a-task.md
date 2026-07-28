---
id: mcp-check-skills-before-starting-a-task
board: code
section: dx
status: inflight
category: Interop · Adoption
complexity: S
impact: High
wow: 3
note: agent reflex
order: 64
owner: mcp-task-entrance
pr: 318
title: MCP — check for a skill when a task starts, not only when authoring one
---
<a href="#mcp-search-before-reinventing">The previous pass</a> gave the MCP server
<code>initialize</code> <code>instructions</code> and intent-framed tool descriptions, but
framed both around a single trigger: <em>before you author a new skill</em>. That is the
rarer moment. Observed behaviour matched the framing exactly — agents called
<code>boost_search</code> only when they were already about to write a skill, and never to ask
whether an installed one covered the work in front of them. The common case, starting
ordinary work that a vetted skill already handles, had nothing pointing at it.
Broaden to <strong>two</strong> declared triggers: <em>starting a task</em> (call
<code>boost_list</code> for what is usable right now, <code>boost_search</code> for what could
be) and the existing <em>authoring</em> one. <code>boost_list</code> is re-framed from "avoid a
duplicate install" to "leverage a capability you already have" — it is the free half of the
check. A closing proportion note bounds it, because an unbounded <em>always check first</em>
turns every trivial turn into a tool call and an agent that learns to ignore the guidance
ignores all of it. Both triggers and the bound are pinned by tests, so dropping either
regresses.
