---
id: snapshot-export
board: code
section: internals
status: shipped
category: Bug
complexity: M
impact: High
wow: 3
note: snapshot restore emptied the store before a symlink broke the extract; rollback dropped scope and pins; export and dump ignored project-scope skills
order: 375
owner:
pr:
title: Snapshot restore is all-or-nothing, rollback keeps holds, export sees project skills
---
<b>Three ways the store's backup and sharing paths lost what the user had.</b>
<code>boost snapshot save</code> archived a symlinked store entry as an absolute link, and
<code>restore</code> wiped the store <i>before</i> extracting, so the data filter's refusal
left every skill deleted and the snapshot unrestorable. Save now archives a link's target
(and skips a dangling one), checks every member against the same filter, and restore
extracts into a staging directory, swapping it in only when that succeeded and putting the
old store back if the swap fails (<code>core/snapshot.py</code>).
<code>boost replay rollback</code> reinstalled a removed skill with defaults; it now passes
the recorded <code>only_agents</code> and writes back <code>pinned</code> and
<code>commit_pin</code> (<code>store.reapply_recorded_holds</code>), warning when the pinned
commit is no longer what the tap serves.
<code>boost export</code> and <code>boost bundle dump</code> read only the user lock, so a
<code>--local</code> skill <code>boost list</code> showed was "not installed". Both now walk
the project lock (<code>store.project_skills</code>); a dumped project skill carries a
trailing <code>--local</code> that <code>bundle install</code> honours.
