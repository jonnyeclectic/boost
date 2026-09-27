---
id: mcp-registration-writes-outside-a-sandboxed-home
board: code
section: planned
status: shipped
category: Safety · Bug
complexity: S
impact: Medium
wow: 3
note: Every other boost surface honours HOME/BOOST_HOME; this one writes to whatever CLAUDE_CONFIG_DIR says…
order: 344
owner: loop/mcp-sandbox-home
pr: "977"
title: boost mcp registration writes outside a sandboxed HOME
---
<b>Found when an agent working in a sandboxed <code>HOME</code> ran <code>boost mcp</code> instead of
<code>boost mcp --stdio</code>.</b> The registration path shells out to <code>claude mcp add</code>,
which resolves its config from <code>CLAUDE_CONFIG_DIR</code> in the ambient environment rather than
from <code>HOME</code> — so boost was registered in the developer's real
<code>~/.claude-personal/.claude.json</code> from inside a run whose <code>HOME</code> and
<code>BOOST_HOME</code> both pointed at a temporary directory. It was reverted with
<code>claude mcp remove boost -s user</code>, and the escape is the finding.
<br><br>
Every other boost surface resolves state through <code>core/paths.py</code>, which reads
<code>HOME</code>/<code>BOOST_HOME</code> at call time — that is what makes the whole test suite
sandboxable. <code>mcphost</code> hands the decision to another CLI, and that CLI has its own
environment variable, so a test, a CI job or an agent that sets <code>HOME</code> and expects
containment does not get it.
<br><br>
<b>Fixed by refusing, not by redirecting.</b> boost <i>could</i> set <code>CLAUDE_CONFIG_DIR</code>
for the child and point the write back inside its own <code>HOME</code> — and that is the worse half
of the choice: it overrides a variable the user set on purpose, and then reports success for a file
their CLI never reads. So <code>mcphost</code> gains the table it was missing
(<code>CONFIG_HOME_ENV</code>, <code>USER_CONFIG_REL</code>) and both shell-out sites check the
answer against boost's own <code>HOME</code> before <code>subprocess.run</code> inherits the
environment. The refusal names the file that would have been written and prints the argv, so the
remedy is one paste; <code>--force</code> is the way through on <code>boost mcp</code>, and
<code>boost install</code>'s MCP prompt has no flag surface, so it only reports.
<br><br>
<b>Only Claude Code can escape, and that was established rather than assumed.</b> Claude Code
2.1.283 resolves its configuration home from <code>CLAUDE_CONFIG_DIR</code> and falls back to
<code>HOME</code> — including for a <i>relative</i> value, which it rejects outright
(<i>"the configuration home (CLAUDE_CONFIG_DIR) is not an absolute path"</i>), so
<code>config_home()</code> falls back on anything not <code>isabs</code>. Gemini CLI 0.57.0's
<code>GEMINI_DIR</code> is a JavaScript constant, not an environment variable, and Antigravity
(<code>agy</code>) exposes none at all; both are anchored at <code>HOME</code> and are pinned to
stay that way, so a Claude-only variable can never hold back a write that was always landing in the
sandbox.
<br><br>
<b>The test fixture had the same hole, and it was not hypothetical.</b> Every existing
<code>mcp</code> test is judged against whatever <code>CLAUDE_CONFIG_DIR</code> the developer has
exported — so on the machine this was found on, removing the fixture's new <code>delenv</code>
fails <b>fourteen pre-existing <code>TestMcp</code> tests</b> while CI, which exports nothing,
stays green. The <code>sandbox</code> fixture now clears it, beside the <code>CODEX_HOME</code>
delenv that is there for exactly this reason.
<br><br>
<b>Review found the guard was guarding the wrong file on the way out.</b>
<code>claude mcp remove boost</code> takes no scope flag and does not need one — it removes the
entry from <i>whichever</i> scope holds it, and project scope is <code>&lt;cwd&gt;/.mcp.json</code>,
a file no <code>$HOME</code> contains. So a check that the user-scope file is inside
<code>HOME</code> vouched for one file while the argv could reach another, and
<code>boost mcp unregister</code> from a repo could delete a committed project registration the
guard never looked at. Claude's <code>unregister_argv</code> now passes <code>--scope user</code>
explicitly: the flag it does not need is how the argv is held to the file the guard checked.
<br><br>
The comparison itself moved into <code>core/mcphost.escapes_home</code>. It had been three lines in
the command layer, which the required gate cannot mutate — <code>mutation_gate.py</code> targets
<code>boost_cli/core</code> — so a mutant flipping <code>not force</code> or inverting the
containment test would have been killed by nothing. It is the only function in that module that
touches the filesystem, because <code>scopes.contains</code> resolves <b>both</b> sides: on macOS a
tempdir <code>$HOME</code> under <code>/var/folders</code> resolves to <code>/private/var/…</code>,
and a symlink <i>inside</i> <code>$HOME</code> that leads out is an escape a string prefix test
would wave through. Both are pinned. So is the raise for a scope the guard cannot model: the
install path threads <code>scope</code> from the install and now refuses anything but
<code>user</code>, rather than measuring the user-scope path for a project write.
<br><br>
<b>Thirty-six tests, and the ablations are what they are worth.</b> Making
<code>escapes_home</code> always answer "contained" — leaving its refusal for an unknown host
intact, so the count is the containment test alone — fails <b>eight</b>: three unit, five
functional, across <code>boost mcp</code> in both directions and <code>boost install</code>'s MCP
prompt, which is the second shell-out and would have read as covered by the first. Dropping
<code>--scope user</code> from Claude's removal fails <b>six</b>, two of them on the argv itself
and four on what the command layer prints and runs. Dropping the fixture's
<code>delenv</code> fails <b>fourteen pre-existing tests</b> on a machine that exports the variable.
The rest pin the parts easy to get wrong: that a config home <i>inside</i> <code>HOME</code> is not
refused, that one refused host does not end the sweep of the others, that a refused host and a
failed host are both reported and the exit code is their union, that <code>--force</code> gets
through in both directions, that <code>--dry-run</code> predicts the run it describes with and
without it, and that the absolute-path fixtures are built with <code>os.path</code> rather than a
literal <code>/</code>, since <code>ntpath.isabs("/foo")</code> flipped to <code>False</code> in
3.13 and CI runs both.
