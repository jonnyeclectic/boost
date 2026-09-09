---
id: exemplar-graded-golden-set-runs-in-no-gate
board: code
section: planned
status: planned
category: Tech-debt
complexity: M
impact: Med
wow: 3
note: The 50-row natural-language golden set is the one place where the project's content-c…
order: 242
owner:
pr:
title: golden-natural.jsonl — the only fully exemplar-graded query set — is invoked by no make target and no workflow, so its numbers can only be produced by a human typing the command
---
<b>Measured.</b> Running the natural set today against the same 20-tap eval corpus prints "REGRESSION vs baseline: catalog.search recall@k: 0.080 -&gt; 0.060 (-0.020)" (BM25 MRR 0.2447 -&gt; 0.237, nDCG 0.2640 -&gt; 0.259) — the snapshot has already drifted, and no Makefile target or workflow passes <code>--golden</code>, so nothing in the repo can ever emit that line.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>grep -n natural Makefile ; echo "makefile grep exit $?"</code><br>
<code>grep -rn natural .github/workflows/ ; echo "workflow grep exit $?"</code><br>
<code>grep -rn 'golden-natural' Makefile .github/workflows/ scripts/ tests/ | sed -n '1,20p'</code><br>
<code>sed -n '1,23p' tests/unit/test_eval_baseline.py</code><br>
<code>python3 -c "import json,hashlib,pathlib; b=json.load(open('tests/eval/baseline.json')); print('baseline keys:',list(b['sets'])); print('current digests:',[p+'@'+hashlib.sha256(pathlib.Path('tests/eval/'+p).read_bytes()).hexdigest()[:12] for p in ('golden.jsonl','golden-natural.jsonl')])"</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. BASELINE NUMBERS ARE WRONG. The claim says the golden-natural row carries "0.350 / 0.160 / 0.245 / 0.259". It does not. tests/eval/baseline.json's <code>golden-natural.jsonl@0d91b0cd8e41</code> BM25 row is <b>0.360 / 0.160 / 0.2447 / 0.2640</b>. The quoted 0.350/0.160/0.245/0.259 are the *pre-migration* ("name-graded (before)") figures at docs/roadmap/items/golden-set-grades-by-name-not-by-skill.md:125; the baseline holds the *post*-migration row from line 126-127 (0.360 / 0.160 / 0.245 / 0.264). The claim read the wrong line of the card.

2. "the only tests that touch it are explicitly synthetic" IS WRONG. tests/unit/test_eval_grading.py reads the REAL shipped file in three live assertions: <code>test_the_shipped_set_has_nothing_left_to_decide</code> (line 217-228, asserts len(rows) == 50 and no unpinned row) and class <code>TestTheMigrationIsFinished</code> (line 247+): <code>test_every_row_pins_an_exemplar</code>, <code>test_every_exemplar_is_well_formed</code>, <code>test_no_exemplar_is_a_localised_copy</code>. Only tests/unit/test_eval_baseline.py is synthetic. The defect survives the correction, because those tests grade the file's SHAPE (row count, exemplar presence and syntax) and never run retrieval — so they cannot move or invalidate a single number in the baseline row. The accurate statement is: automation pins the query set's shape, nothing re-measures its scores.

3.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope and limits of my repro: - The structural half (no <code>--golden</code> in any Makefile target or workflow; <code>--golden</code> defaults to golden.jsonl at scripts/eval_retrieval.py:66/:656) is exhaustive over Makefile, .github/workflows/ and scripts/ — read, not inferred. - The drift measurement was run against a PRIVATE COPY of the shared 20-tap eval corpus (I copied cache/ + config.json into $TMPDIR/lens2-exemplar and never wrote to the shared home). I did not verify that this corpus is byte-identical to the one that produced the committed baseline row: Makefile:130-133 says the corpus "tracks upstream HEAD rather than pinned commits", while CLAUDE.md says every taps.txt row pins a SHA — the repo disagrees with itself there and I did not resolve it. So the -0.020 delta could be corpus movement rather than ranker movement. That distinction does not affect the finding: corpus movement is exactly the thing a re-run is supposed to report, and no re-run happens. - I did not run <code>make eval</code>, <code>make check</code>, or any workflow; I read their recipes. - I did not measure how long a <code>make eval-natural</code> would add (the eval corpus was already materialised for me, so I never paid the tap cost). - <code>catalog.search</code>'s numbers here are near the floor of resolution (3 of 50 queries vs 4 of 50), so its -0.020 is one query; the BM25 MRR/nDCG drift is below the default 0.02 eps and would not have been flagged even if someone ran it.

<b>Why it is worth doing.</b> CLAUDE.md documents the two-set design ("Baselines are keyed by query set (name@content-digest), so one file holds both golden.jsonl and golden-natural.jsonl without either overwriting the other") as if both sets are exercised. Only one is. The set that received 50 hand-made relevance judgments — the project's best available measurement of retrieval quality, and the one whose grading key actually identifies a skill — contributes to no gate and no scheduled monitor, so the investment decays silently. Adding a <code>make eval-natural</code> target (or a non-blocking scheduled run alongside eval-stats.yml) would cost one recipe and turn a frozen snapshot back into a signal.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
