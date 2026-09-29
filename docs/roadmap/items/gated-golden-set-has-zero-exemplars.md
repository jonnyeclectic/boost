---
id: gated-golden-set-has-zero-exemplars
board: code
section: shipped
status: shipped
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: CLAUDE.md presents exemplar pinning as a live migration — "relevance is still decided…
order: 214
owner: loop/gated-golden-exemplars
pr: "994"
title: The exemplar mechanism was applied to the ungated set only: golden.jsonl is 0/91 pinned, and 10 of its 43 hit@1 credits are on names the metric cannot adjudicate
---
<b>Measured.</b> On the 10,731-entry corpus that committed <code>taps.txt</code> materializes today, <code>tests/eval/golden.jsonl</code> — the only set the required <code>eval</code> gate floors — is 0/91 exemplar-pinned while the ungated <code>golden-natural.jsonl</code> is 50/50; 10 of its 44 hit@1 credits (22.7%) are awarded on a name that resolves to more than one distinct body, and the hit@1 floor's entire headroom is 7.60 queries, smaller than the 10 credits the metric cannot adjudicate.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code># 0. confirm which corpus you are on (expect 10152)</code><br>
<code>.venv/bin/python -c "import sys;sys.path.insert(0,'.');from boost_cli.core import catalog;print(len(catalog.all_entries()))"; echo EXIT=$?</code><br>
<code># 1. exemplar counts per set</code><br>
<code>python3 -c "</code><br>
<code>import json</code><br>
<code>for f in ['tests/eval/golden.jsonl','tests/eval/golden-natural.jsonl']:</code><br>
<code>    r=[json.loads(l) for l in open(f) if l.strip() and not l.startswith('#')]</code><br>
<code>    print(f,'rows:',len(r),'with exemplar:',sum(1 for x in r if x.get('exemplar')))"; echo EXIT=$?</code><br>
<code># 2. the harness's own list of undecided gated rows</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The defect is real and the spine is exact, but five figures are stale by one corpus refresh. The finding measured on the 10,152-entry corpus CLAUDE.md documents; committed <code>tests/eval/taps.txt</code> moved on 2026-09-01 (cbc0a58b) and now materializes 10,731 entries, which is what <code>make eval</code>/CI builds today. Corrected values, all measured by me on that corpus:

- hit@1 credits: 43/91 = 0.473 -&gt; <b>44/91 = 0.484</b> - un-adjudicated share of credits: 23.3% -&gt; <b>22.7%</b> (the count stays <b>10</b>) - floor headroom: 6.60 queries -&gt; <b>7.60 queries</b> - worst-case bound stripping all 10: 33/91 = 0.363 -&gt; <b>34/91 = 0.374</b> (still below the 0.400 floor) - BM25 four-metric line: 0.852 / 0.473 / 0.605 / 0.657 -&gt; <b>0.841 / 0.484 / 0.607 / 0.655</b>

The finding's numbers are correct for the corpus it names and it disclosed the provenance honestly; they are nonetheless the wrong numbers to print about "the set the required eval gate floors", because the gate no longer builds that corpus. A card must publish the 10,731 figures and name the corpus.

Nothing else in the finding is wrong. 0/91 vs 50/50, the 27 undecided rows / 62 candidate bodies, the same 10 names and 10 queries, the skill-creator worked example, the not-carded check, and the "realistic shift is 1-2 queries, the floor still passes" bound all hold on BOTH corpora.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

1. WHAT IS CORPUS-INDEPENDENT (identical on 10,152 and 10,731): exemplar counts 0/91 and 50/50; 27 undecided worksheet rows over 62 candidate bodies; the same 10 ambiguous-credit names and the same 10 queries; the skill-creator example. Only the credit count and the two ratios moved. Build the card on the invariant half and quote the 10,731 figures for the rest.

2. TRAP FOR THE NEXT VERIFIER: the shared read-only <code>$TMPDIR/eval-home</code> is a PRE-REFRESH corpus — its <code>.eval-corpus-ready</code> sentinel digest does not match <code>sha256(tests/eval/taps.txt)</code>, and 10 of its 20 clones sit at a different commit. Anyone who measures only there reproduces the finding's old numbers verbatim and marks it CONFIRMED without noticing. Rebuilding at the committed pins in a disposable HOME took ~3 minutes and is what produced the correction.

3. DO NOT COPY Makefile:126, which still comments "over twenty it scores 0.863 / 0.473 / 0.607 / 0.662". That matches neither corpus (10,152 gives 0.852/0.473/0.605/0.657; 10,731 gives 0.841/0.484/0.607/0.655). CLAUDE.md:67's figures are right for the old corpus and now also stale.

