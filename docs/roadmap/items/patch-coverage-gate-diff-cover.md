---
id: patch-coverage-gate-diff-cover
board: code
section: pipeline
status: shipped
category: Testing · Gap
complexity: S
impact: Med
wow: 2
note: self-hosted
order: 8
owner: loop/patchcov
pr: 183
title: Patch-coverage gate — <code>diff-cover</code>
---
Enforce coverage on the <em>changed lines</em> of each PR — no external
           service needed, it reads the same <code>coverage.xml</code> the suite
           already emits. Pairs with the 80% project gate so new code can't quietly
           ride in under-tested behind an already-high overall number.
