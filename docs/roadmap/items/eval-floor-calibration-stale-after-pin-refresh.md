---
id: eval-floor-calibration-stale-after-pin-refresh
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: CLAUDE.md states the gate's four floors sit "~10% under" measured values of 0.852 / 0…
order: 210
owner:
pr:
title: The 2026-09-01 pin refresh moved the corpus and re-baselined it, but nothing re-derives the floors — CLAUDE.md's "~10% under measured" is now 7.2%–17.3%
---
<b>Measured.</b> The required gate's recall floor has 5.52 queries of headroom out of 91 ((0.8407 - 0.78) x 91), against the 6.55 that CLAUDE.md's published 0.852 implies — one golden query of margin the documentation says exists and does not, because commit cbc0a58b re-baselined the corpus to 10,731 entries and left CLAUDE.md, taps.txt and eval_corpus.py all stating 10,152 / 0.852.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code># 1. the refresh commit moved pins + baseline and nothing else</code><br>
<code>git show cbc0a58b --stat --format='%h %ad %s' --date=short</code><br>
<code>git show cbc0a58b -- tests/eval/baseline.json | grep -E '^[-+].*(recall|hit@1|MRR|nDCG)'</code><br>
<code># 2. what taps.txt records NOW vs what the docs claim</code><br>
<code>awk '!/^#/ &amp;&amp; NF&gt;=3 {s+=$3; n++} END {print "rows:", n, " recorded total entries:", s}' tests/eval/taps.txt</code><br>
<code>grep -n '10,152\|0\.852' CLAUDE.md tests/eval/taps.txt scripts/eval_corpus.py</code><br>
<code># 3. recompute the floor gaps against the committed post-refresh baseline</code><br>
<code>python3 -c "</code><br>
<code>import json</code><br>
<code>b=json.load(open('tests/eval/baseline.json'))['sets']['golden.jsonl@a0617183f8c9']['engines']['BM25 full-content']</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. CAUSAL FRAMING IS WRONG (the headline correction). The title and claim say the 2026-09-01 pin refresh is what made "~10% under" untrue. It was untrue the day it was written. <code>git log -S'~10% under'</code> traces the sentence to 170d52c0 (2026-07-31), whose own commit message says the floors were "re-derived against the 20-tap numbers at the same ~10% relative headroom" against measured 0.863 / 0.473 / 0.607 / 0.662 — at which point the gaps were 9.6% / 15.4% / 14.3% / 12.4%, a 1.60x spread. The refresh WIDENED a spread (1.60x -&gt; 1.82x -&gt; 2.39x); it did not create one. Correct statement: "the floors were never uniformly ~10% under, and the refresh widened the spread from 1.82x to 2.39x."

2. "not the 6.60 the documented number implies" — 6.60 matches nothing. CLAUDE.md's published 0.852 gives (0.852-0.78) x 91 = 6.55 queries; the unrounded pre-refresh baseline 0.8406... gives 6.52. Use 6.55. (The optimism is therefore ~1.03 queries, not 1.1.)

3. "2.4x spread" -&gt; 2.39x (rounding, harmless, but state it as 2.39x on a card).

4. DIRECTION OF DRIFT IS NOT UNIFORM. "every future passing refresh decays the calibration further" is true only of the SPREAD. This refresh moved two floors tighter (recall 8.4%-&gt;7.2%, nDCG 11.8%-&gt;11.5%) and two LOOSER (hit@1 15.3%-&gt;17.3%, MRR 14.0%-&gt;14.3%). A card must not say "the floors tightened."

5.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE THE REMEDY CAREFULLY — the finding's phrase "nothing re-derives the floors" invites exactly the fix 170d52c0 warns against: auto-moving floors on every refresh ("Lowering a threshold deserves suspicion... a floor calibrated on an unrepresentative corpus measures the corpus"). The repo's design is deliberately fixed absolute floors with a relaxed regression-vs-baseline. The CONFIRMED defect is narrower and should be carded as such: the measured values and the "~10%" characterisation are stated in seven places across four files (CLAUDE.md:67,84; tests/eval/taps.txt:25,43; scripts/eval_corpus.py:30,108 and the runtime-printed operator message at :331-334), nothing re-states or guards them after a PASSING refresh, and no test asserts any of them.

SCOPE LIMIT OF MY REPRO #1: I did not re-measure 0.8407 / 0.4835 / 0.6065 / 0.6552. Those are the committed baseline written by cbc0a58b — which is also the finder's only source. Verifying them empirically needs a re-tap at the new pins, which is forbidden here (shared read-only corpus) and needs network. Every derived percentage in this verification inherits that.

SCOPE LIMIT #2: the shared $TMPDIR/eval-home is materialised at the PRE-refresh pins — live total 10,152 vs taps.txt's recorded 10,731, with the same 10 taps PIN-DIFFERS. <code>make eval</code> against it would trip eval_corpus.py's CORPUS DRIFT check, not run the gate.

<b>Why it is worth doing.</b> The "~10% under" statement is the entire published justification for where the four floors sit — CLAUDE.md calls it "loose enough that upstream drift can't flake the build, tight enough to catch a collapse." That is a claim about a margin, and the margin now differs 2.4x across the four metrics with recall the tightest at 5.52 queries out of 91. Because the monthly refresh re-baselines but never re-derives or re-states the floors, and prompts a human only when the refreshed corpus FAILS, every future passing refresh decays the calibration further with no signal at all.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
