---
id: search-footer-not-fitted-to-the-pane-its-rows-were-fitted-to
board: code
section: planned
status: planned
category: UX · Bug
complexity: S
impact: Low
wow: 2
note: search_layout's docstring guarantees every row measures within cols, and at COLUMNS=4…
order: 231
owner:
pr:
title: The search footer is the one unfitted line on a screen <code>search_layout</code> just fitted: 55 columns in a 40-column pane
---
<b>Measured.</b> The same command measures 55 columns in a 40-column pane in the field and 39 in the test that asserts it fits: <code>tests/functional/test_cli_pane_width.py::TestChromeOnlyCommandsFitAnyPane::test_search[40]</code> passes only because its fixture tap yields exactly one match, whose footer is <code>1 match · ranked by full-content BM25</code> = 39 — one column under the pane.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>COLUMNS=40 ./boost search "code review" 2&gt;&amp;1 | python3 -c "</code><br>
<code>import sys,re,unicodedata</code><br>
<code>A=re.compile(r'\033\[[0-9;]*m')</code><br>
<code>def vl(s):</code><br>
<code>    s=A.sub('',s); return sum(0 if unicodedata.combining(c) else (2 if unicodedata.east_asian_width(c) in ('W','F') else 1) for c in s)</code><br>
<code>for i,l in enumerate(sys.stdin.read().splitlines()):</code><br>
<code>    if vl(l)&gt;40: print('OVERFLOW line%d %d&gt;40: %r' % (i, vl(l), l))</code><br>
<code>"</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three citation errors; all measured numbers are right.

1. The footer emit is <code>boost_cli/commands/discovery.py:238</code>, not 239. 2. The <code>search_layout</code> docstring sentence is <code>boost_cli/core/output.py:665-667</code> (the whole docstring runs 653-668), not 680-682. Lines 680-682 are <code>desc_room()</code>'s body and the <code>tap_w</code> drop test. 3. "thirty lines later in the same module" is wrong: 238 -&gt; 258 is 20 lines. The finding's own <code>why_it_matters</code> already says "20 lines away", so the evidence contradicts itself.

Not a correction but a scope fact the finding did not state: the *other* footer branch also overflows. At COLUMNS=40 with BM25 the widths are 39 (1 match, fits) / 41 (3) / 42 (35 matches, measured) / 55 (cap branch, measured) — i.e. the overflow is 1-15 cells, zero at exactly one match. The smart path pushes it further ("ranked by Claude Haiku relevance" = 59).

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope of my repro: the 20-tap eval corpus at $TMPDIR/eval-home for the field measurement, plus the real <code>tests/make_fixture.py</code> tap in a disposable HOME for the gate fixture. No network, no writes to the shared corpus. The defect is in the emit site, not the corpus — any query returning &gt;1 match reproduces it.

Four things a card author must not get wrong:

1. <b><code>search_layout</code> does not violate its own docstring.</b> Its guarantee is over "every row assembled from the plan"; the footer is not a row assembled from the plan. The title's contrast is rhetorical and true as *juxtaposition* (the fitted rows sit directly above an unfitted line), but a card must not say "search_layout breaks its own guarantee." The law the footer *does* break is the repo's own, stated in <code>tests/functional/test_cli_pane_width.py</code>'s module docstring: "Commands whose whole output boost composed — <code>search</code>, <code>who</code>, <code>protocol</code> — are swept at panes down to 40 columns. Every line is chrome, so every line is boost's to fit."

2. <b>"The one unfitted line" holds only for a screen with results.</b> On the zero-result screen a different line overflows and <code>search_layout</code> never runs: <code>COLUMNS=40 ./boost search zzzqqxnothing</code> emits <code> → try \</code>boost discover zzzqqxnothing\<code> to search all of GitHub</code> at 62 columns. Fixing the footer does not make <code>boost search</code> pane-clean, and a card claiming it does will be wrong the first time someone types a miss.

3.

<b>Why it is worth doing.</b> The footer is chrome (a count and a ranker name), so the wrap law permits fitting it — nothing on that line is data the user must copy. Leaving it unfitted means the one screen boost spent a whole frozen <code>SearchLayout</code> dataclass fitting still wraps on a narrow pane, and it wraps on the summary line, breaking the visual bottom edge of the result block. The fix is one call already used 20 lines away in the same file.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
