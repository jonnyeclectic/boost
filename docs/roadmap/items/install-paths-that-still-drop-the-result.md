---
id: install-paths-that-still-drop-the-result
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Med
wow: 1
note: six more install paths printed success over an agent dir that refused the link, because they threw the install result away
order: 332
owner: loop/install-result-callers
pr: 938
title: Six install paths still printed success over an agent dir that refused the link
---
<b>Found by the review of release train 4</b>, which routed bundle install, cohort apply,
profile use and snapshot restore through <code>_warn_unwritable</code>. Six more skill install
paths threw the result away and so never said which agent they skipped:
<code>boost reinstall</code> of a local import and of a URL import, <code>boost import --all</code>,
<code>boost create --install</code>, <code>distill</code>, <code>infer</code> and <code>absorb --install</code>
(one shared helper), and the <code>boost browse</code> install worker.

<b>Measured</b> in a disposable HOME with <code>~/.cursor/skills</code> at mode 500. Each printed
its success line and exit 0 with no word about Cursor: <code>reinstalled my-skill (local, from
…)</code>, <code>imported a-skill v1.0.0</code>, <code>installed new-one → ~/.agents/skills/new-one</code>
followed by a linked list that simply left Cursor out, and a browse detail pane reading
<code>● installed  ~/.agents/skills/brainstorming</code>. Each now prints
<code>not linked: ~/.cursor/skills is not writable</code> with its remedy. The browse pane carries
the same words on its status line, since it cannot print while the browser is on screen.

<b>Also:</b> the boost-first offer, when every file refused the write, said the rule "was not
written anywhere yet" and then named no way forward or back, though its docstring promises the
reversal on every branch. It now names <code>boost sync</code> to finish it and
<code>boost uninstall boost-first</code> to drop it.

<b>Not covered:</b> after the browser closes, its summary still prints a bare
<code>installed NAME</code> for what it installed in place. The pane showed the warning, but the
summary only has the entries, not their results.
