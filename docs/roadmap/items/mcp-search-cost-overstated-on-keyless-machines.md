---
id: mcp-search-cost-overstated-on-keyless-machines
board: code
section: planned
status: planned
category: Interop
complexity: M
impact: Med
wow: 3
note: boost_search's description and INSTRUCTIONS both state the cost as a flat "10-15 seco…
order: 217
owner:
pr:
title: boost_search advertises "10-15 seconds" unconditionally; with no AI configured it is 0.013 s median and the rerank never runs
---
<b>Measured.</b> With no AI backend available, boost_search over 20 distinct queries against the 10,152-entry eval corpus returned in a median of 0.0134 s (min 0.0057 s, max 0.1206 s, and 0.075 s for the first search in a fresh process) while both MCP surfaces state an unconditional "10-15 seconds — an LLM reranks every match" — because rag.py:1129 returns the retrieval order untouched when <code>ai.available()</code> is False, so no LLM call is ever made.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/audit-mcp-surface &amp;&amp; mkdir -p "$HOME"</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home &amp;&amp; export BOOST_NO_AI=1</code><br>
<code>.venv/bin/python -c '</code><br>
<code>import time, statistics</code><br>
<code>from boost_cli.commands import configuration as c</code><br>
<code>from boost_cli.core import ai</code><br>
<code>print("ai.available() -&gt;", ai.available(), "(rag.py:1129 returns the retrieval order unreranked when False)")</code><br>
<code>Q=["set up code review","add commit conventions","write a migration","debug flaky tests","python testing","react hooks","terraform module","docker compose","ci pipeline","security audit","api documentation","database schema","kubernetes deploy","git hooks","typescript lint","rust async","llm prompt","data pipeline","monorepo build","code"]</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. THE HEADLINE MULTIPLIER IS MISLABELED. "790x-2,240x over-stated at the median" mixes two statistics: 2,240x is 15s / 0.0067s, the finder's MIN, not its median. At the finder's own median (0.0126s) the range is 794x-1,190x; at my reproduced median (0.0134s) it is 746x-1,119x. A card must say ~750x-1,200x at the median, or drop the point multiplier entirely (see notes on corpus scope).

2. configuration.py:1271-1290 is wrong for <code>_ranking_note</code>. It is at lines 1275-1294 (def at 1275).

3. mcp.py:428-447 for <code>engine_note</code> — the def is at line 427 (body 427-447).

Everything else in the finding checked out exactly: rag.py:1129 is verbatim <code>if not ai.available():</code> followed by <code>return hits[:limit], engine</code>; tests/unit/test_mcp.py:200-201 and :545 are the exact assertions quoted; the quote from mcp-search-hid-which-ranking-ran.md ("A boost installed with pipx has neither inside its venv unless the key is exported, so the silent path is the common one rather than the edge case") is verbatim; the captured reply line is verbatim; and both surfaces do carry "10-15 seconds" as an unconditional literal with no hedge for machine state.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE LIMITS OF MY REPRO — a card author must not overstate any of these:

1. CORPUS-DEPENDENCE OF THE MULTIPLIER. My timings are against the 20-tap / 10,152-entry eval corpus. The repo's OWN shipped card <code>mcp-search-cost-was-understated.md</code> measured the same rerank-off path at 0.10 s — ~8x slower than my median — which yields 117x-170x, not three orders of magnitude. The real user install is ~71,700 items (7x the eval corpus again). The defect is unaffected, but the headline number is not robust: write it as "two to three orders of magnitude, corpus-dependent" and name the corpus, never a bare "2,240x".

2. THE 10-15 s NUMERATOR IS INHERITED, NOT RE-MEASURED. I could not verify it here. With BOOST_NO_AI unset, <code>ai.available()</code> returned True (the <code>claude</code> shim is on PATH) yet the rerank still fell through to BM25 at 0.80-0.94 s and the reply carried the "did NOT run" note — a sandbox CLI-shim artifact, not evidence about real machines. The 11.7-17.0 s figure comes from <code>mcp-search-cost-was-understated.md</code>, not from me.

3. BOOST_NO_AI=1 IS A PROXY, AND THE "COMMON CASE" PREMISE IS INHERITED. On this machine <code>claude</code> is on PATH, so <code>ai.available()</code> is naturally True and the keyless state was simulated. The proxy is fair — <code>available()</code> is <code>enabled() and (has_cli() or ANTHROPIC_API_KEY)</code>, and both routes hit the identical rag.py:1129 branch — but I did NOT observe a keyless machine. The "pipx has neither inside its venv" premise is the sibling card's assertion restated, and it is loose reasoning: <code>has_cli()</code> calls <code>shutil.which</code>, which reads PATH, not the venv.

<b>Why it is worth doing.</b> The stated cost is not decoration — mcp.py's own comment calls it load-bearing ("The stated COST kills the hesitation over an unknown-price call") and it is the sole justification for the "WORTH THE SECONDS" gate that tells an agent to search only when the request touches more than one file or outlives the session. On the machine this repo calls the common one there are no seconds, so the gate suppresses a free call on a false price — the mirror of the defect the mcp-search-cost-was-understated card fixed in the other direction, and with the same consequence: "a wrong cost in the one paragraph whose job is to make the tool worth reaching for discredits everything around it." An agent that …

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
