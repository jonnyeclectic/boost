---
id: fix-project-integrity
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note: project-scope integrity hashed only the first agent copy, so doctor and verify passed a tampered or deleted copy and heal left it missing
order: 375
owner:
pr:
title: Project-scope integrity checks every agent copy, and heal repairs a missing one
---
<b>A vendored skill is a real directory per agent, and only the first one was ever checked.</b>
<code>integrity.project_status</code> hashed the first materialization that was on disk and
called the install intact. An instruction appended to <code>.cursor/skills/x/SKILL.md</code>
passed <code>boost verify</code> with exit 0, and a deleted <code>.claude/skills/x</code> fell
through to the next copy, so <code>doctor</code> said "intact", <code>heal</code> left it missing,
and only <code>boost sync</code> noticed.
<br><br>
Now every recorded row is judged. A copy that hashes differently is <code>modified</code>, and that
outranks a missing sibling, because <code>boost update</code> asks this before it overwrites. A row
that is gone, or that escapes the repo, is <code>missing</code>: the same rows
<code>project_sync_plan</code> repairs. <code>doctor</code> names the missing copies, and
<code>heal</code> re-materializes them through <code>project_sync_apply</code>, which writes only
the missing agents and never copies over an edit in another one. A copy it cannot restore is
a warning, and heal exits 1.
