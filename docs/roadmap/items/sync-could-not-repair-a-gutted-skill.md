---
id: sync-could-not-repair-a-gutted-skill
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Med
wow: 4
note: two commands named `boost sync` as the repair; sync answered "everything in sync" and changed nothing
order: 111
owner: fix/sync-repairs-gutted-skill
pr:
title: The repair command could not repair the thing two commands sent you to it for
---
<code>boost edit</code> and <code>boost evolve</code> both refuse a skill whose <code>SKILL.md</code>
is gone, and both name the same remedy:

<code>Error: SKILL.md missing from ~/.agents/skills/brainstorming</code><br>
<code>&nbsp;&nbsp;hint: repair the store with <b>boost sync</b></code>

It could not. <code>sync_plan</code> classified a skill as <code>missing_store</code> only when its
<b>directory</b> was absent (<code>if not sdir.is_dir()</code>), so a directory that still existed
but had been emptied read as perfectly healthy. Running the named remedy printed
<b><code>✓ everything in sync</code></b>, changed nothing, and the next <code>boost edit</code>
produced the identical error. <code>boost heal</code> said <code>nothing to heal</code>.
<code>boost update</code> said <code>everything up to date</code>. The one command that did repair
it — <code>boost reinstall</code> — was named by neither hint.

<b>That is a loop, not a bad message.</b> The reader runs the suggested fix, observes no change,
and has no next move — every diagnostic in the tool agrees the store is fine while the command in
front of them insists it is not. It is the same defect as the shard exporter fixed earlier this
session, which answered "no vectors — build them first with <code>reindex --dense</code>" inside a
CI job where <code>reindex --dense</code> had just succeeded on the line above.

<b>The state is ordinary, not exotic.</b> An interrupted copy, a partial rsync, a half-finished disk
cleanup, or a user deleting the file to "start fresh" all leave the directory standing.

<b>Why the suite could not see it.</b> One test pins that hint, in
<code>tests/functional/test_cli_pkg.py</code>, and it removes the <i>whole directory</i> with
<code>shutil.rmtree</code> — the case <code>sync</code> already handled. Nothing ever deleted just
the file, so the <i>file-level</i> check in the two commands and the <i>directory-level</i> check in
<code>sync</code> were never compared with each other. Both were individually correct; the defect
lived only in the gap between them, which is where three of this session's other bugs also lived.

<b>Fixed in the detection, not the repair.</b> <code>sync_apply</code> already knows how to restore a
<code>missing_store</code> entry — it reinstalls from the recorded tap — so the change is one
condition, and <code>missing_store</code> is the right bucket precisely because its existing repair
is what a gutted directory needs. Seven tests pin both directions: the gutted case is now reported
<i>and</i> actually restored, the wholly-missing directory still is, a healthy skill still is not
(or <code>sync</code> would reinstall everything on every run), and the restored file is
byte-identical to the original — restoring an <i>empty</i> SKILL.md would satisfy every other
assertion and leave <code>boost edit</code> opening a blank document.
