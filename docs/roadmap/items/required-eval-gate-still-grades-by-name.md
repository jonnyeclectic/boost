---
id: required-eval-gate-still-grades-by-name
board: code
section: planned
status: planned
category: Tech-debt
complexity: M
impact: Med
wow: 3
note: CLAUDE.md states "Relevance is still decided by name (or by content class when a gold…
order: 243
owner:
pr:
title: The exemplar migration never reached the query set the required gate runs: 0 of 91 rows, and 27 of them have an ambiguous target on the gate's own corpus
---
<b>Measured.</b> Both invocations of the merge-blocking retrieval gate — the Makefile <code>eval</code> target and ci.yml's "retrieval quality gate" step — run <code>scripts/eval_retrieval.py</code> with no <code>--golden</code>, so both take <code>DEFAULT_GOLDEN = tests/eval/golden.jsonl</code>; 0 of that file's 91 rows carry an <code>exemplar</code>, and on the gate's own 20-tap corpus 27 of the 91 rows have at least one target name that resolves to more than one content digest (21 of 77 distinct target names are ambiguous).

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>python3 -c "import json; rows=[json.loads(l) for l in open('tests/eval/golden.jsonl') if l.strip() and not l.startswith('#')]; print(len(rows),'rows;',sum(1 for r in rows if r.get('exemplar')),'with exemplar')"</code><br>
<code>python3 -c "import json; rows=[json.loads(l) for l in open('tests/eval/golden-natural.jsonl') if l.strip() and not l.startswith('#')]; print(len(rows),'rows;',sum(1 for r in rows if r.get('exemplar')),'with exemplar')"</code><br>
<code>grep -n 'DEFAULT_GOLDEN' scripts/eval_retrieval.py</code><br>
<code>sed -n '134,139p' Makefile</code><br>
<code>sed -n '269,279p' .github/workflows/ci.yml</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>python3 -c "</code><br>
<code>import json,glob,collections,os</code><br>
<code>n2c=collections.defaultdict(set)</code><br>
…

<b>Verification found nothing to correct.</b> Every number, <code>file:line</code> and command output above was independently re-derived and matched exactly.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Severity lowered from the claim's High to Medium on a measurement the claim did not make. I inspected the bodies behind the ambiguous names and they are two different things. Genuine homonyms exist — <code>brand-guidelines</code> is Anthropic brand colors vs OpenAI brand colors vs Sentry *copy writing* (three different jobs), and <code>pdf</code> is a general PDF skill vs a workflow that converts PDF to Markdown with one specific tool — but they are a minority, and neither appears among the rank-1 hits. The names that actually score hit@1 through an ambiguous target (skill-creator, slack-gif-creator, theme-factory, prompt-engineering, mcp-builder) are re-publications of one upstream skill across anthropics/skills, composio-community/awesome-codex-skills and sickn33/antigravity-awesome-skills, differing by a few bytes. A "wrong body" there is still a correct answer to the user, so the looseness is much smaller in practice than in principle. I did not adopt the shipped card's "the looseness was latent" finding as a reason: that was measured at hit@1 0.160, where there was nothing for ambiguity to inflate, whereas this set measures 0.484 — a different regime, so it does not transfer.

Floor-margin exposure, with that qualification attached: hit@1 measures 44/91 = 0.484 against a floor needing 37 rows (margin 7 rows) with 10 rank-1 hits landing on an ambiguous name; recall@10 measures 77/91 = 0.846 against a floor needing 71 rows (margin 6 rows) with 20 rows matched only via ambiguous names.

<b>Why it is worth doing.</b> This is the only gate in <code>make check</code> that can fail a merge on retrieval quality, and every retrieval decision validated against it (RRF fusion vs preferring dense, pool depth, whether the LLM rerank earns its keep) inherits the looseness. The project already established the fix and built the harness for it; the required set simply never got migrated, and because the card is closed as shipped nothing tracks the remaining work on the set that matters most.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CONFIRMED</b>. No fix is prescribed here — the measurement is the contribution.</em>
