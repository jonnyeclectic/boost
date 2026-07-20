---
id: framework-adapter-multi-agent
board: code
section: dx
status: planned
category: Interop
complexity: L
impact: Med
wow: 4
note: 
order: 42
owner: 
pr: 
title: <code>boost adapt</code> — multi-agent skills → crews/graphs, not one Agent
---
Today <code>boost adapt</code> (#146, #163) projects a skill into a <b>single</b> framework Agent carrying its instructions/role/model — but a skill can declare tools and a whole subagent graph (e.g. <code>rust-review</code> = worker + dedup-judge + fp-judge). Adapt the richer structure: emit a CrewAI <code>Crew</code> (agents + tasks) or a LangGraph <code>StateGraph</code> when a skill's frontmatter/plugin dir declares subagents, and surface declared tools as stubs. Scope: detect subagent/tool declarations in <code>SKILL.md</code>/<code>plugins/*/agents/*.md</code>; add a crew/graph renderer path in <code>core/adapters.py</code> (single-Agent stays the default for flat skills); golden + <code>compile()</code> tests + a conformance leg. Turns "one skill → one agent" into "one skill → a runnable multi-agent workflow." See <a href="../adapters.html">adapters.html</a>.
