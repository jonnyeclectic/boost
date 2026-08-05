---
id: gemini-agent-frontmatter-sanitizer
board: code
section: compat
status: planned
category: Bug
complexity: S
impact: Med
wow: 2
note: measured on Gemini CLI 0.53.1 — a boost-installed agent fails Zod validation at startup, and hand-fixes regress on the next sync
order: 97
title: sanitize agent frontmatter for Gemini instead of copying it verbatim
---
boost's Gemini <code>agents/</code> slot copies workflow Markdown into
<code>~/.gemini/agents/</code> <b>verbatim</b> — the deliberate contrast to the
<code>commands/</code> slot, which renders TOML. That is right for the body and wrong for the
frontmatter: taps carry agent files written for <i>other</i> hosts, and Gemini validates the
frontmatter with a Zod schema at startup. Measured with <code>trojan-skill-hunter</code> from the
<code>github/awesome-copilot</code> tap on Gemini CLI 0.53.1: the load fails with
<i>"name: Name must be a valid slug"</i> plus six <i>"Invalid tool name"</i> errors, once per
Copilot tool. Every session greets the user with a validation error for a file boost installed.

<b>The schema, verified against the shipped bundle</b> (docs <code>core/subagents.md</code> +
the validator itself): <code>name</code> must match <code>^[a-z0-9-_]+$</code>, with a separate
optional <code>display_name</code> for the human-facing string; <code>tools</code> entries must be
Gemini built-ins (<code>read_file</code>, <code>replace</code>, <code>grep_search</code>,
<code>run_shell_command</code>, …) or <code>*</code>/<code>mcp_*</code> wildcards, and an
<b>omitted</b> list inherits the parent session's toolset; <code>model</code> is any string — so
<code>model: GPT-5</code> passes validation and then fails at runtime, the worst of both.

<b>The fix is a sanitizer in the Gemini agents-slot materializer</b> (beside
<code>workflows.render_gemini_command</code>): slug-ify <code>name</code> and move the original to
<code>display_name</code>; drop a <code>tools</code> list whose entries are not Gemini's (mapping
Copilot/Claude names one-to-one is guesswork — inheriting the session toolset is the documented
safe default); drop a <code>model</code> Gemini cannot resolve. Body stays byte-identical. Pin the
valid-tool set with a unit test the way <code>tests/unit/test_mcphost.py</code> pins the MCP
grammar, so a Gemini schema change surfaces as a red test rather than a user-visible load error.
Hand-editing <code>~/.gemini/agents/</code> is not a fix: <code>boost sync</code> regenerates the
file from the tap source and the lock's sha256 flags the edit as drift.
