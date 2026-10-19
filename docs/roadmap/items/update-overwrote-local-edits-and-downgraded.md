---
id: update-overwrote-local-edits-and-downgraded
board: code
section: trust
status: shipped
category: Security · Supply chain
complexity: M
impact: High
wow: 3
note: edits and versions held unless --force
order: 5
owner: fix/update-guards
pr:
title: Update no longer overwrites local edits or walks a version back
---
<code>boost drift</code> listed an edited skill, rule and workflow as
<em>local-edits</em> and said <code>boost reinstall X</code> would discard
them — then a routine <code>boost update</code> after an upstream commit
overwrote all three with three green <code>refreshed … (source
changed)</code> lines, exit 0, no prompt and no backup. A tap rewound from
v1.5.0 to v1.4.0 was followed the same way, reported as <code>refreshed
brainstorming v1.4.0</code>. Both update loops now ask
<code>staleness.update_hold</code> before writing: an item whose installed
copy no longer hashes to its lock (<code>integrity.locally_edited</code>,
which checks <em>every</em> written rule/workflow artifact rather than
stopping at the first fault the way <code>materialized_status</code> does) or
whose upstream advertises a lower version is skipped with a warning naming
<code>boost reinstall X</code> / <code>boost update --force</code>, and the run
ends "N items held back" instead of "everything up to date".
<code>--force</code> (which already moved pinned taps) releases the holds and
says what it did: <code>downgraded brainstorming v1.5.0 → v1.4.0</code>,
<code>… — local edits discarded</code>.
