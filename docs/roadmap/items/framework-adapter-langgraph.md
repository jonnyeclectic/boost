---
id: framework-adapter-langgraph
board: code
section: dx
status: planned
category: Interop
complexity: M
impact: Med
wow: 3
note: 
order: 41
owner: 
pr: 
title: <code>boost adapt --to langgraph</code> — third framework renderer
---
Extend <code>boost adapt</code> (shipped in #146) with a LangGraph target. Unlike CrewAI / Agents-SDK, a LangGraph agent isn't one <code>Agent(...)</code> constructor — the skill body is the system prompt of a node bound into a <code>StateGraph</code>. Add a <code>render_langgraph</code> to <code>core/adapters.py</code> emitting a node factory (prebuilt <code>create_react_agent</code>, or a prompt-carrying node) + its <code>FORMATS</code> row, with byte-exact golden + <code>compile()</code> tests. Then add a <code>langgraph</code> leg to <code>.github/workflows/adapter-conformance.yml</code> (pip install langgraph, import the emitted file). Follows the pattern in <a href="../adapters.html">adapters.html</a>: one <code>render_*</code> fn + registry row + golden test + one matrix line.
