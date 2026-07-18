---
id: crash-recorder-error-paths-core-logs-py
board: code
section: shipped
status: shipped
category: Testing · Resilience
complexity: S
impact: Med
wow: 3
note: 7 branches · 88%→100%
order: 5
owner:
pr:
title: Crash-recorder error paths — <code>core/logs.py</code>
---
The black-box diagnostic logger swallows every filesystem/handler
           failure so a broken log can never break the CLI — but those
           <code>except</code> arms (the parts that matter most <em>during</em> a
           crash) were the least exercised. New tests force each failure —
           handler <code>close()</code> raising, a read-only log dir, an
           unresolvable version, a wedged logger, <code>unlink</code> denied —
           taking the module to <strong>100%</strong> coverage.
