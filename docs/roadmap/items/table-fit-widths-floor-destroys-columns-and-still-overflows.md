---
id: table-fit-widths-floor-destroys-columns-and-still-overflows
board: code
section: planned
status: planned
category: UX · Bug
complexity: M
impact: Med
wow: 3
note: out.table's _fit_widths has floor=1, and _clip_visible(cell, 1) returns just the elli…
order: 237
owner:
pr:
title: _fit_widths shrinks data columns to a bare "…" and still overflows: <code>boost taps</code> is 54 columns wide on every terminal narrower than 54
---
<b>Measured.</b> At COLUMNS=80 — a default terminal width, not a narrow split — <code>boost hooks list</code> renders 5 of its 6 columns (host, scope, event, name, matcher) as a bare "…" for every row INCLUDING the header, so the table no longer says what its own columns are, and the row is still 89 columns wide (94 on a color TTY) against a natural 142: five columns of data destroyed, 15 columns of ink spent on placeholders, and the fit still not achieved — dropping those five columns outright would have measured 74 and fit.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>for w in 53 54 55 56 58; do printf "COLUMNS=%s: " $w; COLUMNS=$w ./boost taps 2&gt;&amp;1 | sed -n '2p'; done</code><br>
<code># and the width measurement:</code><br>
<code>for w in 20 40 50 55; do printf "COLUMNS=%s widest_row=" $w; COLUMNS=$w ./boost taps 2&gt;&amp;1 | python3 -c "</code><br>
<code>import sys,re,unicodedata</code><br>
<code>A=re.compile(r'\033\[[0-9;]*m')</code><br>
<code>def vl(s):</code><br>
<code>    s=A.sub('',s); return sum(0 if unicodedata.combining(c) else (2 if unicodedata.east_asian_width(c) in ('W','F') else 1) for c in s)</code><br>
<code>ls=sys.stdin.read().splitlines(); print(max(vl(l) for l in ls), 'over=', max(vl(l) for l in ls)-int('$w'))</code><br>
<code>"; done</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

1. NAME column is 39 columns wide, not 40. The finding says "NAME (40 cols) is therefore unshrinkable". Longest tap name in the corpus is <code>composio-community/awesome-codex-skills</code> = 39. The constant 54 decomposes as 39 + 2 + 5(ITEMS header) + 2 + 1 + 2 + 0(curated ★, empty here) + 2 + 1.

2. EVERY figure in the finding is a PIPED (no-color, sep=2) figure, and the "why it matters" is about real terminals, where <code>use_color</code> makes sep <code>" │ "</code> = 3 columns. On a color TTY the same rows are: taps floor row = 58 (not 54), and the two dead cells + separators cost 8 (not 6); hooks list floor row = 94 (not 89). Verified with <code>BOOST_COLOR=always</code>. A card that ships "54" describes a pane nobody is looking at.

3. Line numbers drifted. Actual, on current <code>main</code> (9b70fc8e): <code>_fit_widths</code> is output.py:809-831 (claimed 801-823); <code>_clip_visible</code> is 781-806 and its <code>keep = width - len(ellipsis) if width &gt; len(ellipsis) else 0</code> is line 788 (claimed 762-765); <code>table()</code>'s "widest text column is shrunk" docstring sentence is 856-858 (claimed 846-849). Correct as claimed: the <code>fmt</code> clip at 901 (claimed 900-903) and <code>taps.py:351</code> (out.table at 351, <code>keep=("NAME",)</code> at 352).

4. The <code>COLUMNS=20 over=34</code> and <code>COLUMNS=40 over=14</code> numbers are NOT evidence of the floor bug and must not be used as such.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO - taps figures are the 20-tap READ-ONLY eval corpus at $TMPDIR/eval-home (longest name 39). On the real ~445-tap install the NAME column is wider (BOOST-D24's card cites <code>K-Dense-AI/claude-scientific-skills</code> = 44), which shifts the whole band upward. Do not ship "54" as a universal constant — ship the mechanism plus the corpus it was measured on. - hooks list figures are this machine's own <code>~/.claude/settings.json</code> (2 hooks, longest command 74 chars). <code>boost hooks list</code> reads HOME, not BOOST_HOME, so those numbers are install-specific too. - The other four <code>keep=</code> call sites (quality.py:1007/1569/1596, pkg.py:1750) were not exercised — they need attestations / fingerprints / snapshots I did not create. - <code>boost list</code> (no <code>keep=</code>) degrades correctly: at COLUMNS=20 and 40 its table rows fit; the only over-wide lines are chrome hint lines, which is a different, separate issue.

THREE THINGS A CARD AUTHOR MUST NOT GET WRONG 1. <code>floor=0</code> is NOT the fix, and the card must not propose it. For taps the dead columns are TRAILING, so <code>.rstrip()</code> eats their separators and floor=0 would give 46 — a fit. For hooks list the dead columns are LEADING: 0+2+0+2+0+2+0+2+0+2+74 = 84, still over 80. Only dropping the column AND its separator (the shape <code>search_layout</code> already implements, output.py:651-689, with a stated drop order and an explicit "every row measures within cols for any terminal 40 cells wide or more" guarantee) reaches 74. 2.

<b>Why it is worth doing.</b> A 50-column pane (a vertical split, a phone SSH session, a narrow tmux pane) is a realistic terminal. On it <code>boost taps</code> spends 6 columns printing two ellipses that say nothing, hides both the last-update date and the URL for all 20 taps, and *still* wraps every row — so the user gets neither the data nor the fit. The right answer for a column squeezed below a readable floor is to drop it (the shape <code>search_layout</code> already implements, with a stated drop order), not to render a placeholder that costs ink and carries nothing.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
