---
id: audit-edit-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: editor fails → green "✓ no changes", exit 0; drift calls a local edit upstream-moved
order: 265
owner: loop/edit-drift-classification
pr:
title: "<code>boost edit</code>: CLI audit findings (2026-08)"
---
<b>edit rewrites the lock sha, so drift misclassifies a local edit as upstream-moved.</b> After an
edit, boost warns <em>&ldquo;local edits diverge from the tap source &mdash; boost drift will flag
this&rdquo;</em> &mdash; and then <code>boost drift</code> prints
<code>brainstorming&nbsp;&nbsp;upstream-moved&nbsp;&nbsp;boost update</code>, recommending the one
command that would discard the edit, although the tap is pinned and unchanged.
<code>cmd_edit</code> (<code>info.py:601-611</code>) overwrites <code>lock["sha256"]</code> with the
post-edit store hash, so <code>staleness.drift_state</code>'s store&ne;lock test
(<code>staleness.py:52-77</code>) can never fire <code>LOCAL_EDITS</code> and falls through to
<code>UPSTREAM_MOVED</code>. Fix: stop rewriting the lock sha &mdash; record the edit in the journal
only (already done) or under a separate <code>local_sha256</code> key.

<br><br><b>edit exits 0 with a green success line after the editor itself failed.</b> With
<code>EDITOR=false</code>: <em>&ldquo;! editor exited with status 1&rdquo;</em> immediately followed
by <em>&ldquo;&#10003; no changes&rdquo;</em>, exit 0 &mdash; a failed editor launch reported as a
clean no-op. In <code>cmd_edit</code> (<code>info.py:596-611</code>), when <code>rc != 0</code>
return 1 right after the warning and skip the sha compare and success messaging.

<br><br>Both fixes change edit's documented behaviour, so regenerate <code>docs/commands.html</code>.
Found by the 2026-08 CLI audit (clusters edit-drift-classification, edit-editor-failure-exit); repro
in the audit log.
