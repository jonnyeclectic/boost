---
id: post-deploy-smoke-headless-load-check
board: code
section: docsite
status: planned
category: Testing · Docs
complexity: M
impact: Med
wow: 3
note: catches red deploys
order: 9
owner:
pr:
title: Post-deploy smoke — headless load check
---
After each Pages deploy, headless-load the guide and roadmap and assert
           the essentials: HTTP 200, every asset resolves, and the console is free
           of errors. Distinct from the planned visual-regression pass — this is a
           cheap always-on health gate that would have caught the current broken
           Pages deploy automatically.
