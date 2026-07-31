---
id: mcp-check-skills-before-starting-a-task
board: code
section: dx
status: shipped
category: Interop · Adoption
complexity: S
impact: High
wow: 3
note: agent reflex
order: 64
owner:
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

<b>Shipped &mdash; the claim was stale, not the work.</b> PR <code>#318</code> merged and its branch
is gone, but this item sat at <code>inflight</code> under that branch name, so the board advertised
live work as taken. Verified against the code rather than the PR state alone:
<code>mcp.INSTRUCTIONS</code> leads with using an installed skill, names <code>boost_list</code> for
what is usable right now, and carries the proportion bound this card asks for &mdash; &ldquo;Skip it
for a question, a one-line edit, or a command you were just handed.&rdquo; The trigger is pinned by
<code>test_instructions_lead_with_using_a_skill_not_authoring_one</code>.

One note for anyone reading both cards: <code>mcp-one-benefit-nameable-task</code> (<code>#355</code>,
later) <em>superseded</em> this card's &ldquo;two declared triggers&rdquo; framing by demoting
authoring to a clause on <code>boost_search</code>, on the grounds that it was the rarer moment
crowding out the common one. The task-start trigger this card argued for is what survived.
