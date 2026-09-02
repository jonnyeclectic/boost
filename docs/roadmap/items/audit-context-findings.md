---
id: audit-context-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: git missing from PATH is reported as "not in a git repository", even inside a repo
order: 259
owner: loop/context-git-state
pr: 699
title: "boost context: CLI audit findings (2026-08)"
---
<b><code>context</code> and <code>impact</code> conflate "git missing from PATH" with "not a git
repo", and impact's note claims a repo outside one.</b> With git removed from PATH and the cwd a
real git repository, <code>context status</code> prints <em>"branch&nbsp;&nbsp;(not in a git
repository)"</em>, <code>context apply</code> says <em>"not inside a git repository — nothing to
apply"</em>, and JSON gives <code>"branch": null</code> with no hint — all exit 0.
<code>gitutil.run</code> itself distinguishes the missing binary (<em>"git is required but was not
found on PATH"</em>), so the information exists and is dropped: <code>_current_branch</code>
(<code>boost_cli/commands/intelligence.py:139-145</code>) returns <code>None</code> for both
<code>not has_git()</code> and a non-repo cwd, and every caller words <code>None</code> the same
way.

<br><br>The other half: outside any repo, <code>impact brainstorming</code> still prints
<em>"correlation, not causation — commits since install in this repo"</em> (identical in JSON, with
<code>commits_since: null</code>), because <code>_IMPACT_NOTE</code>
(<code>intelligence.py:1087-1090</code>) is emitted unconditionally although <code>in_repo</code>
is computed right above it (<code>:1050-1054</code>) — and the <code>&mdash;</code> placeholder
sits left-aligned under a right-aligned numeric column. Fix: branch the note on
<code>in_repo</code> (text and JSON, e.g. <em>"not inside a git repository — commit counts
unavailable"</em>), right-align the placeholder, and make <code>_current_branch</code>/impact
distinguish <code>has_git()==False</code> — print <em>"(git not found on PATH)"</em> and expose
<code>"git": false</code> in JSON. No doc changes. Found by the 2026-08 CLI audit (cluster
<code>git-state-misreport</code>); repro in the audit log.
