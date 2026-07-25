---
id: mcp-aware-skills
board: code
section: dx
status: shipped
category: Interop · MCP
complexity: L
impact: Med
wow: 4
note: skills that need a server
order: 46
owner: loop/mcp-aware-skills
pr: 235
title: MCP-aware skills — declare and wire an <code>.mcp.json</code> on install
---
Mining boost's catalog surfaces a recurring shape: skills that only work paired
           with a Model Context Protocol server (<code>manage-mcp-servers</code>,
           <code>mcp-integration</code>, <code>mcp-builder</code> and dozens more). boost
           already <em>is</em> an MCP server and registers itself, but a skill could not say
           "I need server Y", so it installed cleanly and then failed in the agent for a
           reason nothing surfaced. Now a skill declares <code>mcp: github, playwright</code>
           in frontmatter and/or bundles a standard <code>.mcp.json</code>; on install boost
           states the requirement and offers to register the servers that came with a
           runnable spec, the same way <code>boost mcp register</code> wires boost itself.
           <code>boost info</code> lists them beside <code>capabilities:</code>, and
           <code>--no-mcp</code> opts out. Deliberately <em>flat</em>, not the nested
           <code>mcp:</code> block first sketched: boost's frontmatter parser is a stdlib
           YAML subset that does not fail loudly on a nested mapping — it hoists the inner
           keys to top level and clobbers their siblings — so the declaration meets the
           parser where it already works and full specs live in the sidecar that needs no
           parser at all. The decision layer is <code>core/mcpdecl.py</code>, pure and
           I/O-free like <code>core/resolve.py</code>.
