---
id: ai-cli-calls-inherit-the-real-config-home
board: code
section: trust
status: shipped
category: Core · Bug
complexity: S
impact: Low
wow: 1
note: explain / search --smart run the claude CLI with the parent environment, so a sandboxed HOME still writes into the real config home
order: 369
owner: loop/ai-cli-env
pr: 1057
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

<b>Shipped</b>, by a fourth route, a CLI flag. The third option's stance covers only the residual bookkeeping named below. <code>aihost</code>'s Claude row now passes
<code>--no-session-persistence</code>, and <code>CLAUDE_CONFIG_DIR</code> is left alone, so the
child keeps the user's login. The flag exists in Claude Code from 2.0.63 (absent from the published
<code>cli.js</code> of 2.0.61 and 2.0.62, present in 2.0.63) and is listed in the installed
2.1.295's <code>--help</code>. In 2.0.63's bundle, the transcript writer's <code>appendEntry</code>
returns before it creates <code>projects/</code> or any file when the flag is set. Measured with
the published 2.0.63 <code>cli.js</code>, no login, a fresh empty <code>CLAUDE_CONFIG_DIR</code> each
time: <code>echo hi | claude -p --output-format text</code> fails at the login check and still leaves
three <code>projects/&lt;cwd&gt;/*.jsonl</code> files, while the same call with the flag leaves no
<code>projects/</code> directory at all. A new test runs <code>ai.ask</code> against a stand-in <code>claude</code> under a
sandboxed <code>HOME</code> with <code>CLAUDE_CONFIG_DIR</code> pointing outside it, and fails on
the old argv because the transcript lands there. What the flag does not cover is the CLI's own
<code>.claude.json</code> bookkeeping, which every run of the user's CLI already does. Redirecting
it would cost the credentials. Gemini needs nothing: it has no config-home variable, so a
sandboxed <code>HOME</code> already contains it.

An older CLI rejects the flag. Run against the published 2.0.62 <code>cli.js</code> under a sandboxed
<code>HOME</code>, it prints <code>error: unknown option '--no-session-persistence'</code> and exits 1,
which would have sent every AI command on that version to the heuristic. <code>ai._ask_cli</code> now
retries once without the flag, but only when stderr is an "unknown option" error that names it
(<code>aihost.rejected_headless</code>), so an auth failure is never retried. Measured through
<code>ai.ask</code> on 2.0.62: the first call fails on the option and the retry gets past option
parsing to the login check. On a CLI that old the transcript is still written, as it always was.
