---
id: search-footer-overflows-40-col-pane-gate-passes-by-luck
board: code
section: planned
status: planned
category: UX · Bug
complexity: M
impact: Med
wow: 3
note: tests/functional/test_cli_pane_width.py asserts _widest(r.out) &lt;= cols for boost sear…
order: 232
owner:
pr:
title: <code>boost search</code>'s footer overflows a 40-column pane by 2-15 cells, and the gate that swears it doesn't passes only because its fixture returns exactly one match
---
<b>Measured.</b> On the gate's <b>own</b> 5-item fixture at COLUMNS=40, changing the query from <code>brainstorming</code> to <code>workflow</code> — nothing else — takes <code>_widest(r.out)</code> from 40 (passes) to 41 (fails), because the footer goes from <code>1 match · ranked by full-content BM25</code> (39 cells) to <code>2 matches · ranked by full-content BM25</code> (41 cells): the gate's green is a property of the singular noun, not of the code. On the 20-tap corpus the same footer measures 55 cells at COLUMNS=40 (over by 15) via the <code>hit_cap</code> branch.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>.venv/bin/python - &lt;&lt;'PY'</code><br>
<code>import os,subprocess,sys</code><br>
<code>sys.path.insert(0,".")</code><br>
<code>from boost_cli.core import output</code><br>
<code>for C in (40,48,60,80,120):</code><br>
<code>    env=dict(os.environ); env["COLUMNS"]=str(C)</code><br>
<code>    r=subprocess.run(["./boost","search","code","review"],capture_output=True,text=True,env=env)</code><br>
<code>    lines=r.stdout.splitlines()</code><br>
<code>    w=max((output.visible_len(l) for l in lines),default=0)</code><br>
<code>    print("COLUMNS=%-4d widest=%-4d %s" % (C,w,"OVER by %d"%(w-C) if w&gt;C else "ok"))</code><br>
<code>    for l in lines:</code><br>
<code>        if output.visible_len(l)&gt;C: print("      %3d | %s" % (output.visible_len(l), l))</code><br>
<code>for q in (["quarkus"],["minio"]):</code><br>
<code>    env=dict(os.environ); env["COLUMNS"]="40"</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three of the finding's file:line refs are stale against current HEAD (9b70fc8e). A card author copying them lands in the wrong place:

1. <code>hit_cap = len(hits) &gt;= k</code> is at <b>discovery.py:161</b>, not 157. 2. <code>k = max(60, args.limit * 4)</code> is at <b>discovery.py:153</b>, not 150. 3. <code>out.info(out.role(footer, "muted"))</code> is at <b>discovery.py:238</b>, not 239. (<code>discovery.py:234-237</code> for the footer assembly IS correct — 234 is the cap branch, 236-237 the plain branch.) 4. The test-file docstring quote is at <b>test_cli_pane_width.py:15-17</b>, not 14-17 (line 14 is blank).

5. "Every other count on any corpus overflows" is over-scoped. The 8-cell count budget (40 - 2 indent - 3 separator - 27 for "ranked by full-content BM25") is specific to the <b>key-free BM25 label</b>. <code>rag.py:1282-1287</code> ships two other labels and the envelope moves in BOTH directions: - <code>dense vectors</code> → "ranked by dense vectors" is 23, budget 12, so counts up to <code>9999 matches</code> fit at 40. A dense-backed install's plain branch mostly does not overflow. - <code>hybrid RRF (BM25 + dense)</code> → "ranked by hybrid RRF (BM25 + dense)" is 35, budget 0, so <b>nothing</b> fits at COLUMNS=40 — including <code>1 match</code>.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO - The 55 / 54 / 42 / 41 numbers come from the shared 20-tap eval corpus at $TMPDIR/eval-home. They are "how bad on a real catalogue", corpus-dependent. - The load-bearing half is corpus-INDEPENDENT: the arithmetic (2 + len("N match(es)") + 3 + len("ranked by &lt;label&gt;")) and the fixture proof above, both reproducible with only <code>tests/make_fixture.py</code>. A card can be written without any external corpus. - The gate currently passes (4 passed, exit 0). I did not edit any source.

DEDUPE — clean, not carded. I read <code>long-hints-overflow-narrow-panes.md</code> (#555) in full: it enumerates its 11+1 offenders by name (doctor 127, AI-fallback 101, protocol 100, changelog 93, who 87, search's *extra hint* 82, simulate 97) and its "Still open" section names only doctor's ·-joined summaries at 71 and protocol's <code>try it:</code> at 59 — the search footer is absent, and could not be present since 74c4aac9 wrote the long branch after #555. <code>audit-search-findings.md</code> (#770) specifies the footer's new wording and never measures a pane. <code>search-and-browse-visual-refresh.md</code> scopes its 40-column claim to <code>format_search_row</code>, which my measurement confirms still holds (every result row fits at 40 and 48). Also checked BOOST-D23, BOOST-D24, BOOST-D27, cli-output-ignored-the-terminal, cli-audit-2026-08-full-sweep, audit-output-wrap-tokens…, audit-out-table-clips… — none mention search's footer.

<b>Why it is worth doing.</b> A required functional gate is asserting an invariant that is false for every real user, and it stays green because the fixture happens to hit the one count that fits. Anyone reading <code>test_cli_pane_width.py</code> or <code>long-hints-overflow-narrow-panes</code> ("eight overflowing lines became two, and the two are the data lines") believes <code>boost search</code> is width-clean at 40 columns; on a real catalogue the footer wraps in a split pane or narrow tmux window, which is exactly the class of regression PR 555 built the sweep to catch. The footer is chrome by the card's own definition — a match count and an engine label, not data like <code>pulse</code>'s paths or <code>fingerprint</code>'s hash — so nothing exempts it.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
