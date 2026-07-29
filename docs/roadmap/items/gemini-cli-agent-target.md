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
boost spoke Claude Code, Cursor and Windsurf; Gemini CLI users got nothing. It is now a fourth target — and the interesting part is what it <em>doesn't</em> need. Gemini implements the <a href="https://agentskills.io">Agent Skills</a> standard and discovers <code>~/.agents/skills</code> — boost's canonical store — natively, so skills need <b>no symlink</b> (<code>links_skills: false</code>); linking anyway put one skill in two of its discovery tiers and cost a "Skill conflict detected" line per skill per session. <code>agents.linking_agents()</code> / <code>native_store_agents()</code> partition the enabled set so link, unlink, sync and health each iterate the right one. Formats diverge where Gemini's do: rules become a <code>GEMINI.md</code> managed block (<code>rules.CONTEXT_FILES</code>, generalized from <code>CLAUDE_MD_AGENTS</code>), and slash commands render to <b>TOML</b> (<code>workflows.render_gemini_command</code>, strings via <code>json.dumps</code> — a valid TOML basic string for any input) while subagents stay verbatim Markdown. New <code>core/mcphost.py</code> holds the per-host <code>mcp add</code>/<code>remove</code> grammar: Claude wants <code>&lt;name&gt; … -- &lt;cmd&gt;</code>, Gemini wants flags-then-name and <b>no</b> <code>--</code>, and its <code>remove</code> defaults to project scope so unregister must pass <code>-s user</code> or silently no-op. <code>boost mcp register</code> gained <code>--host</code> (default: every installed CLI). Verified end to end against a real Gemini CLI 0.46.0: <code>gemini mcp list</code> reports boost <b>Connected</b>, and <code>gemini skills list</code> discovers the store with no conflict warning.
