---
id: fix-mcp-tool-parity
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 2
note: boost_doctor, boost_info, boost_list and boost_search disagreed with the CLI about what is installed and whether it is intact
order: 375
owner:
pr:
title: The MCP tools agree with the CLI on install state and skill drift
---
<b>Four MCP replies contradicted the CLI on the same machine.</b> <code>boost_doctor</code>
checked rules and workflows for in-place edits but not skills, so it said "healthy" while
<code>boost doctor</code> flagged a modified skill. <code>boost_info</code> looked up
<code>tap:name</code> unsplit in a lock keyed by bare name and answered "installed: no" right
after <code>boost_install</code> had installed it. It also took its description from whichever
tap sorted first, not the installed one. With nothing installed it did not report an ambiguous
name. And <code>boost_list</code>, <code>boost_info</code> and <code>boost_search</code> never
read the project lock, so a skill installed with <code>--local</code> looked missing to the agent.

<b>The fix puts the shared checks in core, and both surfaces call them.</b>
<code>integrity.skill_modified</code> is the drift test both doctors ask.
<code>integrity.find_installed</code> splits a qualified name, holds the qualifier against the
installed record (<code>catalog.for_tap</code>, moved out of <code>commands/info.py</code>) and
falls back to the project lock. <code>integrity.installed_names</code> unions both locks for the
search marker. <code>boost_info</code> takes its description from the installed tap's catalog row
and raises the same ambiguity error as <code>boost_read</code>.
