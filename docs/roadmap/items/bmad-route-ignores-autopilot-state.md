---
id: bmad-route-ignores-autopilot-state
board: code
section: dx
status: next
category: Agents · BMAD
complexity: S
impact: Med
wow: 2
note: the briefing hook checks state, the router never does
order: 322
owner:
pr:
title: <code>bmad route</code> never checks autopilot state, so any hook <code>off</code> missed keeps routing
---
The two autopilot hooks disagree about what decides whether they speak. <code>_orient</code>
(<code>boost_cli/commands/bmad.py:525-531</code>) prints only when its scope's state says so, and its hook names the
scope (<code>:266-268</code>). <code>_route</code> (<code>:331-356</code>) reads the prompt and the payload
<code>cwd</code> and nothing else, and its hook is a bare <code>&lt;launcher&gt; bmad route || true</code>
(<code>:269-270</code>). Only <code>status</code> reads the <code>autopilot</code> flag, and it already applies the
right rule: on means state <em>and</em> hook (<code>:625</code>, pinned by
<code>test_autopilot_reads_as_off_when_the_hook_is_gone</code>). <code>off</code> works only because it deletes the
hook, so any copy it misses keeps routing. Replayed once over one real prompt history, the router bannered <b>147 of
417</b> regular prompts (35%; 109 if pasted text is not part of the hook's <code>prompt</code> field, which was not
checked), averaging ~163 tokens.

<b>Copies it misses are ordinary. Two were reproduced in a throwaway HOME.</b> <i>(1) A worktree or second
checkout.</i> <code>on --scope project</code> writes the hook into <code>.claude/settings.json</code>, which Claude
Code's docs tell teams to commit, but keys state by the absolute checkout path (<code>:692-693</code>). In a copy of
the checkout, <code>status</code> reads <code>project autopilot=off 7 personas router=on briefing=on</code>,
<code>orient</code> prints <b>0 bytes</b> and <code>route</code> prints <b>711 bytes</b> of hook JSON.
<i>(2) The restore net.</i> Every hook write that changes the file snapshots the prior version into
<code>claude-settings-history/</code> (<code>boost_cli/core/claude_settings.py:19-21, 88-124</code>). <code>off</code>
removes the two hooks in two saves, so the last snapshot it writes holds <em>only</em> the router. Copy it back and
state says <code>autopilot:false</code>, no personas are on disk, the hook still sends a <b>594-char</b> banner, and
<code>status</code> suggests turning the autopilot on (<code>commands/bmad.py:632-633</code>).

<b>The first <code>on</code> reaches running sessions before its personas can.</b> The hooks docs say edits to hooks
in settings files &ldquo;are normally picked up automatically by the file watcher&rdquo;. The sub-agents docs say
the agents-directory watcher &ldquo;covers only directories that existed when the session started&rdquo;, and
<code>write_personas</code> creates <code>~/.claude/agents</code> when it is absent (<code>core/bmad.py:680</code>).
Read together (inferred from the docs, not observed in a live session), a first install that creates the directory
can start banners in open sessions before any restart, naming a lead subagent and support personas those sessions
cannot load. The command only says &ldquo;restart your agent session to pick up the new subagents&rdquo;
(<code>commands/bmad.py:289-291</code>), not that the banners are already live.

<b>Fix.</b> <i>(1)</i> Install <code>&lt;launcher&gt; bmad route --scope &lt;scope&gt; || true</code> and pass
<code>args.scope</code> through (<code>commands/bmad.py:120</code>). When <code>_route</code> runs as a hook (no
positional prompt, no <code>--plain</code>), it returns 0 silently inside its existing <code>try</code> unless that
scope's state has <code>autopilot</code>. Project scope looks up the payload <code>cwd</code> with the same exact
key <code>_orient</code> uses (<code>:692-693</code>). A nearest-parent lookup would route in a worktree nested under
the repo while the briefing stays silent, which is this defect again. A hook with no <code>--scope</code>, as on
every current install, accepts either scope until the next <code>on</code> replaces it. A corrupt state file reads as
empty, so the router stays silent. <i>(2)</i> For a live autopilot whose persona files are gone, drop the Lead and Support lines when the
lead's <code>.md</code> is in neither <code>~/.claude/agents</code> nor the project's. Check with
<code>persona_state()</code> (<code>core/bmad.py:707-720</code>), not <code>installed_personas()</code>
(<code>:693-704</code>), which requires an unedited digest and would drop the lead for anyone who hand-edited
<code>bmad-dev.md</code>. <i>(3)</i>
<code>on</code> checks <code>agents.is_dir()</code> before writing. If the directory is new, say that banners can
start in open sessions immediately and a restart is needed to use the personas. If it already existed, drop the
restart line.

<b>Checked and left alone.</b> <code>off</code> leaves an empty agents directory. Keep it, because it lets the
<em>next</em> <code>on</code> reach running sessions without a restart.

<b>Tests.</b> In <code>tests/functional/test_cli_bmad.py</code>,
<code>TestRoute.test_emits_the_hook_json_contract</code> and
<code>test_uses_the_cwd_the_hook_reports_not_its_own</code> assert a banner where <code>on</code> never ran. They
pin the defect, so they should run <code>on</code> first. So should
<code>test_trivial_prompts_produce_no_output_at_all</code> and <code>test_a_project_signal_failure_still_exits_zero</code>,
which would otherwise pass vacuously once state gates the router. Add <code>TestRoute</code> cases for state off
(empty stdout, exit 0), the second-checkout repro, a corrupt state file (as in
<code>TestOrient.test_a_broken_state_file_never_breaks_the_session</code>), and positional or <code>--plain</code>
input still printing. <code>TestAutopilotOn</code> should check <code>--scope global</code> on the route hook and
split its <code>"restart"</code> assertion by whether the directory existed. Also add a personas-absent case to
<code>TestRouteContext</code> in <code>tests/unit/test_bmad_core.py</code>.
