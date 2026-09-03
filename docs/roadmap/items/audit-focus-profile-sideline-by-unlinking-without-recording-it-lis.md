---
id: audit-focus-profile-sideline-by-unlinking-without-recording-it-lis
board: code
section: internals
status: shipped
category: CLI · Bug
complexity: M
impact: High
wow: 2
note: doctor's remedy for a sideline is `boost sync` — which silently undoes the sideline
order: 218
owner: loop/sideline-visibility
pr: 741
title: "focus/profile sideline by unlinking without recording it; list lies, doctor exits 1, and its own remedy (sync) undoes the switch"
---
<code>focus</code> and <code>profile use</code> both &ldquo;sideline&rdquo; skills by calling
<code>store.unlink_agents</code> without writing anything into the lock &mdash; so every other command
reads the lock as truth and fights the state. Verified live: <code>profile use daily</code> prints
<em>&ldquo;sidelined 1 skill(s) not in the profile (unlinked, still installed):
test-driven-development&rdquo;</em>; <code>boost list</code> then still shows
<code>AGENTS claude&middot;windsurf&middot;cur&hellip;</code> for it although no symlink exists;
<code>doctor</code> exits 1 with four lines of <em>&ldquo;! skill test-driven-development not linked
for &lt;agent&gt; &mdash; run <code>boost sync</code>&rdquo;</em>; and following that remedy relinks
all four &mdash; silently undoing the switch, while <code>focus --status</code> afterwards still
prints <em>&ldquo;&#8961; focus: brainstorming&rdquo;</em>. The inverse lies too:
<code>focus --clear</code> with no session at all reports <em>&ldquo;&#10003; focus cleared &mdash; 2
skill(s) restored&rdquo;</em>, because the count is the number of <code>link_agents()</code> calls,
not links actually re-created.

Why it matters: a user who runs <code>doctor</code> mid-focus is told their install is damaged and
handed the one command that ends the session without saying so &mdash; three surfaces
(<code>list</code>, <code>doctor</code>, <code>focus --status</code>) each report a state that is not
on disk. The writers are <code>boost_cli/commands/intelligence.py:1001-1013</code> (focus),
<code>team.py:362-365</code> (profile), and the bogus restore count is
<code>intelligence.py:957-966</code>. (<code>context disable</code> at <code>intelligence.py:922</code>
shares the unlink-without-record shape but was not replayed by the verifier.)

Fix (verified recommendation): record the sideline in the lock (e.g. <code>sidelined_by:
focus|profile</code>, mirroring the <code>only_agents</code> pattern the shipped
<em>sync-relinks-into-every-agent-ignoring-scope</em> item built for <code>install --agent</code>) and
have <code>list</code>/<code>doctor</code>/<code>sync</code> consult it &mdash; list shows the flag,
doctor stops calling it damage, sync leaves it unlinked; have <code>profile use</code> relink from that
record. Make <code>focus --clear</code>/<code>context disable</code> count only skills whose links were
actually missing and say <em>no focus session</em> when <code>focus.json</code> is absent. Docs:
regenerate <code>docs/commands.html</code> if summaries change. Found by the 2026-08 CLI audit
(cluster <code>sideline-state-unrecorded</code>); repro in the audit log.
