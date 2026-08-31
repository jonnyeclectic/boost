---
id: gemini-hooks-host-aware
board: code
section: compat
status: shipped
category: Compat
complexity: M
impact: Med
wow: 4
note: two upstream Gemini bugs found while establishing the schema
order: 9
owner: loop/gemini-hooks-support
pr: 570
title: boost hooks learns a second host — and finds two bugs upstream
---
<code>boost hooks</code> managed Claude Code's <code>settings.json</code> and nothing else,
while Gemini CLI 0.57.0 has had hooks — and a <code>migrate --from-claude</code> path — for
some time. The schema was <b>established, not guessed</b>: from the bundle's own shipped
<code>docs/hooks/*.md</code>, from the JS that actually reads the file
(<code>HookEventName</code>, <code>DEFAULT_HOOK_TIMEOUT</code>,
<code>Storage.getGlobalGeminiDir()</code>), and from observed runs under a throwaway
<code>HOME</code> <i>and</i> cwd — <code>HOME</code> alone does not sandbox Gemini, which
writes project scope to <code>./.gemini</code>.
The block shape turns out to be <b>identical to Claude's</b>. Three differences are
load-bearing, and two of them are upstream defects this work surfaced:
<b><code>timeout</code> is milliseconds, not seconds.</b> Gemini's own
<code>migrateClaudeHook</code> copies the field verbatim, so a 10-second Claude hook becomes a
<b>10-millisecond</b> Gemini one. <code>hookhost.timeout_scale</code> is 1 for Claude and 1000
for Gemini; the mutant that sets it back to 1 is killed by four tests.
<b>The event map has a typo that leaks.</b> Upstream's <code>EVENT_MAPPING</code> keys
<code>SubAgentStop</code> — capital A, a spelling Claude Code never emits — so the real
<code>SubagentStop</code> passes through unmapped and lands in <code>settings.json</code> as an
event the CLI can never fire. Confirmed by probe. boost maps both subagent events to
<code>None</code> and <b>refuses</b> the hook, naming the alternatives, rather than writing one
that is dead on arrival.
<b>And <code>name</code> is really read</b>, which was falsified rather than assumed: Gemini
rejects <code>name: 123</code> with a schema error while accepting boost's output silently.
<code>core/hookhost.py</code> is a pure I/O-free per-host table in the shape
<code>core/mcphost.py</code> already set. Claude's behaviour is byte-preserved — including the
exact row dict of <code>list_hooks</code>, which is why <code>list_all_hooks</code> is a
separate function rather than a new key on the old one.
