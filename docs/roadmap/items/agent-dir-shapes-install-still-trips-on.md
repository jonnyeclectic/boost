---
id: agent-dir-shapes-install-still-trips-on
board: code
section: planned
status: planned
category: Robustness · Bug
complexity: S
impact: Low
wow: 2
note: Agent-dir shapes install, doctor, heal and sync still mishandle after the read-only-home fix; each behaves the same on c7dca95c…
order: 332
owner:
pr:
title: Agent-dir shapes boost still trips on: a parent with no search bit, a missing dir under a read-only parent, a dir at a rule's file path, a blocked agent dropped from the lock's scope
---
<b>Found by the third review of <code>read-only-boost-home-with-no-cache-dir</code>.</b> None is a regression.
Each was measured behaving the same on <code>c7dca95c</code>.

<b>A parent with no search bit.</b> With an agent dir's parent at mode <code>0o600</code>,
<code>store.install</code> copies the skill into the store. It then crashes at exit 70 in
<code>linked_agents</code>, where <code>(adir / name).is_symlink()</code> raises
<code>PermissionError</code> outside <code>link_agents</code>' guard. The store dir is left
unrecorded. Treating an <code>OSError</code> there as "not linked" would close it.

<b>A missing skills dir under a read-only parent.</b> The install names a <code>chmod</code>
target that does not exist, and <code>doctor</code> and <code>heal</code> disagree about it.
<code>link_agents</code>' <code>PermissionError</code> branch should record the block from
<code>paths.refuses_writes(adir)</code> and word it through <code>link_refusal</code>. doctor's
agent-dir check should use the same function, so that it agrees with heal.

<b>A blocked agent drops out of the scope.</b> After an install skips an agent as blocked, the lock's
<code>agents</code> list leaves it out. <code>preserved_agent_scope</code> replays that list, so a
later <code>install --force</code> never retries the agent and never says so. Only
<code>boost sync</code> reports and repairs it.

<b>Callers that drop the result.</b> <code>boost import</code> (<code>install_from_path</code>),
<code>quarantine --release</code> and the unsideline paths (focus, profile, context, team) drop
<code>res.blocked</code> without a word, as they already drop <code>res.unwritable</code>.
<code>pkg._warn_unwritable(res)</code> is the existing reporter.

<b>Also found by the reconcile review of #933 with #931</b>, and also measured on both parents: With any agent dotdir at mode <code>600</code>, on Python 3.12 and 3.13 (3.14's <code>Path.exists</code> answers False where they raise), <code>doctor</code>, <code>heal</code> and <code>sync</code>
exit 70 (<code>PermissionError</code> on <code>~/.cursor/skills</code>). A rule or workflow install in that
shape is fixed on #933's branch: <code>_refused_target</code> names the dir through
<code>paths.refuses_writes</code>, which asks <code>lexists</code>. So is uninstall of a rule or workflow there, through <code>store.refusing_dir</code>, which now treats a path it may not look at as not there. The skill install and these three are not fixed. And the remedy is wrong for this shape: <code>chmod u+w</code> leaves a <code>600</code> dir at <code>600</code>, because the missing bit is search, so the wording should say <code>chmod u+wx</code> when <code>X_OK</code> is what fails.<br><br>A <em>directory</em> at a rule's target file path (<code>~/.cursor/rules/house.mdc/</code>) raises
<code>IsADirectoryError</code>. That is not one of the refusal shapes, so install exits 70 after writing
the other agents' copies, with no lock entry.<br><br><code>heal --dry-run</code> previews "would re-materialize" a rule whose target dir is still locked or
blocked. The real run then re-materializes nothing, correctly. The exit codes agree (1 and 1), but the
wording does not.<br><br>With <code>~/.agents/skills</code> read-only, every install exits 1, naming it, while
<code>doctor</code> says healthy. <code>doctor</code> could ask <code>paths.refuses_writes(paths.store_dir())</code>.
