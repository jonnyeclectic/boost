---
id: the-agents-line-lists-agents-an-item-does-not-reach
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 2
note: a rule written for 1 of 5 recorded agents still advertises all five in list, info and stats
order: 368
owner:
pr:
title: "The agents line lists every recorded agent, including the ones boost no longer writes"
---
#1040 made an item whose materialization rows are <b>all</b> unwritten read as
<code>unreachable</code>, through <code>integrity.reaches_no_agent</code>. It deliberately left the
partial case, and every surface that names agents still ignores it.

Three readers list each recorded row as an agent the item reaches:

- <code>lockfile.agent_names</code>, which feeds <code>boost stats NAME</code>'s <code>agents</code> line
  (<code>commands/discovery.py</code>) and <code>boost info</code>'s <code>materialized</code> line.
- <code>info._materialized_agents</code>, the <code>AGENTS</code> column of <code>boost list</code>.

None of them asks <code>agents.materialization_is_written</code>. Measured on the #1040 control fixture
(five recorded rows, only <code>cursor</code> enabled): <code>boost doctor</code> says
<em>4 recorded materializations name an agent boost no longer writes</em>, and on the same machine
<code>boost info team-conventions</code> prints
<code>materialized  claude-code, codex, cursor, gemini, windsurf</code>.

<b>Fix:</b> add one helper next to <code>reaches_no_agent</code>, for example
<code>written_agent_names(kind, entry)</code>, that filters rows through the same predicate. Point all
three readers at it so they can't drift apart. A row with no <code>agent</code> key still counts as
written, matching <code>reaches_no_agent</code>. Skills record a flat <code>agents</code> list and stay
as they are.
