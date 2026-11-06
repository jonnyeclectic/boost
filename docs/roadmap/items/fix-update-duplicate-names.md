---
id: fix-update-duplicate-names
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note: with two same-named copies in one tap, boost update replaced the copy picked with install --path by the one that scanned first
order: 375
owner:
pr:
title: boost update refreshes the copy that was installed
---
<b><code>boost update</code> replaced the copy you chose with the other one.</b>
A tap can ship one name twice, and <code>boost install NAME --path DIR</code> picks between
them. The lock records the choice in <code>source_dir</code> for a skill and in
<code>source_file</code> for a rule or workflow. Update ignored both and took
<code>matches[0]</code> by scan order. It printed "refreshed (source changed)" and installed
the other copy, and the upstream change to the chosen copy never arrived.
<code>boost info</code> had the same fault: it showed the other copy's description next to the
installed copy's source.
<br><br>
Both now resolve through <code>catalog.select_lock_source</code>, the resolver that
<code>sync</code> and <code>reinstall</code> already used. When the recorded copy has gone
from the tap, update warns and names the copy it fell back to.
