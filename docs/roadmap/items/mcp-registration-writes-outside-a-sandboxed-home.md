---
id: mcp-registration-writes-outside-a-sandboxed-home
board: code
section: planned
status: planned
category: Safety · Bug
complexity: S
impact: Medium
wow: 3
note: Every other boost surface honours HOME/BOOST_HOME; this one writes to whatever CLAUDE_CONFIG_DIR says…
order: 344
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
<b>Fix.</b> Decide deliberately and say so in <code>mcphost.py</code>, which already documents each
host's argv rules: either pass the scope explicitly derived from boost's own
<code>HOME</code> (Claude Code reads <code>CLAUDE_CONFIG_DIR</code>, so boost can set it for the
child), or refuse to register when <code>HOME</code> is not the ambient one and say which file
would have been written. Pin whichever with a test that sets both variables apart and asserts
nothing outside the sandbox is touched.
