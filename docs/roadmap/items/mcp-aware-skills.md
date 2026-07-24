---
id: mcp-aware-skills
board: code
section: dx
status: planned
category: Interop · MCP
complexity: L
impact: Med
wow: 4
note: skills that need a server
order: 46
owner:
pr:
title: MCP-aware skills — declare and wire an <code>.mcp.json</code> on install
---
Mining boost's catalog surfaces a recurring shape: skills that only work paired
           with a Model Context Protocol server (<code>manage-mcp-servers</code>,
           <code>mcp-integration</code>, <code>mcp-builder</code> and dozens more). boost
           already <em>is</em> an MCP server and registers itself, but a skill can't say
           "I need MCP server Y," and boost can't help install or wire other servers.
           Let a skill declare an <code>mcp:</code> block (or bundle an <code>.mcp.json</code>)
           in its frontmatter; on install, boost offers to register that server into the
           agent the same way <code>boost mcp register</code> wires boost itself. Extends
           the "search boost before reinventing" reflex from skills to the MCP tools a
           skill depends on, and pairs naturally with the <code>requires:</code> resolver.
