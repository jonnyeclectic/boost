---
id: audit-mcp-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 1
note: no --dry-run; a named missing host exits 0; unregister claims success Gemini denies
order: 276
owner:
pr:
title: "boost mcp: CLI audit findings (2026-08)"
---
Three truthfulness gaps in one command, all verified against the real CLIs.
<code>boost mcp</code> has no <code>--dry-run</code>/<code>--print</code>: register shells straight into
<code>claude mcp add &hellip;</code> / <code>agy mcp add &hellip;</code>, and the argv boost will run is
only visible in the one case where the child CLI is <em>missing</em> &mdash; though
<code>mcphost.argv()</code> makes printing it trivial and siblings (<code>clean</code>,
<code>compact</code>, <code>onboard</code>, <code>self-update</code>) all offer <code>--dry-run</code>.
Add one to <code>cmd_mcp</code> (<code>boost_cli/commands/configuration.py:1674-1779</code>) that prints
the resolved argv and installed-or-not per host, then exits 0 without running or seeding.

<br><br>Second: <code>mcp --host gemini</code> with no <code>gemini</code> on PATH prints
<em>&ldquo;! `gemini` CLI not found &mdash; run this yourself: &hellip;&rdquo;</em> and exits <b>0</b> having
registered nothing &mdash; fine for <code>auto</code>, which says what it looked for, but a script naming
one host gets success for a no-op. Return 1 when an explicitly named host's CLI is missing.

<br><br>Third: with nothing registered, <code>mcp unregister --host gemini</code> prints
<em>&ldquo;&#10003; unregistered boost as an MCP server for Gemini CLI (scope: user)&rdquo;</em> exit 0, while
Gemini's own argv (Gemini CLI 0.57.0) prints <em>Server &quot;boost&quot; not found in user settings.</em>
&mdash; on <b>stderr</b>, which <code>_run_mcp_host</code>
(<code>configuration.py:1553-1568</code>) drops while mapping any rc-0 child to &ldquo;ran&rdquo;. Scan
stdout+stderr for a not-found marker on unregister and report &ldquo;not registered &mdash; nothing to
do&rdquo;, mirroring register's <em>already registered</em> path. Docs: regenerate
<code>docs/commands.html</code> for the new flag and update <code>README.md</code>'s mcp section. Found by
the 2026-08 CLI audit (cluster <code>mcp-command-truthfulness</code>); repro in the audit log.
