---
id: mcp-already-covered-defeater
board: code
section: dx
status: shipped
category: Interop · Adoption
complexity: M
impact: High
wow: 4
note: every trigger was a predicate over the request; the veto was a predicate over the agent's own context
order: 75
owner: loop/mcp-defeater
pr: 479
title: MCP — answer the veto that overruled the trigger ("a skill already matched")
---
A Gemini CLI session was asked to <i>"create a new, simplified app demonstrating RAG
implementation in Python3 using langGraph, langChain, and langSmith"</i> — a new project, an
architecture decision and a dependency choice, which is <b>three</b> of the triggers
<code>boost_search</code>'s description names explicitly. It activated two already-installed
skills, built the app, and never called boost. Asked why, it paraphrased boost's own lock-in
trigger list back verbatim.

<b>So the trigger fired and was overruled — it did not fail to persuade.</b> That distinction is
the whole card. Every trigger boost ships is a <b>predicate over the request</b>: "has a name",
"touches more than one file", "outlives the session", "a new project or subsystem". All of them
matched. The gate the model actually applied was a <b>predicate over its own context</b>:
<i>something already matched, so I am covered.</i>

That proposition appears nowhere in boost's agent-facing text. Grepped across
<code>INSTRUCTIONS</code> and all six tool descriptions: <code>already have</code> 0 ·
<code>already loaded</code> 0 · <code>already matched</code> 0 · <code>even if</code> 0 ·
<code>even when</code> 0 · <code>enough</code> 0 · <code>sufficient</code> 0 ·
<code>active skill</code> 0. <b>A clause that does not exist cannot have failed</b> — which is why
the fix is a new proposition rather than a louder one, and why "state the trigger more clearly"
was the wrong instinct.

<b><code>boost_list</code> was the amplifier.</b> Its description sold installed items as
"capability you own and may not know you own" — purely inward. An agent that stopped because
something had already matched would, on calling the one free tool, have been told <i>only about
the things it already had</i>. The reply confirmed the belief that suppressed the search.

<b>The fix is a defeater, not a fourth trigger</b> — it sits downstream of the existing gate and
removes a spurious veto, so it cannot widen the check and the skip list is untouched. It says what
an active skill <i>is</i> (installed on an earlier day; matched on its own description — what it
covers, not what this request needs; one kind of three, where a rule you never installed cannot
activate and a workflow waits to be called by name) and leaves the conclusion to the reader.
Two computed lines make the claim arithmetic rather than assertion: a per-kind footer on
<code>boost_list</code> — a machine showing <b>0 rules</b> cannot have loaded the guardrail — and
an overlap note on <code>boost_search</code>, so "none of these is what you already have" is
representable for the first time.

<b>Deliberately excluded: raw catalog totals.</b> An earlier draft printed "the tapped catalog
holds 57,119 skills · 3,016 rules · 11,520 workflows" on every call. Those are un-de-duplicated
index entries, and this repo's own eval work is the refutation — the ranked list de-duplicates on
content hash precisely because 13 distinct skills named <code>code-reviewer</code> collapsing to
one slot was <i>crediting the ranker with a compression that existed only in the scoring code</i>.
It was also the only new text with no bound attached, the closest thing in the surface to a sales
pitch. Cutting it keeps <code>boost_list</code> lock-file-only, so the shipped claim that it is
<b>instant</b> stays true.

<b>Placement is load-bearing, and it is a host fact rather than a preference.</b> The clause is
repeated in <code>boost_search</code>'s <i>description</i> rather than left in
<code>INSTRUCTIONS</code>, because Gemini never delivers server instructions in interactive mode
at all: <code>Config.initialize()</code> does not await <code>mcpInitializationPromise</code>, so
<code>getMcpInstructions()</code> returns <code>""</code>, <code>startChat</code> stamps the
context entry once with a stable id, and the later <code>refreshMcpContext()</code> re-renders
Tier 1 only. The failing session's log carries an empty <code>${environmentMemory}</code> slot and
zero hits for <code>start of server instructions</code>. Claude Code delivers the same text fine.
On Gemini the function declarations are not merely the most reliable carrier — they are the only one.

<b>What this card does not do.</b> It ships on argument, because nothing measures whether an agent
calls a tool; see <code>tool-call-eval-tier</code>. A first-party skill in
<code>~/.agents/skills</code> was spiked as an alternative delivery route and rejected: the roster
rides <code>getCoreSystemPrompt</code> (Tier 0, immune to the race), but a skill's <i>body</i>
only enters context after <code>activate_skill</code> is called, so a defeater placed there fires
only in the worlds where the model was already going to check. The skill does not defeat the
gate; it enters the competition the gate adjudicates.
