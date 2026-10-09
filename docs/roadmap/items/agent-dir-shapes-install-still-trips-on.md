---
id: agent-dir-shapes-install-still-trips-on
board: code
section: planned
status: shipped
category: Robustness · Bug
complexity: S
impact: Low
wow: 2
note: "fixed: a 0o600 dotdir no longer crashes install, doctor, heal, sync or uninstall on Python 3.12/3.13 (70 → 0/1) and is named \"not searchable\" with chmod u+wx; a missing skills dir under a read-only dotdir is named by its dotdir everywhere, and doctor (0 → 1) and sync now report it; a refused agent, or one whose link boost cannot look at, is recorded as refused_agents, retried by install --force, and blocks uninstall rather than being stranded; focus, context, profile and quarantine --release say what they skipped; a directory at a rule's file path is a conflict (70 → 0); heal --dry-run no longer previews a refused re-materialize; doctor names a read-only store (0 → 1)"
order: 332
owner: loop/agent-dir-shapes
pr: 1059
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
<code>doctor</code> says healthy. <code>doctor</code> could ask <code>paths.refuses_writes(paths.store_dir())</code>.<br><br><b>Shipped.</b> Every shape reproduced on <code>11dbbc77</code>, on Python 3.13 and 3.14, and each is closed.

<b>No search bit.</b> With <code>~/.cursor</code> at <code>0o600</code>, 3.13 crashed in more places than the
one the card named: <code>linked_agents</code>, <code>sync_plan</code>, <code>_broken_links</code>,
<code>cmd_heal</code>'s missing-dir scan, doctor's per-link and per-rule-file checks, and
<code>boost health</code>'s link count. Each now asks
<code>os.path</code>, which answers False where 3.12 and 3.13's pathlib raises. Measured on 3.13: install
70 &rarr; 0, doctor 70 &rarr; 1, heal 70 &rarr; 1, sync 70 &rarr; 0. On 3.14, where nothing crashed, install
named <code>~/.cursor/skills</code> with <code>chmod u+w</code>, doctor said healthy and sync said
"everything in sync". All four now name <code>~/.cursor</code> as "not searchable" and give
<code>chmod u+wx</code>: <code>paths.write_remedy</code> adds the <code>x</code> when <code>X_OK</code>
is what fails, and "cannot be created" becomes "cannot be reached", because the dir below may exist.
Uninstall's named refusal for a rule or workflow there now uses the same wording, where it still said
<code>chmod u+w</code>. A skill uninstall there went from 70 on 3.13 to a <em>silent</em> 0 on the
first draft of this fix: <code>unlink_agents</code> skipped the cursor link it could not see, and the
store dir and lock entry were deleted anyway, which left <code>~/.cursor/skills/brainstorming</code>
dangling into a deleted store. It now checks before it removes anything, exits 1 with
<code>chmod u+wx ~/.cursor</code>, and keeps the store, the lock and every link, so uninstalling again
after the <code>chmod</code> finishes it. A link it can see is checked whatever the lock says, since
<code>unlink_agents</code> removes every visible link. A link it cannot see is checked for every agent
the lock records in <code>agents</code> <em>or</em> <code>refused_agents</code>: the second draft read
<code>agents</code> alone, and an <code>install --force</code> or <code>reinstall</code> run under the
<code>600</code> dotdir moves cursor into <code>refused_agents</code> while the first install's link is
still on disk, so uninstall again exited 0 and stranded it (measured: exit 0 before, exit 1 and the link
kept after, for both). The third draft still stranded it through a relink that never tried cursor:
<code>install --force --agent claude-code</code> under the <code>600</code> dotdir refused nothing, and
<code>linked_agents</code> cannot tell "no link" from "could not look", so the lock dropped cursor from both
fields and uninstall exited 0. Every path that rewrites <code>agents</code> now also records, in
<code>refused_agents</code>, each agent whose link <code>os.lstat</code> may not look at
(<code>store.unrecorded_agents</code>): <code>install</code> (and so <code>update</code> and
<code>reinstall</code>), <code>import</code>, <code>quarantine --release</code> and the unsideline paths
through <code>record_links</code>, and the lock <code>sync</code> recovers from the store, which also stops
counting an unseen agent as a narrowing. Measured on the reviewer's row: lock <code>refused_agents</code>
<code>None</code> and uninstall exit 0 before, <code>['cursor']</code> and exit 1 with the link kept after.
A sideline (focus, profile, context) and <code>quarantine</code> empty
<code>agents</code> after an unlink that skipped the unseen link, which stranded it the same way, so an
empty <code>agents</code> now means every agent to the guard, as it already did to
<code>preserved_agent_scope</code>. The cost is conservative and tested: an agent refused at its first
install, never linked, also blocks uninstall until its dotdir is searchable, as does any unsearchable
dotdir for a sidelined or quarantined skill, and, since the third draft, any agent whose dotdir was
unsearchable at the skill's last install, relink, import or recovery, whether that run tried it or not:
so a dotdir left at <code>600</code> blocks uninstalling every skill written while it was. An agent a
non-empty lock entry does not name never blocks, so a dotdir locked down after that write blocks only
where the lock records a link.

<b>A missing skills dir under a read-only parent.</b> <code>link_agents</code> records
<code>refuses_writes(adir)</code>, as <code>_refused_target</code> already did for rules, so the install names
<code>~/.cursor</code>. <code>unwritable_agent_dirs</code> asks <code>refuses_writes</code> too, so doctor
(0 &rarr; 1), heal and sync name the same dir once. The four inline <code>chmod u+w</code> strings now
share one wording, <code>store.unwritable_refusal</code>. <code>heal --dry-run</code> no longer says
"would link" for a dir the run will skip.

<b>A refused agent stays in scope.</b> A skill's lock entry records the agents whose dir refused as
<code>refused_agents</code>. <code>preserved_agent_scope</code> replays them with <code>agents</code>, so after
the <code>chmod</code>, <code>install --force</code> links cursor, where before it linked three agents and said
nothing. The field is absent when nothing refused, so other entries are unchanged. An empty
<code>agents</code> still replays as every agent. A sideline empties it and leaves the refusals, and
replaying those alone would have narrowed the next <code>update</code> to the refused agents.

<b>Callers.</b> <code>focus</code>, <code>focus --clear</code>, <code>context</code> apply and disable,
<code>profile use</code> and <code>quarantine --release</code> now print the skip, on stderr under
<code>--json</code>. <code>boost import</code> already did, through <code>_report_result</code>, so that part of
the card was stale.

<b>A directory at a rule's file path</b> is filed as a conflict with an <code>unwritable</code> row. Install
went from 70 to 0 for rules and workflows, and doctor, heal and sync name it with the move.
<code>heal --dry-run</code> stops previewing a re-materialize while a row's dir still refuses (or a directory
sits at its path), which matches what the run reports. Doctor and heal now name a read-only
<code>~/.agents/skills</code>; doctor went from 0 to 1. Heal and sync printed "rule house was not re-materialized" under a green
check mark (also on <code>origin/main</code>); that line is now a warning.

<code>tests/functional/test_agent_dir_shapes.py</code> had 54 tests when this shipped, and 45 of them fail on
<code>11dbbc77</code>. The other nine guard the opposite direction. The 3.12/3.13 crashes are reproduced on any interpreter by a
fixture that makes pathlib raise where those versions do. Found while measuring and left out of this change:
<code>boost quarantine</code> under a <code>0o600</code> dotdir reports its links removed, but it cannot see the
cursor link to remove it. Fixed since, in #1063 (<code>quarantine-reports-a-link-removed-that-it-could-not-see</code>).
