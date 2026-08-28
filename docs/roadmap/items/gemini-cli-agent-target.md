---
id: gemini-cli-agent-target
board: code
section: compat
status: shipped
category: Interop
complexity: M
impact: High
wow: 4
note: 
order: 41
owner: loop/gemini-cli-agent-target
pr: 
title: Gemini CLI as a first-class agent target (skills, rules, workflows, MCP)
---
boost spoke Claude Code, Cursor and Windsurf; Gemini CLI users got nothing. It is now a fourth target — and the interesting part is what it <em>doesn't</em> need. Gemini implements the <a href="https://agentskills.io">Agent Skills</a> standard and discovers <code>~/.agents/skills</code> — boost's canonical store — natively, so skills need <b>no symlink</b> (<code>links_skills: false</code>); linking anyway put one skill in two of its discovery tiers and cost a "Skill conflict detected" line per skill per session. <code>agents.linking_agents()</code> / <code>native_store_agents()</code> partition the enabled set so link, unlink, sync and health each iterate the right one. Formats diverge where Gemini's do: rules become a <code>GEMINI.md</code> managed block (<code>rules.CONTEXT_FILES</code>, generalized from <code>CLAUDE_MD_AGENTS</code>), and slash commands render to <b>TOML</b> (<code>workflows.render_gemini_command</code>, strings via <code>json.dumps</code> — a valid TOML basic string for any input) while subagents stay verbatim Markdown. New <code>core/mcphost.py</code> holds the per-host <code>mcp add</code>/<code>remove</code> grammar: Claude wants <code>&lt;name&gt; … -- &lt;cmd&gt;</code> because its <code>-e</code> is commander's variadic <code>&lt;env…&gt;</code> and keeps eating, so the name must lead; Gemini's is yargs with <code>nargs: 1</code>, so flags may precede the name safely. Gemini takes <b>no</b> <code>--</code>, and its <code>remove</code> defaults to project scope so unregister must pass <code>-s user</code> or silently no-op. <code>boost mcp register</code> gained <code>--host</code> (default: every installed CLI). Verified end to end against a real Gemini CLI 0.46.0: <code>gemini mcp list</code> reports boost <b>Connected</b>.
<b>Re-verified against Gemini CLI 0.57.0</b>, and one stated reason turned out to have been wrong from the start. The <code>--</code> is omitted because <code>unknown-options-as-args</code> already carries <code>--stdio</code> into <code>[args...]</code>, making the separator redundant — <i>not</i>, as this card and <code>mcphost.py</code> both claimed, because Gemini would capture it and hand it to boost. Checking the v0.46.0 tag shows that block byte-identical, so it was never drift: the argv was right for a reason nobody had verified. Name position and the project-scope <code>remove</code> both still hold verbatim, and 0.57.0 adds nothing that changes the argv.
The "no conflict warning" claim also needs a caveat it did not have: boost creates no link into a native-store agent, but <i>another installer</i> can, and one had — <code>~/.gemini/skills/hyperframes</code> pointing back into the canonical store through <code>.claude/skills</code>. Same symptom, different cause, and nothing in boost noticed. Detection lands separately, on its own branch.
