---
id: search-caps-the-two-copyable-identifiers
board: code
section: planned
status: planned
category: UX · Bug
complexity: M
impact: Med
wow: 3
note: output.search_layout (output.py:668-690) hard-caps name_w at 32 and tap_w at 20 and h…
order: 229
owner:
pr:
title: <code>search</code> caps the name column at 32 and the tap column at 20 at every terminal width, while the description column grows without limit
---
<b>Measured.</b> At COLUMNS=300 the same two <code>doc-coauthoring</code> rows render their tap as <code>anthropics/skills</code> and <code>sickn33/antigravity…</code> in <code>search</code> while <code>browse</code> prints both taps in full on the identical terminal — and <code>./boost info 'sickn33/antigravity…:doc-coauthoring'</code> returns "Error: no tap named 'sickn33/antigravity…'", so the qualifier <code>info</code> demands cannot be built from the row <code>search</code> shows. Across the 10,152-entry corpus, 714 rows (7.03%) have at least one clipped copy target — a name over 32 cells, or a required tap qualifier over 20 cells — and because <code>name_w</code> and <code>tap_w</code> are <code>min(..., 32)</code> and <code>min(..., 20)</code> with no width term, that 7.03% does not shrink at any terminal width, while the description column grows from 27 cells at 84 columns to 443 at 500.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export BOOST_HOME=$TMPDIR/eval-home</code><br>
<code>python3 -c "import sys;sys.path.insert(0,'.');from boost_cli.core import output as o;[print('cols=%-4d name_w=%d tap_w=%d desc_w=%d'%(c,(l:=o.search_layout(c,['doc-coauthoring'],['skill'],['sickn33/antigravity-awesome-skills'])).name_w,l.tap_w,l.desc_w)) for c in (84,140,300,500)]"</code><br>
<code>COLUMNS=300 ./boost search "wordpress seo blogwriting" | head -1</code><br>
<code>./boost info 'wordpress-centric-high-seo-optim…'</code><br>
<code>COLUMNS=300 ./boost search doc-coauthoring | sed -n '2,3p'</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three cosmetic errors; none touches the defect or any headline number.

1. The finder's layout table is labelled as evidence for BOTH caps but shows <code>name_w=15</code> at every width, because it passes the 15-char name <code>doc-coauthoring</code>. That table demonstrates only the tap cap. The name cap needs a &gt;32-char name; my second table (name_w=32 at cols=84/140/300/500) is the missing half.

2. The finder's repro line pastes <code>wordpress-centric-high-seo-optim…</code> (an extra <code>m</code>); the cell search actually renders is <code>wordpress-centric-high-seo-opti…</code> (31 chars + ellipsis = 32 cells). Both error, but the repro string is not what is on screen. Use the 31+ellipsis form.

3. "browse's plain table prints it in full" — the BEHAVIOR is correct and I verified it, but there is no <code>--plain</code> flag on browse (<code>Error: unrecognized arguments: --plain</code>). The plain table is what browse falls back to when stdout is not a TTY. Also add <code>boost list</code> and <code>boost taps</code>, which likewise print full tap names via the width-aware <code>out.table</code>.

Everything else re-derived exactly: 487 / 379 / 77.8% / 25 into 10 / 10,152 / 162 / 333 / 3.28% / 102 / 17 of 20 (85%) / real name 54 chars.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE LIMIT ON THE 25-into-10 COLLISION — the most important caveat for a card author. That figure is a property of the NAME LIST in <code>boost_cli/data/registries.json</code>, not an observed screen. I measured the 20-tap eval corpus and found ZERO colliding tap cells (<code>{}</code>). Nobody has seen two identical <code>anthropics/claude-c…</code> cells side by side; it requires a machine that has tapped both repos and a query that hits both. So the finding's <code>why_it_matters</code> sentence "two rows from different repos are indistinguishable on screen" is an INFERENCE, not a measurement — a card must word it as "25 of the 487 shipped registries would render as one of 10 identical cells if co-tapped", never as an observed fact. The DEMONSTRATED defect is truncation-breaks-paste (the doc-coauthoring chain above), which is fully reproduced.

MITIGATIONS (why Med and not High): every failure path recovers in one command. The name miss prints closest matches, which included the real 54-char name. The ambiguity error prints BOTH full tap names. <code>search --json</code> carries the full tap verbatim (verified: <code>('doc-coauthoring', 'sickn33/antigravity-awesome-skills')</code>), and <code>browse</code>/<code>list</code>/<code>taps</code> print both identifiers in full.

<b>Why it is worth doing.</b> <code>search</code> is the front door and the row is what a user copies. At real catalogue scale its provenance column stops being an identifier: 25 shipped registries render as one of 10 identical cells, so two rows from different repos are indistinguishable on screen — and the tap is precisely what disambiguates the 102 names that live in more than one tap. The information exists (<code>search --json</code> carries the full tap, <code>browse</code>'s plain table prints it in full, and the ambiguity error names both taps), so the claim is that search's human path withholds the copy target, not that it is unreachable — but the user only learns that after the command they typed has failed.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CONFIRMED</b>. No fix is prescribed here — the measurement is the contribution.</em>
