---
id: rule-and-workflow-rows-carry-a-scope-nothing-but-list-local-reads
board: code
section: dx
status: shipped
category: CLI · Bug
complexity: S
impact: Low
wow: 2
note: a --local rule whose repo was deleted read as missing, and every remedy recreated the repo
order: 236
owner: loop/rule-scope-readers
pr:
title: "A rule or workflow installed <code>--local</code> into a since-deleted repo reads as missing, and every remedy recreates the repo"
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

<b>Shipped.</b> Reproduced on <code>main</code> first, and half the premise did not hold. From a
second repo, <code>doctor</code>, <code>verify</code> and <code>drift</code> graded another
checkout's <code>--local</code> rule <em>correctly</em> &mdash; its materialization rows are
absolute paths, so they can be read from anywhere, and <code>boost reinstall</code> repairs them
from anywhere too. The real bug was the other case: <code>rm -r</code> the checkout and every
surface read the rule as <em>missing</em>, and every remedy they named &mdash; <code>reinstall</code>,
<code>sync -y</code>, <code>heal</code>, <code>update</code> &mdash; re-materialized into the
recorded base and <b>recreated the deleted directory</b> (measured: a <code>.cursor/</code>, a
<code>.windsurf/</code>, <code>AGENTS.md</code>, <code>CLAUDE.local.md</code> and
<code>GEMINI.md</code> in a folder that no longer existed). So the row whose repo is gone is now
<em>stranded</em> (<code>scopes.stranded</code>: project scope, an absolute base, not a
directory), and the decision per surface is:
&middot; <b>doctor</b> &mdash; one issue per stranded item naming the repo and
<code>boost uninstall &lt;name&gt;</code>, never the per-agent "run <code>boost reinstall</code>"
lines. A live checkout's rows are still graded from anywhere.
&middot; <b>verify</b> / <b>attest --verify</b> &mdash; status <code>stranded</code>, which fails (it
did as <code>missing</code> already), with the uninstall hint. Every <code>--local</code> rule or
workflow row now reports <code>scope: project</code> and its <code>base</code>, where it used to
say <code>user</code>.
&middot; <b>drift</b> / <b>health</b> &mdash; <code>stranded</code>, hinted
<code>boost uninstall</code> rather than <code>boost heal</code>; health counts it as needing
attention, beside store-missing, source-missing and unreachable.
&middot; <b>sync</b> / <b>heal</b> &mdash; leave it out of the repair plan; the MCP doctor tool counts
it instead.
&middot; <b>update</b> &mdash; when the tap moved, skip it with the reason (before the risky-diff
prompt); silent when there is nothing new. <b>reinstall</b> and <b>quarantine --release</b>
refuse (release restores its stash to absolute paths, so it recreated the repo too). All three
rest on <code>store._refuse_stranded_base</code>, which refuses any lock-driven write of a rule or
workflow into a base that is gone. A quarantined row still reads <code>quarantined</code> in verify and drift;
<code>boost uninstall</code> clears either.
&middot; <b>info</b> / <b>cat</b> &mdash; <code>info</code> prints the <code>base</code>, marked
<code>(gone)</code>, and no agent list for a stranded row (its JSON carries
<code>stranded</code>); <code>cat</code> under digest enforcement refuses with the uninstall hint
instead of falling through to the tap copy. <b>doctor</b> and the MCP doctor tool still name a
stranded row after it is quarantined, since release refuses it.
&middot; <b>completion</b> &mdash; unchanged on purpose: <code>uninstall &lt;name&gt;</code> is the
remedy, so TAB keeps offering every row.
&middot; <b>list</b> &mdash; FLAGS carries <code>project:&lt;base&gt;</code>, and
<code>(gone)</code> for a stranded row, so a rule in another checkout no longer prints the same
as one in <code>~/.claude</code>.
Pinned by <code>tests/unit/test_stranded.py</code> (the predicate in both directions, the status,
the write guard and the sync plan) and <code>tests/functional/test_stranded_project_rows.py</code>
(each surface, end to end, with the checkout deleted and with it present); 40 of their 48 fail on
<code>main</code>, and the other eight pin behaviour that was right already and is kept.
