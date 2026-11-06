---
id: lock-field-preservation
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: Medium
wow: 3
note: a commit pin did not survive a reinstall, a profile brought back skills that were off, and update gave an all-clear over pinned items it skipped
order: 374
owner:
pr:
title: Pins hold through <code>reinstall</code>, profiles snapshot the active set, <code>update</code> names what a pin held
---
<b><code>boost reinstall</code> erased a commit pin and moved a pinned skill.</b> Every lock builder
in <code>store.install</code> rebuilds the entry from scratch and carried <code>pinned</code>,
<code>tags</code> and <code>installed_at</code> by name, but never <code>commit_pin</code>. After
<code>boost pin X --commit</code>, an upstream bump and <code>boost update</code> (which correctly
skipped X), <code>boost reinstall X</code> installed v0.2.0 under the old version pin, dropped the
commit pin without a word, and <code>boost verify</code> went on passing. All four builders (skill,
rule, workflow, import) now carry it through <code>store.carried_user_state</code>, whose docstring
lists the audit: user state that is carried, derived fields that are rebuilt, and the two fields
reset on purpose (<code>quarantined</code>, and <code>sidelined_by</code>, because the install
relinks). <code>store.reinstall_pin_hold</code> refuses a reinstall that would move a pinned item:
a commit-pinned one whose tap is off the pin, or a pinned one whose source changed. It says
<code>`boost unpin X` first</code>, and a same-content reinstall still restores the item.
<code>boost sync</code>'s repair applies the same commit-pin check, so a missing store dir is not
re-filled from a commit nobody pinned.

<b><code>boost profile save</code> recorded sidelined skills.</b> A skill that focus, context or an
earlier <code>profile use</code> had unlinked was saved as part of the profile, so restoring the
profile switched it back on. Save now takes the active set only, through
<code>lockfile.split_sidelined</code>, and names what it left out. To <code>profile use</code>, a
left-out skill is an extra, so it is sidelined again and the saved state comes back as it was.

<b><code>boost update</code> said "everything up to date" over pinned items it skipped.</b> The
skill loop and <code>_update_materialized</code> skipped a pinned item before checking for a
newer version, so it never counted, while <code>boost outdated</code> listed the same item. Update
now prints "N pinned items have an update held back", with <code>boost outdated</code> to see them
and <code>boost unpin</code> to take one, and gives the all-clear only when nothing was held.

Not changed here: a reinstall still clears <code>sidelined_by</code> and relinks, and
<code>update</code> refreshes sidelined skills the same way.
