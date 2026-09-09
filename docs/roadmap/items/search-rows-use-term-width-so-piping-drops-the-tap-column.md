---
id: search-rows-use-term-width-so-piping-drops-the-tap-column
board: code
section: planned
status: planned
category: UX · Bug
complexity: M
impact: Med
wow: 3
note: commands/discovery.py:219 builds the search column plan from out.term_width(), which …
order: 234
owner:
pr:
title: <code>boost search</code> rows fit to <code>term_width()</code>, not <code>pane_width()</code>, so a piped search silently loses the TAP column entirely
---
<b>Measured.</b> Piped, <code>boost search orchestrator | grep -c sickn33/antigravity</code> returns 0, while <code>COLUMNS=200</code> on the identical pipe prints that tap in the row — and <code>pane_width</code> has 0 callers in <code>boost_cli/commands/discovery.py</code> against 6 <code>out.term_width()</code> calls, so the search row plan (discovery.py:219) is built from an assumed 80 columns that <code>search_layout</code> (output.py:674-676) then uses to drop the tap column entirely.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>unset COLUMNS</code><br>
<code>echo '--- piped, no COLUMNS:'; ./boost search "orchestrator" 2&gt;&amp;1 | head -3</code><br>
<code>echo '--- COLUMNS=200:'; COLUMNS=200 ./boost search "orchestrator" 2&gt;&amp;1 | head -3</code><br>
<code>grep -n 'pane_width\|term_width' boost_cli/commands/discovery.py</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Four things in the finding are wrong; the defect itself is real.

1. <code>boost_cli/core/output.py:696-699</code> is WRONG for the <code>tap_w = 0; if cols &gt;= 84:</code> gate. The real location is <b>output.py:674-676</b>. Lines 696-699 are inside <code>format_search_row</code>'s docstring.

2. Three of the six <code>out.term_width()</code> line numbers are wrong. Claimed "lines 219, 260, 352, 1043, 1894, 1907"; actual is <b>219, 260, 352, 1058, 1924, 1948</b>. (The count of 6, and <code>discovery.py:219</code> itself, are correct.)

3. <code>pane_width</code>'s docstring is cited as <code>output.py:325-336</code>; the <code>def</code> is at <b>326</b> and the docstring runs <b>327-336</b>. The quoted docstring sentence is verbatim correct.

4. "the provenance … prints fine on a wide TTY" is FALSE for most taps. <code>search_layout</code> caps <code>tap_w</code> at 20 cells (output.py:676), so at <code>COLUMNS=200</code> every tap in the repro is still ellipsised — <code>sickn33/antigravity…</code>, <code>first-fluke/oh-my-a…</code>, <code>OneWave-AI/claude-s…</code>. <b>17 of the 20 eval-corpus taps exceed 20 characters.</b> Separately, the column is present only at cols &gt;= 84, so a real 80-column TTY drops it too — the trigger is "pane under 84 columns", not "stdout is a pipe".

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

LOAD-BEARING for a card author: switching discovery.py:219 to <code>out.pane_width() or _UNPANED</code> (the cli.py:178 pattern, <code>_UNPANED = 10**6</code>) does NOT make <code>boost search … | grep &lt;owner/repo&gt;</code> work. The 20-cell tap cap at output.py:676 still ellipses 17 of the 20 eval-corpus taps, so <code>grep sickn33/antigravity-awesome-skills</code> stays at 0 hits after the implied fix. The fix needs BOTH: fit to <code>pane_width()</code>, and lift the tap cap when there is no pane. The description half IS fully fixed by the pane change alone (descriptions currently clip to an assumed 80 in a pipe and print in full at COLUMNS=200) — a card should lead with that half, which is unambiguous.

SCOPE of my numbers: "17 of 20 taps exceed 20 chars" is measured over the 20-tap eval corpus at $TMPDIR/eval-home only, not over the real 460-tap install. State it with that scope. Everything else is measured against current <code>main</code> source.

NOT ALREADY CARDED — I re-checked independently. The PR 739 card (<code>audit-out-table-clips-data-columns-to-an-assumed-80-columns-when-s.md</code>, shipped) names exactly two emit sites: <code>out.table -&gt; _fit_widths</code> (11 of 12 findings) and <code>cli.print_help</code> (<code>cli.py:169,199-209</code>). Search rows go through <code>out.search_layout</code> + <code>out.format_search_row</code> + <code>out.info</code> and are not among them. <code>cli-output-ignored-the-terminal.md</code> (PR 552) mentions search's tap-drop but describes it as *correct* narrow-TTY adaptation, not the pipe case. <code>audit-search-findings.md</code> touches <code>search_layout</code> only for CJK cell-width.

<b>Why it is worth doing.</b> The tap is the identifier <code>boost install --tap</code> and <code>boost untap</code> take, and it is the only thing that distinguishes the 13 real skills named <code>code-reviewer</code>. A user scripting over <code>boost search</code> (<code>| grep</code>, <code>| awk '{print $4}'</code>) sees a column that exists on their screen and vanishes in their pipeline, with no error. <code>--json</code> exists as an escape hatch, but the same escape hatch existed when PR 739 fixed <code>out.table</code>, and the <code>| grep</code> argument it accepted applies unchanged here.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
