---
id: mcp-hub-diagram-node-text-overflow
board: code
section: docsite
status: planned
category: Docs · Visual polish
complexity: S
impact: Low
wow: 2
note: read_body→chunk node clips its 3rd line
order: 12
owner:
pr:
title: Fix overflowing node text in the RAG diagram (<code>mcp-hub.html</code>)
---
On the Fig 2 RAG-pipeline diagram, the <code>read_body → chunk</code> node
           overflows its rounded box: the third caption line
           (<code>1000 chars · 150 overlap · ≤40…</code>) runs past the node's
           right border and is clipped where the pink <em>embed</em> arrow begins.
           Give the node room so all three lines sit inside the bubble — widen its
           min-width, wrap or shrink the caption, or trim the label text — and
           re-check the other nodes at the same breakpoint so none clip.
