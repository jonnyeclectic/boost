---
id: mcp-one-benefit-nameable-task
board: code
section: dx
status: shipped
category: Interop · Adoption
complexity: S
impact: High
wow: 3
note: agent reflex
order: 74
owner:
pr: 355
title: MCP — one benefit, one observable trigger (and stop routing through boost_info)
---
Gemini CLI used the boost MCP server only when asked by hand, never on its own.
Two causes, and neither was fixed by writing more instructions.
<strong>Placement:</strong> Gemini appends a server's <code>initialize</code>
<code>instructions</code> to the <em>GEMINI.md memory tier</em>
(<code>getMcpInstructions</code> → <code>categorizeMemoryContents</code>), gated on
folder trust — so the block reads as background documentation, sits far from the
tool-call decision, and is dropped entirely in an untrusted folder. Claude Code puts
the same text in the system prompt, which is why the gap only showed on Gemini. The
tool descriptions are the only boost text reliably in context at the decision point,
so each now repeats the trigger, the cost and the miss protocol instead of deferring
upward. <strong>Wording:</strong> <a href="#mcp-check-skills-before-starting-a-task">the
previous pass</a> declared three triggers bounded by a proportionality note, and the
bound beat the triggers every time — judging work "non-trivial" takes judgement, while
"this turn looks small" is free, and every turn looks small when it opens. Collapse to
<strong>one</strong> benefit (find a skill for the task in front of you) and
<strong>one observable</strong> trigger (<em>does the task have a name?</em>), which an
agent can pattern-match without deciding anything. Authoring drops from co-equal
trigger to a clause on <code>boost_search</code> — it is the rarer moment and it was
crowding out the common one. Three additions are load-bearing, not padding: the stated
<em>cost</em> (read-only, ~1s, installs nothing) kills the unknown-price hesitation; the
<em>miss protocol</em> ("finding nothing is a good outcome") stops one empty search
teaching an agent to quit checking; and "the task stays yours" is what makes an agent
willing to look, since one that expects a hit to seize the work is safer not looking.
Finally, drop <code>boost_info</code> from the advertised flow — <code>boost_search</code>
already returns each hit's description, the only field that changes an install decision,
so the hop bought a round-trip and a decision point and nothing else. It stays registered
for looking up a name from elsewhere, and its description now says so. All of it is
pinned by tests, including negative assertions so authoring and the info hop cannot
creep back.

<b>Shipped &mdash; the claim was stale, not the work.</b> PR <code>#355</code> merged and its branch
is gone, yet this item still read as owned. Every element is verifiable in
<code>mcp.INSTRUCTIONS</code> today: the stated cost (&ldquo;read-only, take about a second, and
install nothing&rdquo;), the miss protocol (&ldquo;Finding nothing is a good outcome, not a wasted
call&rdquo;), &ldquo;The task stays yours&rdquo;, and <code>boost_info</code> absent from the
advertised flow &mdash; which <code>test_instructions_route_search_straight_to_install</code> pins
with a negative assertion so the hop cannot creep back.
