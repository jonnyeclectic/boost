---
id: recommend-recomputes-its-columns-per-row
board: code
section: planned
status: planned
category: UX · Bug
complexity: S
impact: Low
wow: 2
note: cmd_recommend hand-rolls its rows and computes desc_w = max(cols - 2 - width - 2 - (l…
order: 226
owner:
pr:
title: <code>boost recommend</code> sizes the description cell per row from that row's <code>because:</code> text, so neither column lines up
---
<b>Measured.</b> At COLUMNS=100 the eight <code>boost recommend</code> rows truncate their descriptions at eight per-row widths spanning 34 to 54 columns — a 20-column swing, the widest cell 59% wider than the narrowest — because <code>desc_w</code> is recomputed inside the row loop from that row's own <code>because:</code> tag length (<code>boost_cli/commands/discovery.py:1062</code>); every rendered cell matched the predicted <code>desc_w</code> to the character and every description ended in an ellipsis, so this is column geometry, not natural description length.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/audit-dbi-sweep; mkdir -p "$HOME"; export BOOST_HOME=$TMPDIR/eval-home BOOST_NO_AI=1</code><br>
<code>COLUMNS=100 ./boost recommend &gt; $TMPDIR/rec.txt 2&gt;&amp;1; cat $TMPDIR/rec.txt</code><br>
<code>python3 - &lt;&lt;'PY'</code><br>
<code>import re,os</code><br>
<code>for line in open(os.environ["TMPDIR"]+"/rec.txt").read().splitlines()[1:]:</code><br>
<code>    m=re.match(r"^  (\S+)\s+(.*?)\s\sbecause: (.*)$", line)</code><br>
<code>    if m: print("desc_cell=%3d because_len=%2d row_len=%d %s"%(len(m.group(2)),len("because: "+m.group(3)),len(line),m.group(1)))</code><br>
<code>PY</code><br>
<code>sed -n '1061,1065p' boost_cli/commands/discovery.py</code><br>
<code>sed -n '638,644p' boost_cli/core/output.py</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The geometry numbers are all CORRECT — I re-derived every one (cells 46/38/46/42/54/34/46/54, because-lengths 19/27/19/23/11/31/19/11, spread 34..54 = 20 columns, row_len 100 on all 8 rows). Four wording/detail claims are wrong and must not ship as written:

1. FALSE AS STATED: "<code>recommend</code> is also the one result table in the find group that does not go through the width-aware shared <code>out.table()</code>." <code>cmd_search</code> does not call <code>out.table()</code> either — it calls <code>out.search_layout()</code> at <code>boost_cli/commands/discovery.py:219</code> and renders through <code>SearchLayout</code>. <code>out.table()</code> in the find group is called by <code>cmd_index</code> (:857), <code>cmd_discover</code> (:954), <code>_browse_plain</code> (:1091, used by <code>browse</code>) and <code>cmd_trending</code> (:1925, :1949). The correct claim: <b><code>recommend</code> is the only find-group result renderer that uses neither <code>out.table()</code> nor a frozen <code>SearchLayout</code>.</b>

2. TITLE OVERSTATES: "so neither column lines up" — and the evidence line "row_len 100 on all 8 — every row is right-flush, nothing is a column" contradicts itself. The <code>because:</code> column's RIGHT edge IS flush (col 100 at COLUMNS=100, col 120 at COLUMNS=120, on all 8 rows). What wanders is (a) the <code>because:</code> column's LEFT edge, 69..89, and (b) the description truncation point, 34..54.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

PROVENANCE (I checked; it partly softens the framing and the card should say so). <code>git blame</code> puts line 1062 in ff61dfeb, "fix(search): width-clamp &amp; truncate results — the D05 overflow fix (#33)", whose message states the intent: "clip each description to the remaining terminal width, so every result stays one scannable line <b>with its trailing tag (★ curated / because:) intact</b>." So preserving the trailing tag was deliberate; the per-row recompute is what that intent produced. The defect is drift, not carelessness: <code>search</code> was later rewritten onto the frozen <code>SearchLayout</code> (7f1a9a8d, "feat(ui): one design system across search and browse", #540) whose docstring states the opposite rule, and <code>recommend</code> was left on the 2026-07 scheme. Neither commit message nor any comment claims right-alignment of the reason tag as a design goal for <code>recommend</code>, so nothing in the tree defends the current shape — but a card that calls it an oversight without naming #33's stated intent is overclaiming.

SCOPE OF MY REPRO. Measured only from the boost repo (detected stack: javascript, python · frameworks: pytest · also: ci) against the shared read-only 20-tap eval corpus at $TMPDIR/eval-home, with BOOST_NO_AI=1 (which suppresses the "AI picks" block — unrelated to the geometry). Which eight rows appear, and therefore the exact cell widths, depend on that corpus and that stack; the geometry itself is deterministic from :1062 and appears whenever the shown rows carry different <code>because:</code> sets.

<b>Why it is worth doing.</b> <code>recommend</code> is the surface a new user hits before they know any skill names, and its output is a ragged block rather than a scannable list — the description truncation point jumps 20 columns row to row for reasons the reader cannot see (it is the length of the reason tag on the right). Two shipped design items (BOOST-D08, BOOST-D24) made <code>out.table()</code> width-aware for ~28 call sites; this one never adopted it, and the frozen-plan rule that <code>search</code> states in its own docstring is inverted here.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
