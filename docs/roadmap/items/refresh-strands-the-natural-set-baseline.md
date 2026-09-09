---
id: refresh-strands-the-natural-set-baseline
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: eval-corpus-refresh.yml:119 runs eval_retrieval.py --save-baseline -k 10 with no --go…
order: 227
owner:
pr:
title: The corpus refresh re-baselines only golden.jsonl, so golden-natural.jsonl's baseline silently describes a corpus that no longer exists
---
<b>Measured.</b> On the corpus tests/eval/taps.txt pins today (10,731 entries, 20 taps), <code>eval_retrieval.py --golden tests/eval/golden-natural.jsonl -k 10</code> exits 1 and prints "REGRESSION vs baseline: catalog.search recall@k: 0.080 -&gt; 0.060 (-0.020)" — while the keyword set on that identical corpus exits 0 and reproduces its baseline to four decimals (0.841/0.484/0.607/0.655), because the September refresh commit cbc0a58b moved golden.jsonl's baseline and left golden-natural.jsonl's describing the 10,152-entry corpus it replaced.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code># 1. the refresh re-baselines with no --golden, and the default is golden.jsonl</code><br>
<code>sed -n '112,119p' .github/workflows/eval-corpus-refresh.yml</code><br>
<code>grep -n 'DEFAULT_GOLDEN\|--golden' scripts/eval_retrieval.py</code><br>
<code># 2. the refresh commit changed ONLY the golden.jsonl set</code><br>
<code>git show cbc0a58b -- tests/eval/baseline.json | grep -nE 'golden|^[-+] *"(recall|hit)'</code><br>
<code># 3. the natural baseline still holds pre-refresh numbers</code><br>
<code>python3 -c "</code><br>
<code>import json;s=json.load(open('tests/eval/baseline.json'))['sets']</code><br>
<code>for k,v in s.items(): print(k, v['engines']['BM25 full-content'])"</code><br>
<code># 4. and they reproduce exactly on the PRE-refresh corpus</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The mechanism and every load-bearing measurement are correct. Four stated details are wrong:

1. LINE NUMBER. <code>if drop &gt; eps:</code> is at scripts/eval_retrieval.py:545, not 546. (The other three cited lines are exact: DEFAULT_GOLDEN at 66, <code>--golden</code> default at 656, <code>--regression-eps</code> default 0.02 at 668, and the workflow's bare <code>--save-baseline</code> at eval-corpus-refresh.yml:119.)

2. ROADMAP FILENAME. The finding's not_carded_check names <code>nothing-refreshes-the-eval-corpus-pins</code>; no such file exists. That string is the card's TITLE. The file is docs/roadmap/items/eval-corpus-pins-have-no-refresh-path.md (status: shipped, pr: 431). Its conclusion still stands — I read it, and its only baseline sentence is "regenerate <code>baseline.json</code>", singular, with nothing about which sets a refresh maintains.

3. TITLE COUNT. "Checked all 318 titles" — there are 432 item files (405 <code>board: code</code>, 27 <code>board: design</code>). I re-ran the not-carded check over all 432 and reached the same conclusion.

4. UNDERSTATED, NOT OVERSTATED — the important one. The finding frames the false regression as a future risk ("a 2-query shift (0.040) reports a confident REGRESSION"). It is not future. On the corpus the current taps.txt pins, the natural set ALREADY exits 1 today with <code>REGRESSION vs baseline: catalog.search recall@k: 0.080 -&gt; 0.060 (-0.020)</code> — the drop computes to 0.020000000000000004, which clears eps=0.02.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO — what it does and does not settle. - It settles the mechanism completely: I read the current workflow and argparse default, walked every commit that ever touched baseline.json, and confirmed cbc0a58b is the first to move one set of two. - It settles the consequence empirically, which the finding did not: I built the post-refresh corpus (network fetch of the 8 moved pins onto copies of the shared clones, in HOME=$TMPDIR/verify-5, since deleted) and got a real exit-1 false regression on the natural set with a clean exit-0 control on the keyword set. That pair is the card's evidence — one command, two sets, same corpus, opposite results. - Measurement noise seen: BM25 MRR on the natural set came out 0.235 on the --build run and 0.237 on the next run against the same index. Do not quote the natural set's post-refresh MRR to three decimals in a card. recall@k (0.360), hit@1 (0.160) and the catalog.search regression line were stable across both runs.

BLAST RADIUS — do not overstate it in the card. The natural set is NOT wired into any gate. <code>make eval</code> and CI run golden.jsonl only, and both pass <code>--regression-eps 1</code>, so the required gate is untouched and stays green. grep for golden-natural across *.py/*.yml/Makefile/*.sh finds it only in tests/unit/test_eval_baseline.py and test_eval_grading.py (which test the harness, not the corpus) plus CLAUDE.md and roadmap prose.

<b>Why it is worth doing.</b> CLAUDE.md documents baseline keying as the fix for exactly this class of bug: "Before that, running the natural-language set printed eight confident 'REGRESSION vs baseline' lines that were only the gap between two different question sets." The key was made query-set-aware but not corpus-aware, and the monthly refresh only maintains one of the two sets. The natural set is the only instrument the project has for measuring whether a user's plain-English question finds the right skill (it scores BM25 at recall 0.360 / hit@1 0.160, and 0.077 / 0.000 on its 13 workflow rows) — so it is the set that matters most for judging the keyless-dense work, and its reference point is now silently wrong.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
