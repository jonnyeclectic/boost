---
id: invocation-pid-logging-for-crash-correlation
board: code
section: shipped
status: shipped
category: Observability · Diagnostics
complexity: S
impact: Med
wow: 3
note: rule boost in/out of OS crash reports
order: 9
owner:
pr:
title: Crash-correlation breadcrumbs in the invocation log
---
A native abort (e.g. a macOS Obj-C fork-safety <code>SIGABRT</code>) kills the
           process outright, so it never reaches boost's Python crash recorder —
           leaving no boost-side trace to confirm or clear boost when an OS crash
           report appears. <code>log_invocation</code> now records
           <code>pid</code>, <code>ppid</code> and the interpreter path on every
           run, so any OS crash report can be cross-referenced by PID: if the
           crashing PID never appears in <code>~/.boost/logs/boost.log</code>,
           boost is definitively ruled out.
