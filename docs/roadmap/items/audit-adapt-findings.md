---
id: audit-adapt-findings
board: code
section: dx
status: planned
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: a subagent named after a tool renders a crew that compiles but cannot run
order: 247
owner:
pr:
title: "boost adapt: CLI audit findings (2026-08)"
---
<b>A subagent named after a declared tool renders modules that compile but cannot run.</b> With a
subagent <code>grep</code> and tool <code>Grep</code>: crewai emits <code>@tool("grep") def
grep</code> then <code>grep = Agent(...)</code>, so <code>reviewer_1 = Agent(tools=[read,
grep])</code> hands the Agent where a tool belongs (stub run: TypeError); langgraph assigns
<code>grep = create_react_agent(...)</code> inside <code>build_mycrew</code>, making it local, so the
earlier <code>tools=[read, grep]</code> raises UnboundLocalError. <code>_unique_idents</code>
(<code>core/adapters.py:188-202</code>) dedups only among agent specs and <code>_unique_tools</code>
(<code>:205-212</code>) allocates stub names independently. Fix: pass the tool ident set into
<code>_unique_idents</code> as pre-reserved names (or prefix stubs <code>tool_&lt;name&gt;</code>) in
<code>render_crew</code>/<code>render_graph</code>, plus a golden test that executes a colliding
render against stubs.

<br><br><b><code>docs/commands.html</code> brackets required options as optional.</b> Line 369 shows
<code>boost adapt [--to FRAMEWORK] &hellip;</code> while <code>adapt --help</code> prints an
unbracketed <code>--to FRAMEWORK</code> and omitting it exits 2 &mdash; and the verify pass found it
is broader than adapt: evolve's required <code>--feedback</code> and catalog's required
mutually-exclusive group render all-optional too. Pure generator bug:
<code>scripts/build_command_reference.py:122-126</code> brackets every option unconditionally. Emit
required options unbracketed (a required group as <code>(--a | --b)</code>), prefer the short flag
like argparse, then <code>make generate</code> &mdash; the <code>--check</code> gate holds it after
that.

<br><br><b>Colon-form model ids get double-prefixed for the LiteLLM targets.</b>
<code>--model anthropic:claude-x</code> &mdash; the form langgraph accepts <em>and emits</em> &mdash;
renders <code>llm=LLM(model="anthropic/anthropic:claude-x")</code> for crewai and the same for
agents-sdk; multi-agent crews inherit it via <code>adapters.py:376</code>.
<code>_litellm_model</code>'s docstring says a provider-qualified value passes through, but the code
checks only <code>/</code>. Fix: replace the first <code>:</code> with <code>/</code> before deciding
to prefix (mirror of <code>_langchain_model</code>); document accepted syntaxes in
<code>docs/adapters.html</code>'s <code>--model</code> paragraph (~line 344, slash form only today),
and regenerate <code>docs/commands.html</code> only if the argparse help changes.

<br><br><b><code>adapt -o</code> and <code>run --print -o</code> write generated source mode
0600</b> &mdash; and re-rendering over an existing 0644 file silently downgrades it, unlike a shell
redirect (<code>-rw-------</code> vs <code>-rw-r--r--</code> under umask 022).
<code>util.atomic_write_text</code> (<code>core/util.py:91-116</code>) inherits mkstemp's 0600, right
for the lock/config it was written for, wrong for source the user asked boost to write. Fix: add an
optional <code>mode</code> parameter (fchmod the temp fd before <code>os.replace</code>), keep 0600
the default, and have <code>cmd_adapt</code> (<code>pkg.py:1753-1761</code>) and <code>cmd_run</code>
(<code>run.py:62</code>) pass the umask default.

<br><br>Found by the 2026-08 CLI audit (clusters <code>adapt-ident-collision</code>,
<code>docs-required-flag-synopsis</code>, <code>adapt-model-id-syntax</code>,
<code>generated-file-mode</code>); repro in the audit log.
