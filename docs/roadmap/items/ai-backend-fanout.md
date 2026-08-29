---
id: ai-backend-fanout
board: code
section: shipped
status: shipped
category: Agents · Parity
complexity: S
impact: High
wow: 4
note: the last surface that only spoke Claude — and the one a user can see
order: 13
owner: loop/ai-backends
pr:
title: A Gemini user got the heuristic fallback from every AI command
---
Skills, MCP, rules, workflows and hooks all fan out across agents. <code>core/ai.py</code>
did not: it knew the <code>claude</code> CLI, or <code>ANTHROPIC_API_KEY</code>, and nothing
else. So <code>explain</code>, <code>search --smart</code>, <code>distill</code>,
<code>infer</code>, <code>absorb</code>, <code>evolve</code> and <code>simulate</code> all
degraded to their heuristic fallbacks for a user running Gemini CLI — with a perfectly good
assistant installed. <b>This was the last Claude-only surface, and the one a user actually
sees</b>, because the difference between the two paths is the difference between synthesised
prose and a structural summary.
<code>core/aihost.py</code> is the table, built like <code>hookhost</code>: per-backend facts
as data, testable without spending a token or running a subprocess. Three of those facts are
differences that would otherwise be bugs. <b>Gemini has no
<code>--append-system-prompt</code></b>, so the system text is folded into the prompt body —
passing an unknown flag would make every call fail with a usage error rather than degrade,
which is the one outcome worse than having no AI at all. <b><code>ai.model</code> holds a
Claude id</b>, and <code>gemini -m claude-sonnet-4-5</code> is an error, not a fallback. And
<b>Claude stays first</b>, which is behaviour rather than taste: anyone with both CLIs had
Claude answering before this existed, and reordering would silently change every result.
<b>An existing test caught a real regression.</b> The first model rule asked "does this backend
own the id", which quietly dropped an explicit <code>--model m-x</code> override on Claude.
<code>test_cli_explicit_model_and_timeout</code> went red and was right to. The corrected rule
is <b>"not another vendor's"</b>, not "one of mine": an id no backend claims — a custom alias, a
pinned snapshot — goes through untouched, and only an id another backend plainly owns is
withheld.
<b>Scoped honestly.</b> The direct-API path stays Anthropic-only; someone using Gemini CLI has
the binary by definition, and a second HTTP client is a separate change with its own wire
format and error taxonomy. The eval floors were measured against Claude, and the README now
says so rather than implying the numbers describe every backend.
