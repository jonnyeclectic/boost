---
id: framework-adapters-boost-adapt
board: code
section: dx
status: shipped
category: Interop
complexity: M
impact: Med-High
wow: 4
note: 
order: 40
owner: loop/framework-adapters
pr: 146
title: <code>boost adapt</code> — render a skill as another framework's agent source
---
boost only installs skills as files for editor agents (Claude Code, Cursor, Windsurf); CrewAI / OpenAI-Agents-SDK apps can't consume them — an agent there is a value built in source. <code>boost adapt &lt;skill&gt; --to crewai|agents-sdk</code> renders one <code>SKILL.md</code> into each framework's native <code>Agent(...)</code> as a deterministic, zero-dependency string transform (<code>core/adapters.py</code>). Strings emit via <code>json.dumps</code> so any body (quotes, <code>"""</code>, unicode) stays valid Python; 97.6% mutation kill. Docs: <a href="adapters.html">adapters.html</a>.
