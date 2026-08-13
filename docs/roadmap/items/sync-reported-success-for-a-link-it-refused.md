---
id: sync-reported-success-for-a-link-it-refused
board: code
section: compat
status: shipped
category: Bug
complexity: S
impact: High
wow: 4
note:
order: 12
owner: fix/audit-findings
pr:
title: <code>sync</code> reported success for a link it had just refused
---
Observed on a real machine as a closed loop with no exit: <code>boost sync</code> answers
"✓ everything in sync" &middot; <code>boost doctor</code> answers "! skill hyperframes not linked
for claude-code — run <code>boost sync</code>" &middot; repeat forever.

Another installer had written <code>~/.claude/skills/hyperframes</code> as a real directory.
<code>link_agents</code> correctly refuses to delete a path boost does not own and records it in
<code>.conflicts</code> — but <code>sync_apply</code> dropped that value on the floor, appended no
action, and the command layer read "no actions" as "nothing to do". Doctor, meanwhile, tested only
<code>is_symlink()</code> and prescribed the command that had just declined to help.

<code>sync_plan</code> now separates the two cases it had been conflating: a
<code>missing_link</code> is one sync can create (nothing in the way, or a dangling symlink boost
owns and may replace), and a <code>blocked_link</code> is a path occupied by a file boost will not
touch. <code>sync</code> warns and names the path; <code>doctor</code> says why sync did nothing
and gives the step that unblocks it. store.py's own comment already named this anti-pattern — "sync
would answer 'everything in sync', change nothing, and send the reader back to the same error" —
one function above the code that was doing it.