4. SCOPE OF MY REPRO: I verified the BM25 engine only (<code>--engines bm25</code>), which is what the gate floors; I did not build a dense store (impossible here). I did not run <code>make eval</code> end to end, only its second command against a corpus I materialised with its first.

5. NOT A DEFECT IN THE HARNESS: <code>exemplar_worksheet</code> (scripts/eval_retrieval.py:219) and exemplar grading work correctly and fail loudly on a bad pin.

<b>Why it is worth doing.</b> golden.jsonl is the set the required <code>eval</code> gate floors, so it is the only one that can block a merge. 23.3% of its hit@1 credits are awarded on a name that maps to several genuinely different skills, and the floor's whole margin (6.60 queries) is narrower than the un-adjudicated credit count (10). That does not mean retrieval is worse than reported — the realistic shift is 1-2 queries — it means the published margin cannot be read as precision about the intended skill, so anyone tuning blend weights or pool depth against this gate inherits an unquantified slack.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>

<b>Shipped.</b> All 91 rows of <code>tests/eval/golden.jsonl</code> now pin an <code>exemplar</code>, so the required gate grades by content class rather than by name. <code>--worksheet</code> reports 0 rows still name-graded, and <code>prepare_row</code> raises on a spec that resolves to nothing, so a stale pin fails the gate rather than quietly weakening it.

<b>The pins are a judgment, so they were made as one.</b> 64 of the 91 rows resolved to a single body and were pinned by lookup. Clustering the remaining 27 rows' candidate bodies mechanically (difflib ratio 0.90) collapsed 7 of them to a single re-publication cluster, pinnable as a list by <code>diff</code> rather than opinion. That left <b>20</b> genuine homonym rows, each judged by an agent under one rule — keep a cluster if a user typing this query would be correctly served by it; two independent implementations of the same job both count; drop only a cluster doing a different job — and each judgment then attacked by two adversarial verifiers, one hunting over-narrow pins and one hunting over-broad. 60 agents, <b>0 of 20 decisions refuted</b>, 19 of 20 at high confidence. Two clusters were dropped: Sentry's <code>brand-guidelines</code> (copy-writing, not a visual brand system) and oh-my-agent's <code>pdf</code> (PDF&rarr;Markdown conversion, which cannot fill a form field).

<b>What the measurement did, and did not, do.</b> Scored per query against the old set and the new on the same 10,731-entry corpus, <b>exactly 1 of 91 rows changed</b>. The other 90 grade identically under name and content class, which is the honest result: on this corpus the name was already selecting the right body almost everywhere, and the value of pinning is that it can no longer stop doing so silently. The one mover is the set's only two-name row (<code>style an html artifact with a color and font theme</code>, relevant <code>theme-factory</code> + <code>web-artifacts-builder</code>): <code>relevant</code> is documented as names that <em>count as a correct top hit</em> — alternatives — but <code>recall@k</code> over a two-element set scored 0.5 for finding one of them. The four pinned bodies are one class, so it scores 1.0, and the aggregate moved 76.5/91 &rarr; 77.0/91. <code>hit@1</code> and <code>MRR</code> are bit-identical.

BM25 over the twenty taps: 0.841 / 0.484 / 0.607 / 0.655 &rarr; <b>0.846 / 0.484 / 0.607 / 0.659</b>. All four floors still clear, and none was moved &mdash; margins are now 7.8% / 17.3% / 14.3% / 12.1%, a 2.21x spread, recall@k binding at 6.0 queries of 91.

<b>The cost, recorded rather than discovered later.</b> A pin is <code>tap::skill_md</code>, so the set can only be scored over a corpus holding that tap. The six-repo comparison figure in <code>Makefile</code> is therefore <b>historical</b>, not stale: today's <code>golden.jsonl</code> cannot be scored over six taps at all. It stays re-derivable &mdash; <code>git show e11a34f2:tests/eval/golden.jsonl</code> over a six-tap corpus reproduces 0.989 / 0.769 / 0.848 / 0.880 to three places. <code>taps-scale.txt</code> is unaffected: it is a superset of <code>taps.txt</code> (149 rows &supe; 20), so <code>eval-scale.yml</code> keeps scoring the same set. The real exposure is <code>eval-corpus-refresh.yml</code>, whose re-baseline step is not <code>continue-on-error</code>: a monthly pin move past a renamed file now stops 141 pinned rows instead of 50, and the pull request does not open. That is the intended signal and is written up as a non-obvious rule in <code>CLAUDE.md</code>.
