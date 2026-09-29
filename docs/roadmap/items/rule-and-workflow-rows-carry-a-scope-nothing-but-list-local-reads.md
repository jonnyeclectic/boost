---
id: rule-and-workflow-rows-carry-a-scope-nothing-but-list-local-reads
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 2
note: a project-scoped rule reads as a user one in doctor, verify, drift, health and update
order: 236
owner:
pr:
title: "A rule or workflow installed <code>--local</code> reads as a user one everywhere but <code>list --local</code>"
---
Rules and workflows installed with <code>--local</code> materialize into the repo but are recorded
in the <em>user</em> lock, tagged <code>scope: project</code> and <code>base: &lt;repo&gt;</code>,
because a project lock holds skills and nothing else
(<code>store._check_scope_conflict</code>). <code>boost list --local</code> now filters them with
<code>scopes.owned_by</code>, and it is the only reader that does.

<code>lockfile.installed_rules()</code> and <code>installed_workflows()</code> have a dozen other
consumers &mdash; <code>store</code>, <code>complete</code>, <code>taps</code>,
<code>team</code>, <code>safety</code>, <code>quality</code>, <code>pkg</code> &mdash; and none of
them ask whose repo a row belongs to. So <code>boost doctor</code> and <code>boost verify</code>
count another checkout's rule as this machine's, <code>drift</code> and <code>health</code> grade
it, tab-completion offers it, and plain <code>boost list</code> prints it under
&ldquo;installed rules&rdquo; with nothing saying it belongs to a directory the user may not be
standing in. The failure is quiet in both directions: a row for a repo that has since been
deleted never goes away, and a row for the repo you <em>are</em> in looks identical to one for a
repo you are not.

Worth settling the design before the sweep, because the honest answer differs per command. A
<code>scope</code> column on plain <code>list</code>'s rule and workflow tables is cheap and makes
the ambiguity visible (<code>boost info</code> already prints <code>scope project</code>).
Whether <code>verify</code> and <code>doctor</code> should <em>grade</em> a rule belonging to
another repo is a separate question &mdash; they cannot read its materializations from here, so
counting it is arguably the bug and skipping it with a note the honest fix. Split out of
<code>audit-project-scope-seams-uninstall-verify-list-info-reinstall-dis</code>, where the
evidence was gathered.
