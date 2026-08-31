---
id: gemini-mcp-parity
board: code
section: compat
status: shipped
category: Compat
complexity: M
impact: Med
wow: 3
note: audited what Gemini actually receives — two of three findings were our own wrong claims
order: 8
owner: loop/gemini-mcp-audit
pr: 569
title: What Gemini actually receives from boost, audited
---
"Do Gemini hooks invoke boost's MCP the same way Claude does?" turned out to be two questions
with different answers, and answering them properly cost three of our own claims.
<b>MCP tools: yes. The guidance around them: not by the same route.</b> boost is registered and
<code>Connected</code> in Gemini, and the tools are callable. But the server sends 2,622
characters of <code>instructions</code> at <code>initialize</code> that <b>Gemini never delivers
in interactive mode</b> — <code>Config.initialize()</code> does not await
<code>mcpInitializationPromise</code>, so <code>getMcpInstructions()</code> returns empty and the
context entry is stamped once and short-circuits. That was already known and test-pinned here.
What compensates is not the MCP surface at all: it is the <code>boost-first</code> rule
materialised into <code>GEMINI.md</code>, which carries the full trigger text.
<b>Hooks: no, and it is not close.</b> <code>boost hooks</code> manages Claude Code's
<code>settings.json</code> and nothing else. Gemini CLI 0.57.0 does have hooks — with a
<code>migrate --from-claude</code> path — and boost knows nothing about them.
<b>Two of the three findings were our own errors, not Gemini's.</b> The claim that
<code>boost_list</code>'s declaration "carries no trigger vocabulary" came from probing it for
<code>boost_search</code>'s words; three of the clauses were already there, and the real gap was
narrower — it asserted <i>instant</i> without ever saying <i>why</i>, so the mechanism (a local
file read, not a search) is now named. And <code>mcphost.py</code>'s reason for omitting the
<code>--</code> separator was <b>wrong at the version it claimed verification against</b>: the
v0.46.0 tag has that yargs block byte-identical, and <code>populate--</code> plus
<code>unknown-options-as-args</code> mean the separator is merely redundant, never hazardous.
The argv was correct for a reason nobody had checked. Re-verified against 0.57.0 by reading the
bundled yargs definitions and running every argv under a throwaway <code>HOME</code> <i>and</i>
CWD — Gemini writes project scope to <code>./.gemini</code>, so <code>HOME</code> alone does not
sandbox it.
