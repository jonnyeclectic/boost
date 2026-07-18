---
id: pre-release-python-canary-3-14t-free-threaded
board: code
section: compat
status: planned
category: Compat · Python
complexity: S
impact: Med
wow: 3
note: continue-on-error
order: 4
owner:
pr:
title: Pre-release Python canary — 3.14t free-threaded
---
An allow-failure matrix leg on Python pre-releases and the free-threaded
           (no-GIL) build gives early warning of breakage before users on new
           interpreters hit it. Cheap insurance for a project that already targets
           3.9&nbsp;→&nbsp;3.14 and can't afford a surprise on release day.
