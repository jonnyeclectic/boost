---
id: mcp-zero-setup-and-three-kinds
board: code
section: dx
status: shipped
owner: loop/mcp-draw
pr: 474
category: Feature
complexity: M
impact: High
wow: 4
note: measured — a fresh install answers every MCP search with "no skills match", which reads as "boost is empty" rather than "nothing is tapped"
order: 12
title: make <code>boost mcp</code> the whole setup, and put all three kinds behind it
---
<b>Measured on a fresh <code>HOME</code>:</b> <code>boost mcp</code> registers the server, and then
the first thing an agent ever asks it — <code>boost_search("set up code review for a python
repo")</code> — comes back <code>no skills match 'set up code review for a python repo'</code>.
Nothing is wrong; nothing is <i>tapped</i>. But the reply is byte-identical to a real miss, so the
agent learns the catalog is empty and stops asking. <code>boost_doctor</code> agrees with it:
<code>taps: 0 (0 skills available)</code> followed by <code>healthy — no issues found</code>. The
one command a new user is told to run leaves the surface it just registered with nothing to answer
from.

<b>Three kinds, one of them unreachable and one invisible.</b> <code>DEFAULT_TAPS</code> is five
skills-first repos: measured, they yield 302 skills and 41 workflows and <b>zero rules</b> — so
the kind whose whole job is steering toward better paths and away from anti-patterns cannot be
found by a default install at all. And a search hit renders as
<code>name — description (tap)</code> with no kind marker, while <code>boost_install</code>'s own
description warns that installing a rule is the more invasive change because it merges into the
context file the agent loads every session. That warning is unactionable: the reply it applies to
never says which hits are rules. Adding one canonical rules repo and one commands/agents repo
takes the default corpus to <b>946 items — 302 skills, 387 workflows, 257 rules</b>, about 14 MB
more than today's five and measured end-to-end at <b>14-45s</b> across runs (it is network-bound,
so quote the range rather than either end of it).

<b>Drawn, not forced — and the research says that is a knife edge.</b> Editing only a tool's
description shifts how often models call it by <b>more than 10×</b> (EMNLP 2025, "Tool Preferences
in Agentic LLMs are Unreliable"), and assertive phrasing, examples and name-dropping are precisely
the capture levers. So the trigger stays a test rather than an order: work that touches more than
one file, or leaves something behind that outlives the session, or that you would name in a commit
message — with the skip list kept in plain sight (a question, a one-line edit, a command you were
handed). The moments worth naming are the ones where a choice gets locked in: a new project or
subsystem, an architecture decision, environment and tooling config, linters, tests, CI. The
existing guardrails hold: no coercive framing, no claimed corpus size, the stated 10-15s cost, and
"the task stays yours" — all of them already pinned by tests.
