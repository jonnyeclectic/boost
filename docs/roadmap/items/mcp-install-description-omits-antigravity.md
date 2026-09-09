---
id: mcp-install-description-omits-antigravity
board: code
section: planned
status: planned
category: Interop
complexity: S
impact: Low
wow: 2
note: boost_install's description says installs are "wired into every agent you have enable…
order: 216
owner:
pr:
title: boost_install's description enumerates four of the five enabled agent targets, and gives Antigravity the one mechanism it does not use
---
<b>Measured.</b> The enumeration is provably stale rather than deliberately partial: the string was written in PR #442 on 2026-08-03, when boost had four agent targets, and Antigravity CLI landed as a FIFTH -- and a LINKING -- target in PR #602 on 2026-08-30 (<code>git merge-base --is-ancestor</code> confirms #442 precedes #602), and the string has not been touched since; today <code>enabled_agents()</code> returns 5 and <code>linking_agents()</code> returns 4 while the description names 4 and 3 of them respectively, and <code>boost_install</code> is the only one of the seven MCP tool descriptions that names any agent at all -- so the fix is a single string.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>rm -rf $TMPDIR/audit-mcp-f4 $TMPDIR/audit-mcp-f4-fix</code><br>
<code>export HOME=$TMPDIR/audit-mcp-f4 &amp;&amp; export BOOST_HOME=$HOME/.boost</code><br>
<code>export BOOST_NO_AI=1 &amp;&amp; export BOOST_ASSUME_YES=1 &amp;&amp; mkdir -p "$HOME"</code><br>
<code>.venv/bin/python tests/make_fixture.py $TMPDIR/audit-mcp-f4-fix &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/audit-mcp-f4-fix &gt;/dev/null 2&gt;&amp;1</code><br>
<code>.venv/bin/python -c '</code><br>
<code>from boost_cli.commands import configuration as c</code><br>
<code>from boost_cli.core import agents</code><br>
<code>print("linking_agents -&gt;", list(agents.linking_agents()))</code><br>
<code>print("enabled_agents -&gt;", list(agents.enabled_agents()))</code><br>
<code>txt,_ = c.REGISTRY.call("boost_install", {"name":"brainstorming"})</code><br>
<code>print(txt.splitlines()[1])</code><br>
<code>d={s["name"]:s["description"] for s in c.REGISTRY.specs()}</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Two stated details are wrong; the defect itself is real.

1. THE TITLE OVER-CLAIMS. "gives Antigravity the one mechanism it does not use" states something about the text that the text does not do. The description does not ASSIGN Antigravity any mechanism -- it omits Antigravity entirely (verified: <code>antigravity in any description: False</code>, and 0 hits for 'antigravity' in both mcp.py and configuration.py). The finder's BODY is careful and correct ("the only claim an Antigravity reader can map onto itself"), but that is an inference about how a reader would map itself, not a measured property of the string. A card title ships literally. Correct title: "boost_install's description enumerates four of the five enabled agent targets and omits Antigravity CLI, the fourth linking agent."

2. THE FINDER'S GREP WAS MALFORMED, so its cited "no matches" is not reproducible as meant. <code>grep -n 'Windsurf|Cursor|symlink|gemini' tests/unit/test_mcp.py</code> is BASIC grep -- the pipes are literal characters, so it could only ever match a line containing that exact string. With <code>grep -inE</code> the file has FIVE matches (lines 493, 571, 623, 687, 738). The CONCLUSION survives: I read all five and none pins boost_install's agent enumeration (they are Gemini-CLI-instructions-delivery comments and one tap name).

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO: fully in scope, no caveat needed. The defect is a static source string plus two pure functions over config defaults, so the 20-tap eval corpus is irrelevant here and I never touched it. Antigravity's <code>enabled</code> comes from config defaults (agents.py:25, <code>bool(spec.get("enabled", True))</code>), not from <code>~/.gemini</code> existing, so the repro does not depend on any Antigravity install being present -- I got all five agents from a bare disposable HOME with only the test fixture tapped.

BONUS STALENESS THE FINDER MISSED, same cause and same PR: the explanatory comment at boost_cli/commands/configuration.py:1467-1468 quotes the output as <code>only "linked agents: claude-code, windsurf, cursor"</code> -- a three-agent list. The real line now emits four (<code>linked agents: claude-code, windsurf, cursor, antigravity</code>, per my repro). If the card ships a fix, that comment should be corrected in the same edit or it becomes a second stale artifact of #602.

WHY THIS IS THE HOST WHERE IT BITES (supports relevance, already established in-repo, not something I had to infer): <code>core/mcphost.py:13,86,94</code> registers boost with <code>agy</code> -- Antigravity CLI is its third MCP host -- so an Antigravity agent genuinely reads this exact description. And the design comment at configuration.py:1575-1582 states that on Gemini-family hosts the function declarations are "the only boost text reliably in context at the moment an agent chooses a tool" (server <code>instructions</code> land in the trust-gated GEMINI.md memory tier).

<b>Why it is worth doing.</b> The harm is the wrong mechanism, not the missing name. The install reply already tells Gemini-family users that a skill is usable without linking, and the comment above that line (configuration.py:1466-1470) says why it exists: an agent that does not see itself in the linked list "concludes the skill did not reach *it*, and goes back to reconstructing the work by hand." An Antigravity CLI agent reading only the description gets the inverse error — the sole Gemini-family claim on offer says the store is read directly, which for Antigravity is false, so a pre-install answer to "will this reach me" is wrong in the direction the surface was written to avoid.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
