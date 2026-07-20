---
id: update-diff-before-apply
board: code
section: trust
status: inflight
category: Security · Supply chain
complexity: M
impact: Med
wow: 3
note: no silent overwrites
order: 5
owner: loop/update-diff-gate
pr:
title: Update-diff before apply
---
<code>boost update</code> overwrites installed skills in place. Show a
           content diff of what an upstream change alters — and require confirmation
           for anything that touches executable-looking instructions — so a poisoned
           update is <em>visible</em> instead of silent. The "review the diff" gate,
           applied to skills.
