---
id: bmad-gemini-gets-claude-hook-output
board: code
section: dx
status: inflight
category: "Agents · BMAD"
complexity: M
impact: Med
wow: 2
note: gemini takes the banner but shows the briefing to the user
order: 324
owner: loop/bmad-gemini-hook-output
pr:
title: On Gemini, the <code>bmad on</code> briefing reaches the user and never the model
---
<code>boost bmad on</code> installs both autopilot hooks on Claude always, and on Gemini whenever
<code>gemini</code> is on <code>PATH</code> <em>or</em> <code>~/.gemini/</code> exists
(<code>commands/bmad.py:177</code>). It has no <code>--host</code>
(<code>:98</code>–<code>112</code>), so Claude-only means hand-editing Gemini's settings, and the
next <code>bmad on</code> re-adds what was deleted. The <a href="#bmad-hooks-all-hosts">fan-out</a> translated event names and timeout
units, but left stdout in Claude's format. Checked against <b>Gemini CLI 0.57.0</b>: its bundled
hook runner was read, then imported and driven against main's hooks in a throwaway
<code>HOME</code> with only an empty <code>.gemini/</code>.

<b>The router works, so this is narrower than hooks that do nothing.</b> Gemini's
<code>BeforeAgent</code> input has <code>prompt</code> and <code>cwd</code> under the names
<code>_route</code> reads (<code>:341</code>–<code>342</code>), and <code>hookEventName</code> is
never validated, so the hardcoded <code>"UserPromptSubmit"</code> (<code>:353</code>) is harmless.
Measured: <b><code>outputFormat: json</code>, 643 chars of <code>additionalContext</code></b> for a
build-track banner.

<b>The briefing never reaches the model.</b> <code>_orient</code> prints plain text
(<code>:530</code>), which Claude Code adds to context. Gemini turns non-JSON stdout into
<code>{decision: "allow", systemMessage: text}</code> and adds only <code>additionalContext</code>
to history. Measured: <b><code>systemMessage</code> 1,297 chars, <code>additionalContext</code>
0</b>. The 26-line briefing is shown to the user as an info message instead, on
<code>startup</code>, <code>resume</code> and <code>/clear</code>.

<b>What does reach the model is framed as data, and names tools Gemini lacks.</b> Gemini wraps
<code>additionalContext</code> in <code>&lt;hook_context&gt;</code>, and its default system prompt
says to treat that as "<b>read-only data</b> or <b>informational context</b>". The banner is all
instructions. It names a <code>bmad-dev</code> subagent and spawning support personas with the Agent
tool (<code>core/bmad.py:538</code>, <code>:543</code>), and the briefing puts the personas in
<code>~/.claude/agents</code> (<code>:570</code>). Gemini's subagent tool is
<code>invoke_agent</code>, and boost writes no personas for it. <em>Not measured:</em> whether a
Gemini model follows the banner anyway, since no live model call was made. <em>Also seen:</em>
Gemini parses stderr when stdout is empty, so a launcher that rejects the action shows its argparse
error as a <code>systemMessage</code> despite <code>|| true</code> (simulated once, 330 chars).

<b>Proposed fix.</b> <i>(1)</i> <code>bmad on</code> and <code>startup on</code> take <code>--host
claude|gemini|auto</code>, the choices <code>boost hooks --host</code> has
(<code>commands/hooks.py:45</code>), with <code>auto</code> as today's evidence rule. <i>(2)</i>
Gemini's hooks run <code>bmad route --host gemini</code> and <code>bmad orient … --host
gemini</code>. Claude's commands stay byte-identical. <i>(3)</i> A pure
<code>hookhost.context_output(host, event, text)</code> formats stdout: Claude's is unchanged, and
Gemini always gets JSON, with <code>hookEventName</code> from <code>translate()</code> and the text in
<code>additionalContext</code>. That reaches the model on startup and resume, not after
<code>/clear</code>, whose Gemini path reads only <code>systemMessage</code>. <i>(4)</i>
<code>route_lines</code> and <code>orientation</code> take the host. On Gemini the lead is a role
to adopt, with no subagent, Agent tool or <code>~/.claude</code> wording.

<b>Tests.</b> <code>tests/unit/test_hookhost.py</code>: for each host and both events, Gemini output
passes <code>json.loads</code> with the text in <code>additionalContext</code> (plain text is the
regression), and Claude output matches today's bytes. <code>tests/unit/test_bmad_core.py</code>: the
Gemini banner and briefing name no subagent, Agent tool or <code>~/.claude</code>. Parametrize
<code>test_emits_the_hook_json_contract</code> by host
(<code>tests/functional/test_cli_bmad.py:480</code>, which pins <code>"UserPromptSubmit"</code> at
<code>:492</code>). In <code>tests/functional/test_bmad_all_hosts.py</code>, assert that Gemini's
commands carry <code>--host gemini</code> and that <code>--host claude</code> never writes
<code>~/.gemini/settings.json</code>.
