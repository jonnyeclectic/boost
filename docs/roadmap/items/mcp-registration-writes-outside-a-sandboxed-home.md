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
Twenty-two tests, and the ablations are what they are worth. Neutering the two guards fails four —
three on <code>boost mcp</code>, one on <code>boost install</code>'s MCP prompt, which is the
second shell-out and would have read as covered by the first. The rest pin the parts easy to get
wrong: that a config home <i>inside</i> <code>HOME</code> is not refused, that one refused host
does not end the sweep of the others, that <code>--force</code> gets through, that
<code>--dry-run</code> names the file either way, and that the absolute-path fixtures are built
with <code>os.path</code> rather than a literal <code>/</code>, since
<code>ntpath.isabs("/foo")</code> flipped to <code>False</code> in 3.13 and CI runs both.
