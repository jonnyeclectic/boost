---
id: a-correct-link-in-a-locked-dir-reads-as-refused
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Low
wow: 2
note: A reinstall into a locked skills dir says "not linked" while the right link is still on disk and the lock records the agent…
order: 333
owner: loop/correct-link-not-refused
pr: 945
title: A reinstall into a locked skills dir says "not linked" over a link that is already there and correct
---
<b>Found by the review of <code>install-paths-that-still-drop-the-result</code>.</b>
<code>store.link_agents</code> unlinks and re-creates every symlink it manages, even one that already
resolves to the store copy. In a skills dir that refuses writes, the unlink raises
<code>PermissionError</code>, so the agent goes into <code>res.unwritable</code>. <code>boost reinstall</code>
then prints <em>not linked: ~/.cursor/skills is not writable</em> while the old link is still on disk,
still points into the store, and the lock still records the agent in <code>agents</code>. The tap
branch of reinstall has done this since #931. The local and URL branches say it now too, because they
report the result at all.

<b>Fix direction.</b> In <code>link_agents</code>, treat an existing symlink that already resolves to the
target as linked, and skip the unlink and re-create. A link that points elsewhere, or no link, still
needs the write and is still refused.
