---
id: fix-update-default-branch
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note: a tap cloned --depth 1 stayed on the branch that was default at clone time, so an upstream rename read as up to date and then broke every update
order: 374
owner:
pr:
title: <code>boost update</code> follows an upstream change of default branch
---
<b>An upstream that switched its default branch was reported as "already up to date".</b>
A tap is cloned <code>--depth 1</code>, which implies <code>--single-branch</code>, so the clone's
fetch refspec named the branch that was default when it was tapped. <code>gitutil.pull</code>
fetched only that branch and reset to <code>origin/HEAD</code>, a symref git sets once at clone
time. A skill committed on the new default branch never arrived, and
<code>boost search</code> could not find it.

<b>Once the old branch was deleted, every update failed.</b> A GitHub
<code>master</code> to <code>main</code> rename deletes the old branch, and from then on
<code>boost update</code> exited 1 with <code>couldn't find remote ref refs/heads/master</code>
and no hint. The only way out was to untap and re-tap.

<code>pull</code> now asks the remote which branch its HEAD names
(<code>ls-remote --symref origin HEAD</code>). It points the fetch refspec at that branch,
fetches, and moves <code>origin/HEAD</code> before the reset. A wildcard refspec is kept, and a
remote that names no branch keeps the old behaviour. The fetch keeps its depth, its blobless
filter and the sparse cone. A pinned tap is still skipped and stays on its commit, and
<code>--force</code> moves it to the new branch.
