---
id: codex-is-not-an-mcp-host
board: code
section: planned
status: planned
category: Compat · Feature
complexity: S
impact: Medium
wow: 3
note: Codex takes skills and rules but `boost mcp register` cannot reach it — the grammar is verified, the host row is not written…
order: 344
owner:
pr:
title: Codex is a skills and rules target but not yet an MCP host
---
<b>Found while adding Codex as an agent target.</b> <code>boost install</code> now reaches Codex —
skills through the canonical store it already reads, rules into <code>~/.codex/AGENTS.md</code> — but
<code>core/mcphost.py</code> still has three rows (Claude Code, Gemini CLI, Antigravity CLI), so
<code>boost mcp register</code> cannot register boost with the one agent most likely to want to search
the catalogue for itself.
<b>The grammar is already verified</b> against Codex CLI 0.156.1, and it differs from all three
existing rows, so it is a row rather than a reuse. Flags are accepted on <em>either</em> side of
<code>NAME</code>, unlike Antigravity, which rejects a flag after the name &middot; <code>--</code> is
needed only when the command token itself starts with a dash &middot; there is <b>no scope
concept</b>, just one global <code>$CODEX_HOME/config.toml</code>, so <code>mcphost.has_scope()</code>
must answer False and the success line drops "(scope: user)" as it already does for Antigravity
&middot; <code>add</code> <b>upserts</b> (rc=0 on a duplicate name), like Antigravity and unlike
Claude, which is what <code>--host auto</code> has to tolerate &middot; <code>remove MISSING</code> is
idempotent (rc=0) while <code>get MISSING</code> fails (rc=1), so a presence probe must use
<code>get</code>, not <code>remove</code>.
<b>Fix direction.</b> Add the fourth row to <code>mcphost.HOSTS</code> and pin each of those five
asymmetries in <code>tests/unit/test_mcphost.py</code>, alongside the existing three. Don't
"simplify" the four shapes into one — that is exactly the note <code>CLAUDE.md</code> already carries
for the first three.
