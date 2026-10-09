---
id: ai-cli-calls-inherit-the-real-config-home
board: code
section: trust
status: planned
category: Core · Bug
complexity: S
impact: Low
wow: 1
note: explain / search --smart run the claude CLI with the parent environment, so a sandboxed HOME still writes into the real config home
order: 369
owner:
pr:
title: "AI-assisted commands reach the real config home from a sandboxed <code>HOME</code>"
---
<code>ai._ask_cli</code> runs <code>subprocess.run(cmd, …)</code> with no <code>env=</code>. When a user
or a test sets <code>HOME</code> to a temporary directory but leaves <code>CLAUDE_CONFIG_DIR</code>
exported, <code>boost explain</code>, <code>search --smart</code> and the other <code>core/ai.py</code>
paths start a <code>claude</code> child that writes its session record into the real configuration
home.

MCP registration already handles this. <code>mcphost.escapes_home</code> detects a config home outside
<code>paths.home()</code> and refuses unless <code>--force</code> is given. The AI path neither detects
it nor says anything.

Before choosing a fix, settle one thing. A child that keeps the real
<code>CLAUDE_CONFIG_DIR</code> is also how it finds the user's credentials, so stripping or redirecting
it may just turn the call into an auth failure that degrades to the heuristic. The options are: warn
once; skip the CLI backend when <code>escapes_home</code> fires; or decide it is acceptable, because a
session record is not configuration, and write that down. Measure what the real CLI does in each case
before picking one.
