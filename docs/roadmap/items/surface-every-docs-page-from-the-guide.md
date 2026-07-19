---
id: surface-every-docs-page-from-the-guide
board: code
section: docsite
status: planned
category: Docs · Discoverability
complexity: S
impact: Med
wow: 2
note:
order: 11
owner:
pr:
title: Surface every <code>docs/*.html</code> page from the main page
---
<a href="make-the-roadmaps-discoverable.html">Making the roadmaps discoverable</a>
           put both boards in the Visual Guide nav, but the same gap remains for
           the rest of <code>docs/*.html</code>: <code>mcp-hub.html</code> is
           reachable only if you already know the URL — nothing on
           <code>index.html</code> links to it. Add a nav entry for every shipped
           doc page (today just the MCP Hub, beside <code>Roadmap&nbsp;↗</code> /
           <code>Design&nbsp;↗</code>) so no page is an orphan, and treat "a new
           <code>docs/*.html</code> means a new nav link" as the standing rule —
           ideally checked in CI so a future page can't ship unlinked.
