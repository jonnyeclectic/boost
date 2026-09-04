---
id: audit-ai-degrade-note-blames-path-api-keys-regardless-of-cause-sev
board: code
section: dx
status: inflight
category: CLI · UX
complexity: M
impact: Med
wow: 2
note: one static string blames PATH/keys while boost.log records "claude CLI call failed: exit 1"
order: 223
owner: loop/ai-fallback-attribution
pr:
title: "AI degrade note blames PATH/API keys regardless of cause; several commands fall back with no note at all"
---
<code>boost simulate</code> prints <code>! AI features need one of `claude` or `gemini` on PATH, or ANTHROPIC_API_KEY set &mdash; using the heuristic fallback</code> in two situations where that diagnosis is false: under <code>BOOST_NO_AI=1</code> with <code>claude</code> on PATH (AI was disabled by env, not missing), and with AI enabled while <code>~/.boost/logs/boost.log</code> records <code>ai: claude CLI call failed: exit 1: &hellip;workspace has not been trusted&hellip;</code> &mdash; the backend ran and failed. A controlled fake <code>claude</code> exiting 3 reproduces the same misblame for <code>evolve</code>. Meanwhile a second group degrades with <b>no note at all</b> when the call was attempted and failed: <code>explain</code> shows the extractive summary with stderr empty, <code>conflict</code> lists pairs as <code>(heuristic)</code> silently, <code>impact</code> and one-shot <code>chat</code> say nothing, and <code>search --smart</code> spent 4.62&nbsp;s then reported <code>60 matches &middot; ranked by full-content BM25</code> with no rerank-failed warning.

The cause: <code>ai.fallback_note()</code> (<code>boost_cli/core/ai.py:62-71</code>) is one static string; <code>enabled()</code> (<code>ai.py:39-41</code>) and the failure recorded by <code>_log_failure</code> (<code>ai.py:97</code>) are never consulted. The shipped <em>ai-bridge-silent-failure-logging</em> roadmap item added only the debug log line &mdash; the user-facing attribution is the unshipped follow-on. A user with an expired login or untrusted workspace is told to fix a PATH that is fine.

Fix, per the verified recommendation: add <code>ai.unavailable_reason()</code> returning one of disabled (<code>BOOST_NO_AI</code>/<code>ai.enabled=false</code>), no backend (no CLI, no key), or backend-failed (the last <code>_log_failure</code> reason, e.g. <code>claude CLI failed (exit 1) &mdash; see ~/.boost/logs/boost.log</code>). Route <code>fallback_note()</code> through it, and emit the note on stderr in every command where <code>ai.available()</code> was true but <code>ask()</code> returned None: explain, conflict, impact, chat one-shot, <code>search --smart</code>. Docs: regenerate <code>docs/commands.html</code> only if help strings change; update README's AI fallback paragraph if it quotes the note text.

Found by the 2026-08 CLI audit (cluster <code>ai-fallback-misattributed</code>); repro in the audit log. Verified against source 2026-08-31.
