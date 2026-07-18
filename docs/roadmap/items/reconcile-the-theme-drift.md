---
id: reconcile-the-theme-drift
board: code
section: next
status: next
category: Design
complexity: M
impact: Med
wow: 3
note: 
order: 3
owner:
pr:
title: Reconcile the theme drift
---
<code>docs/index.html</code> inlines its own amber/orange palette
           instead of the canonical <em>Aurora</em> cyan→violet→pink system in
           <code>style/boost.css</code>. Move it onto the shared stylesheet so
           one token edit recolours the guide, roadmap, and demo together.
