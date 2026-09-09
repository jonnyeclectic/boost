---
id: corpus-refresh-updates-data-not-prose
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: S
impact: Low
wow: 2
note: .github/workflows/eval-corpus-refresh.yml regenerates taps.txt's data rows and baseli…
order: 201
owner:
pr:
title: The monthly corpus refresh rewrote the pins and the baseline but left every documented number stale — taps.txt now contradicts its own header, and nothing checks it
---
<b>Measured.</b> tests/eval/taps.txt contradicts itself inside one file: its header at line 25 states the corpus is "<b>10,152 entries</b>", while its own twenty data rows fifty lines below sum to 10,731 (<code>awk '!/^#/ &amp;&amp; NF {s+=$3} END {print s}'</code>), and an independent materialisation at exactly those pinned SHAs measures 10,731 entries across 20 taps with sickn33 at 61.8% - verified at HEAD 5ec7ed75.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>git show --stat cbc0a58b</code><br>
<code>grep -n '10,152\|6,309\|62.1\|1,616\|0.852' tests/eval/taps.txt scripts/eval_corpus.py CLAUDE.md Makefile .github/workflows/eval-scale.yml tests/unit/test_eval_corpus.py</code><br>
<code>sed -n '48,70p' tests/eval/taps.txt          # data rows: sickn33 ... 6634, ECC ... 1621</code><br>
<code>awk '!/^#/ &amp;&amp; NF {s+=$3} END {print "pinned rows sum to", s}' tests/eval/taps.txt   # -&gt; 10731</code><br>
<code>.venv/bin/python -c "import json;d=json.load(open('tests/eval/baseline.json'));print(json.dumps(d['sets']['golden.jsonl@a0617183f8c9']['engines']['BM25 full-content'],indent=1))"</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Only one statement in the finding is false, and it is narrow:

1. "the same stale figures propagate to ... the Makefile" is WRONG. The Makefile contains no "10,152" (<code>grep -c '10,152' Makefile</code> -&gt; 0) and Makefile:126 quotes a DIFFERENT, older stale set: "0.863 / 0.473 / 0.607 / 0.662", which matches neither the pre-refresh baseline (0.8516/0.4725/0.6048/0.6575) nor the post-refresh one (0.8407/0.4835/0.6065/0.6552). Makefile:126 is stale prose, but it went stale before this refresh, not because of it. (Makefile:132-133 is separately stale in the other direction: it says the corpus "tracks upstream HEAD rather than pinned commits", untrue since #410 pinned it.) The card must not claim the refresh caused the Makefile drift.

2. Under-count of call sites. The finding lists six files; there are at least four more quoting "10,152", one of which is ACTIVE rather than merely left behind: - scripts/build_scale_corpus.py:189 emits the literal string "# 10,152 entries and a real install carries ~71,655..." into tests/eval/taps-scale.txt on regeneration, so a build step re-writes the stale number. - scripts/build_scale_corpus.py:6, tests/eval/taps-scale.txt:11, tests/unit/test_scale_corpus.py:5. - Also scripts/eval_corpus.py:10 ("affaan-m/ECC alone is 1,616"), which the finding's line list omits.

3.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO. I materialised the corpus at the shipped pins in my own disposable HOME (network reachable, 20 blobless sparse clones) and scored it with the exact <code>make eval</code> invocation, so the 10,731 / 61.8% / 76.9% / 0.841-0.484-0.607-0.655 figures are my own measurements, not the finder's. I did not touch the shared read-only eval-home except to read its caches; that corpus is still at the PRE-refresh pins (sickn33 @ d43065e) and totals 10,152 with sickn33 at 6,309 - which is what let me confirm both sides of the move rather than only the new one. My runs wrote nothing into the repo (<code>git status --short</code> shows only a peer session's four modified boost_cli/tests files, none under tests/eval/ or scripts/).

CORRECTED, not REFUTED, and the correction is small: sizes, shares, line numbers, the baseline match, the monthly cron and "no test covers it" all reproduced exactly. Only the Makefile attribution is wrong, plus an under-count of sites. Do not let CORRECTED read as doubt about the defect.

DO NOT list roadmap item bodies as stale. <code>eval-corpus-was-not-actually-pinned.md</code>, <code>eval-corpus-is-one-strangers-repo.md</code>, <code>eval-corpus-is-96x-smaller-than-a-real-install.md</code>, <code>BOOST-D12.md</code> and the CLI-audit cards all quote 10,152 / 6,309 / 0.852, but they are dated records of a measurement that was true when written. The live surfaces are the ones that must be fixed.

NOT A DUPLICATE, but cross-link it.

<b>Why it is worth doing.</b> taps.txt's header is the primary explanation of what the corpus is and why the floors sit where they do; it now states a size, a concentration and a four-metric score that its own data rows contradict, and CLAUDE.md repeats them as the project's ground truth. The next person reasoning about the corpus (or the next agent re-deriving the floors) reads numbers that are one refresh out of date, and the drift widens every month because the job that causes it is scheduled and nothing fails when the prose and the rows disagree.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
