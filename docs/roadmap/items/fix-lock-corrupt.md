---
id: fix-lock-corrupt
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note: a corrupt lock was reported only in boost.log, the next fresh install replaced every record with one, and doctor sent a rolled-back lock's newest skill to sync
order: 374
owner:
pr:
title: A corrupt lock file is reported, and never written over
---
<b>A corrupt lock file was noticed only in <code>boost.log</code>.</b> <code>lockfile.read</code>
copied the bytes to <code>.skill-lock.json.corrupt</code> and fell back to an empty lock, so
<code>boost list</code> printed "no skills installed" and exited 0 with nothing on the terminal.
The first read of a corrupt lock now prints one warning to stderr per process. It names the
<code>.corrupt</code> backup and <code>boost replay rollback &lt;id&gt;</code>, and it stays off
stdout so <code>--json</code> output is still valid JSON.

<b>The next install wiped every record.</b> <code>boost install</code> already refused a skill
that was in the store but missing from the lock. A skill <i>not</i> yet in the store skipped that
check, though. It copied, linked and printed "lock updated" over a lock that now held only itself,
and <code>install --force</code> did the same. Doctor then reported the survivors as "added outside
boost", and the <code>boost sync</code> it suggested re-recorded them as <code>local</code>
skills linked to every agent, losing both their tap and their agent scope.
<code>lockfile.write</code> now raises while the lock on disk is corrupt.
<code>store.install</code> and <code>install_from_path</code> check the same thing before they
copy anything, so a refused install leaves nothing behind in the store. A missing lock (a fresh
install) and a lock in an older schema still write.

<b><code>boost replay rollback &lt;id&gt;</code> is the way back, but not all the way.</b> On a
corrupt lock it asks first, then makes the snapshot the lock byte for byte
(<code>lockfile.restore</code>). The corrupt bytes stay in <code>.corrupt</code>, and the usual skill
diff runs against the restored lock. History is snapshotted <i>before</i> each write, so no
snapshot holds the newest state: rolling back to the newest one restores the lock as it was
before its last change. The warning, the refusal's hint and the rollback's own lines now say so,
and that the newest record is only in <code>.corrupt</code>. Doctor (CLI and MCP) used to call the
skill that last change installed "added outside boost" and offer <code>boost sync</code>, which
re-filed it as a <code>local</code> skill linked to every agent. While the <code>.corrupt</code> file
is at least as new as every snapshot (<code>lockfile.unrestored_corrupt</code>), doctor names that
file instead, and MCP doctor counts the skill as the user's to resolve rather than sync's. The next
lock write snapshots the restored lock, and the usual <code>boost sync</code> line comes back.
