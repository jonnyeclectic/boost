---
id: search-relevance-meter-is-constant-on-default-page
board: code
section: planned
status: planned
category: UX · Bug
complexity: M
impact: Med
wow: 3
note: format_search_row renders aurora(meter(frac), meter_hue(frac)) with frac = score / ma…
order: 233
owner:
pr:
title: The relevance meter and its "one gradient moment" are constant on the default result page: 138/150 rows full bars, 150/150 the same colour
---
<b>Measured.</b> Over 10 real queries at the default <code>--limit 15</code> against the 10,152-entry eval corpus, 138 of 150 rendered rows draw an identical full <code>▰▰▰▰</code> bar and 150 of 150 land in the same cyan band — 8 of the 10 queries render a byte-identical meter on every single row — because <code>frac = score / max(shown score)</code> needs <code>frac &lt; 0.875</code> to drop one of four bars while BM25's top-15 spread is only 2.2%-19.8% (min/top ratio 0.802-0.978).

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>./boost search quarkus          # every row draws ▰▰▰▰</code><br>
<code>./boost search 'code review'    # every row draws ▰▰▰▰</code><br>
<code>.venv/bin/python - &lt;&lt;'PY'</code><br>
<code>import json,subprocess,collections,os</code><br>
<code>QS=["code review","quarkus","python testing","docker kubernetes deploy","react component",</code><br>
<code>    "security audit","database migration","git commit message","terraform aws","documentation writing"]</code><br>
<code>bars=collections.Counter(); hues=collections.Counter(); rows=0</code><br>
<code>for q in QS:</code><br>
<code>    d=json.loads(subprocess.run(["./boost","search",*q.split(),"--limit","15","--json"],</code><br>
<code>                capture_output=True,text=True,env=dict(os.environ)).stdout)</code><br>
<code>    top=d[0]["score"]</code><br>
<code>    for e in d:</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Every primary measurement reproduced to 3 decimal places (150 rows, bars {3:12, 4:138}, hues {cyan:150}, 8/10 queries uniform, the 580-row limit-60 histogram, all ten minratios). Three secondary claims are wrong:

1. "The meter costs 7 fixed columns of every search row (<code>output._SEARCH_FIXED = 7</code>)" and "At COLUMNS=40 those 7 cells are 17.5% of the pane spent on a constant." WRONG. <code>output.py:626-630</code>'s own comment defines the 7: "the 4-glyph meter, a space, the 1-column installed mark, a space." Two of the seven are the installed <code>●</code> and its space — and the mark is NOT constant; it varies per row and is the one glyph in that block that carries information. It would survive dropping the meter. Correct figures: the meter is 4 glyphs = 10.0% of a 40-column pane, or 12.5% counting its separator space. Not 17.5%.

2. "the widest single element after the name". WRONG at every width where the kind column survives (cols &gt;= 48). At the default 80 columns the real plan is SearchLayout(name_w=21, kind_w=10, tap_w=0, desc_w=36) — both the kind column (10) and the description (36) are wider than the whole 7-cell fixed block, let alone the meter's 4. At 100+ cols the tap column is 20.

3. The "Visible, unaided" excerpt pairs the LAST five rendered rows with the FIRST five scores.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO — a card author must not overstate this:

1. Measured BM25-only. The eval home has no dense store; its own footer says "semantic search is off — install the extra". That IS the default install path (a plain <code>pip install boost-skill-cli</code> is BM25-only), so the finding's framing is fair. But on a machine with the <code>[rag]</code> extra AND a built or imported dense store, <code>retrieve_any</code> fuses and the score reaching the meter is <code>rag.rrf_fuse</code>'s <code>sum 1/(60 + rank)</code>, not a BM25 score. By reasoning (NOT measured — a dense build is impossible in this sandbox, the BAAI model cannot be downloaded): a hit at rank 15 in one engine only scores ~0.41 of a two-engine rank-1 hit, which is bar 2 and violet, so the meter would show real variation there. The card should say "on a BM25-only install", not "always".

2. Corpus direction, unmeasured but worth stating honestly: the live catalogue is ~71k items with many mirror copies (the quarkus run above already shows 4 near-identical <code>quarkus-security</code> rows), so BM25's top-15 spread on a real install would compress further, not less. Nothing here suggests the effect is an artifact of the small eval corpus, but I did not measure a 71k install — I deliberately did not run against the user's real <code>~/.boost</code>.

3. The finding's test-coverage claim is correct and can be stated for BOTH helpers, not just <code>meter</code>. <code>tests/unit/test_output.py</code> TestMeter (lines 691-714) and the <code>meter_hue</code> tests (lines ~1400-1421) exercise only synthetic fractions — 1.0, 0.66, 0.659, 0.33, 0.329, 0.0, and clamps at 1.5/2.5/7.5/-1.0/-3.0.

<b>Why it is worth doing.</b> The meter costs 7 fixed columns of every search row (<code>output._SEARCH_FIXED = 7</code>) — the widest single element after the name — and on the default page it carries no information: it is a proportional bar over a quantity that is near-constant by construction, so it reports "top hit" for the 15th result as loudly as for the first. That is precisely the problem BOOST-D07 was raised to solve ("the ranking is invisible — every row looks equal ...

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
