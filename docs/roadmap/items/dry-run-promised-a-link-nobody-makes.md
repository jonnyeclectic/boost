---
id: dry-run-promised-a-link-nobody-makes
board: code
section: internals
status: shipped
category: Correctness
complexity: S
impact: Medium
wow: 3
note: the bug was written down in a test comment and pinned as "behaves today"
order: 100
owner: fix/dry-run-matches-the-real-install
pr: 460
title: install --dry-run predicted an install that never happens
---
<b>A preview has exactly one job, and this one got it wrong by an agent and a verb.</b>
<code>boost install brainstorming --dry-run</code> reported
<code>link&nbsp;&rarr;&nbsp;claude-code&nbsp;&middot;&nbsp;windsurf&nbsp;&middot;&nbsp;cursor&nbsp;&middot;&nbsp;gemini</code>.
The real install reports three agents, plus a separate line saying Gemini reads the store directly
&mdash; and <code>~/.gemini/skills</code> does not exist afterwards, because boost has never created
it.

<b>One list was doing two jobs.</b> The dry-run block computed a single set of targets from
<code>agents.enabled_agents()</code> and printed it for both the skill <code>link</code> line and the
rule/workflow <code>materialize</code> line. For rules and workflows that is right: they really are
materialised into every enabled agent's dotdir, Gemini included. For a <i>skill</i> it is wrong,
because Gemini implements the Agent Skills standard and discovers the canonical store itself, so it
is configured <code>links_skills: false</code> and is deliberately never symlinked. CLAUDE.md is
explicit &mdash; iterate <code>linking_agents()</code> for anything symlink-shaped.

<b>The bug was already written down.</b> The functional test carried a comment saying so:
"<i>the preview lists every enabled agent, so it still promises a gemini link the real install does
not make &hellip; Pinned as it behaves today.</i>" Someone found it, understood it, described it
accurately, and pinned the wrong behaviour rather than fixing it &mdash; which is how a known defect
acquires a test that defends it.

<b>Fixed as a distinction, not a deletion.</b> A skill's preview names the agents that take links and
adds the same "available to Gemini CLI (reads the store directly)" line the real install prints; a
rule's preview still names all four, because a rule genuinely reaches all four. A test now compares
the two runs field by field &mdash; the preview's link list against the real install's &mdash;
because <code>"a&nbsp;&middot;&nbsp;b&nbsp;&middot;&nbsp;c"</code> contains
<code>"a&nbsp;&middot;&nbsp;b"</code>, so a substring assertion passes on exactly this bug. It was
written as a substring first and caught nothing until it was tightened.
