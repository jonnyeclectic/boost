---
id: mcp-skip-list-absent-from-tool-descriptions
board: code
section: planned
status: planned
category: Interop
complexity: M
impact: Med
wow: 3
note: boost's agent-facing surface duplicates six of its seven load-bearing elements from I…
order: 218
owner:
pr:
title: The skip list — the one bound on boost's triggers — ships in INSTRUCTIONS only, in zero of the seven tool descriptions
---
<b>Measured.</b> Six of the seven load-bearing elements of mcp.INSTRUCTIONS are duplicated into boost_search's description and the seventh — the bound — appears in zero of the seven descriptions: verified both by substring probe and by reading all seven descriptions in full, where the only occurrence of the word "skip" in any description is the rerank-cache sentence ("repeating an identical search skips the LLM"), and "not for", "do not call", "trivial", "too small" and "overkill" return NONE across all seven.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/audit-mcp-surface &amp;&amp; mkdir -p "$HOME"</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home &amp;&amp; export BOOST_NO_AI=1</code><br>
<code>.venv/bin/python -c '</code><br>
<code>from boost_cli.core import mcp</code><br>
<code>from boost_cli.commands import configuration as c</code><br>
<code>d={s["name"]:s["description"] for s in c.REGISTRY.specs()}</code><br>
<code>SKIP="Skip it for a question, a one-line edit, or a command you were just handed"</code><br>
<code>print("tools:", list(d))</code><br>
<code>print("skip list in INSTRUCTIONS:", SKIP in mcp.INSTRUCTIONS)</code><br>
<code>for p in ("one-line edit","just handed","Skip it for"):</code><br>
<code>    print(repr(p),"-&gt; descriptions containing it:",[n for n,v in d.items() if p.lower() in v.lower()] or "NONE")</code><br>
<code>for p in ("has a name","10-15 seconds","the task stays yours","one kind of three"):</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The DEFECT reproduces exactly as stated — the seven-row table, the substring probes, the mcp.py:224-225 location, the three cited tests, and the single-arm eval_tools.py are all correct. Three stated details in the write-up are wrong and must not be copied onto a card:

1. "grep for the literal across the repo returns only mcp.py:224, test_mcp.py:467 (a comment), tests/eval/tool_calls.jsonl, and boost_cli/data/rules/boost-first.mdc:54." INCOMPLETE. My grep also returns tests/unit/test_builtin.py:253 and :399, boost_cli/core/mcp.py:144 and :225, docs/roadmap/items/mcp-check-skills-before-starting-a-task.md:37, docs/roadmap/items/tool-call-eval-tier.md:43, docs/roadmap/items/mcp-zero-setup-and-three-kinds.md:42, and docs/roadmap.html (3 lines). The test_builtin.py hits matter: they are real skip-list assertions, but over the builtin boost-first RULE body, not over any tool description — so they reinforce rather than weaken the finding.

2. not_carded_check says "grepped <code>grep -rn 'one-line edit|just handed|Skip it for'</code> across docs/roadmap/items: no hits." FALSE — there are three (listed above). The finder almost certainly ran an alternation without <code>-E</code>, so it searched for the literal string containing pipe characters. I read all three cards: none covers the description gap, so the conclusion survives, but the stated evidence for it does not.

3.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope of my repro: this is a pure source/text audit, settled entirely against the repo at HEAD (main, 9b70fc8e). I measured NO behavioral effect. No <code>gemini</code> CLI is reachable here and the repo's Tier 3 has no Gemini arm, so "the trigger fires on the excluded prompts" is argued, not measured — the finding asserts it from the description's wording, and I did not and could not test it. The eval-corpus BOOST_HOME was irrelevant to this finding and I used it read-only.

Why Med rather than the finder's High. The asymmetry is unambiguous and violates a rule the repo wrote down twice, which argues for High — and the repo did ship mcp-already-covered-defeater (#479) at impact High on the identical argument (descriptions are the only carrier on Gemini). But the harm direction here is OVER-calling, milder than the under-calling failure #479 fixed, and it is unmeasured. High is defensible on the repo's own precedent; I would not let the card assert a measured behavioral effect either way.

THE ONE THING A CARD AUTHOR MUST NOT GET WRONG — there is a recorded counter-precedent for the obvious remedy. docs/roadmap/items/mcp-one-benefit-nameable-task.md (#355) says the previous pass "declared three triggers bounded by a proportionality note, and the bound beat the triggers every time — judging work 'non-trivial' takes judgement, while 'this turn looks small' is free, and every turn looks small when it opens." So a bound in the agent-facing text has already been measured-by-observation to over-suppress once.

<b>Why it is worth doing.</b> mcp.py's own comments say the bound is what buys the rest of the guidance its credibility — "an unbounded 'check first' gets ignored wholesale" and "a surface that captures work it cannot do gets routed around permanently the first time it misses". On the host where this repo already documented and card-fixed a real miss (the Gemini LangGraph session, PR #479), what actually ships is every persuasive element and none of the restraint. That is the capture the whole surface is written to avoid, delivered by omission on the one host it was rewritten for.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
