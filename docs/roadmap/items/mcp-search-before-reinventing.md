---
id: mcp-search-before-reinventing
board: code
section: dx
status: inflight
category: Interop · Adoption
complexity: S
impact: High
wow: 3
note: agent reflex
order: 44
owner: loop/mcp-discover
pr: 
title: MCP — make agents search boost before reinventing a skill
---
The boost MCP server returned no <code>initialize</code> <code>instructions</code> and described its tools by boost's nouns (<em>"Search AI coding skills across the configured tap registries"</em>), so an agent mid-task never mapped <em>"I'll write a code-review workflow"</em> onto <em>"search boost first"</em> — and reinvented the wheel. Add server-level <code>instructions</code> (the field MCP hosts load into the agent's context) framed by the agent's trigger — <em>before you author a reusable skill / rule / subagent, call <code>boost_search</code> FIRST</em> — and rewrite the six tool descriptions to lead with that trigger and a "don't reinvent one that already exists" frame. Follow-up: a self-bootstrapping <code>boost-first</code> meta-skill that <code>boost mcp register</code> / <code>onboard</code> offers to install.
