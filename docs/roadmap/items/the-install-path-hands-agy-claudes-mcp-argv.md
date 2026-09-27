---
id: the-install-path-hands-agy-claudes-mcp-argv
board: code
section: planned
status: inflight
category: MCP · Bug
complexity: S
impact: Medium
wow: 3
note: Two functions built the same `mcp add` command line, and only one of them had heard of agy…
order: 350
owner: loop/mcpdecl-host-parity
title: Registering a skill's MCP server handed Antigravity the one argv its CLI rejects
---
<b>Found by a reviewing subagent on <a href="https://github.com/jonnyeclectic/boost/pull/977">#977</a>,
which was about a different file.</b> <code>boost install</code> of a skill that declares an MCP
server offers to register it with every agent CLI on PATH, and built that command line in
<code>core/mcpdecl.py</code> — a second copy of the per-host grammar whose docstring said it
"mirrors <code>core/mcphost.py</code> exactly". It mirrored two hosts of three. It had a Gemini
branch and a Claude fallthrough, and <b>agy fell through to Claude's</b> — the single host whose CLI
rejects that shape.
<br><br>
Measured against the old code: <code>agy mcp add gh --scope user -e K=v -- npx -y gh-mcp</code>.
Antigravity CLI has <i>no scopes</i> (one global file at
<code>~/.gemini/config/mcp_config.json</code>, inherited from Gemini CLI), so <code>--scope</code> is
an error rather than a no-op, and it requires every flag <i>before</i> the name, so the
<code>-e</code> is rejected too. Every declared server, every install, on any machine with
Antigravity installed — reported as "could not register gh" and never once as a boost bug, because
the line the user sees is the CLI's.
<br><br>
<b>The fix is not the missing branch.</b> Adding one would have left the same two copies, with the
fourth host (Codex, next) to remember in both. The grammar moved into one function,
<code>mcphost.add_argv(host, name, command, tail, …)</code>, and both callers became thin:
<code>register_argv</code> registers boost itself (<code>launcher mcp --stdio</code>) and
<code>mcpdecl.register_argv</code> turns a declared spec into the same call. Output is byte-identical
for Claude and Gemini — all 134 existing argv assertions pass untouched — and correct for agy for the
first time.
<br><br>
<b>And the fallthrough is now loud.</b> Claude's shape was the <code>return</code> at the bottom of
the function, which is <i>why</i> a host with no branch inherited it silently. It is an explicit
<code>if host == CLAUDE</code>, and the bottom of the function raises. A host can be in
<code>HOSTS</code> and have no grammar for exactly as long as it takes a test to run.
<br><br>
Eleven tests. The three literal per-host argvs on the install path (none existed: nothing tested
<code>mcpdecl.register_argv</code> with a <code>host=</code> at all); agy's two rules each pinned
separately, so a regression names which one broke; a cross-module parity test <b>parametrised over
<code>mcphost.hosts()</code></b>, which is the docstring's promise turned into an assertion and which
covers a fourth host the moment the table gains one; and a monkeypatched <code>codex</code> row
asserting <code>ValueError</code> — the regression this shape exists to prevent, failing in CI
instead of on a user's machine.
