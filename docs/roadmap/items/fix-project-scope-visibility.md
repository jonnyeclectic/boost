---
id: fix-project-scope-visibility
board: code
section: internals
status: shipped
category: Bug
complexity: S
impact: High
wow: 3
note: info and list read the repo's own lock; outdated, update, deps and install's dependency plan did not
order: 374
owner:
pr:
title: <code>outdated</code>, <code>update</code> and <code>deps</code> see <code>--local</code> skills
---
<b><code>boost outdated</code> called a stale project skill current.</b> In one repo,
<code>boost info commit-messages</code> printed <code>[update available]</code> while
<code>boost outdated</code> printed <code>everything up to date</code> and <code>--json</code>
printed <code>[]</code>. Both commands walked only the user lock, and a <code>--local</code>
install is recorded only in <code>.boost/skill-lock.json</code>. <code>boost update -y</code> had
the same blind spot and left the skill at its old version. <code>integrity.installed_skill_rows</code>
is now the one walk over both locks. <code>outdated</code> lists project rows with
<code>(project)</code> on the name and a <code>scope</code> field on every JSON row. <code>update</code>
judges a project row's edits against its copy in the repo, reinstalls it there and records the
result in the project lock. A held row now points to
<code>boost install NAME --local --force</code>, because <code>reinstall</code> reads only the user lock.

<b><code>boost deps</code> said a requirement installed beside its dependent was missing.</b>
<code>deps jira-integration</code> printed <code>✗ not installed</code>, exited 1 and hinted at a
second, user-scope install. Plain <code>deps</code> skipped project skills entirely. It now uses
<code>prereq.installed_names(pbase)</code> for what counts as installed, and walks project skills
too. <code>install --local</code> had the same gap in its dependency plan: it re-planned a
requirement already in the repo, the reinstall refused it, and the command exited 1.
