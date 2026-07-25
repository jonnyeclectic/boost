---
id: onboard-overwrites-generated-files-without-confirm
board: code
section: internals
status: planned
category: UX · Bug
complexity: S
impact: Med
wow: 2
note:
order: 35
owner:
pr:
title: <code>boost onboard</code> silently overwrites existing generated files
---
<code>boost onboard</code> writes <code>.boost/telemetry.json</code>, a GitHub Actions workflow, and
<code>.skill-lock.json</code> via a bare <code>write_text()</code> with no existence check,
confirmation, or diff — unlike the sibling "write a generated file" helper elsewhere in the
codebase, which always confirms before overwriting. Re-running it on a repo with its own tracked
lock file silently clobbers it and still reports "created," even though it overwrote. Check
<code>dest.exists()</code> and route through <code>out.confirm()</code> first.
