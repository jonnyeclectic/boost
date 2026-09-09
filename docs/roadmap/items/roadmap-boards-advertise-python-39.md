---
id: roadmap-boards-advertise-python-39
board: code
section: planned
status: planned
category: Quality · Docs
complexity: S
impact: Low
wow: 2
note: docs/roadmap.html:17141 and docs/design-roadmap.html:582 both close with Install with…
order: 228
owner:
pr:
title: The two roadmap boards' install footers still advertise Python 3.9+, four minor versions under the real floor
---
<b>Measured.</b> On stock macOS <code>python3</code> (3.9.6), the exact command in both roadmap footers succeeds silently and installs the wrong software: <code>pip download --no-deps boost-skill-cli</code> exits 0 with no Requires-Python notice and selects boost_skill_cli-1.0.392, because 390 of 557 published releases still declare <code>requires_python: &gt;=3.9</code> — 167 releases behind the current 1.2.103.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>for f in docs/*.html; do printf '%-22s %s\n' "$(basename $f)" "$(grep -m1 -n 'foot-note' $f)"; done | grep -o 'Python 3\.[0-9]*+' | sort | uniq -c</code><br>
<code>grep -n 'requires Python 3.9' docs/roadmap.html docs/design-roadmap.html</code><br>
<code>sed -n '206p' docs/design-roadmap.html</code><br>
<code>grep -n 'requires-python' pyproject.toml</code><br>
<code>.venv/bin/python scripts/build_roadmap.py --check ; echo "EXIT=$?"   # green despite the drift</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The documented defect (<code>claim</code> + <code>evidence</code>) reproduces byte-for-byte — every file, line number and count is right: 9 of 11 footers say 3.12+, roadmap.html:17141 and design-roadmap.html:582 say 3.9+, design-roadmap.html:206 says "targets Python ≥ 3.9", pyproject.toml:22 is &gt;=3.12, README.md:54 says 3.12+, and <code>build_roadmap.py --check</code> exits 0. The correction is confined entirely to <code>why_it_matters</code>, which is wrong three times:

1. WRONG: "the launcher on that interpreter dies with a SyntaxError out of core/workflows.py's match statements." The <code>./boost</code> launcher no longer gates at 3.9 — <code>grep -n '3\.9' boost</code> returns nothing (exit 1), and boost:5, boost:27 and boost:37 all say 3.12. Observed on a PATH holding only Python 3.9.6, the launcher prints <code>boost: Python 3.12+ is required but was not found on PATH / hint: brew install python3</code>. It never selects the 3.9 interpreter.

2. WRONG even if the gate is bypassed: importing the package on 3.9 does not raise SyntaxError from <code>core/workflows.py</code>'s match statements. It raises <code>ImportError: cannot import name 'UTC' from 'datetime'</code> at <code>boost_cli/core/util.py:15</code>, which fires before workflows.py is reached.

3. WRONG about the failure being visible at all. The footer's advertised path is <code>pip install boost-skill-cli</code>, not the launcher.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO: everything above was measured on this checkout at the session's HEAD (main, 9b70fc8e) and against live PyPI. No eval corpus or BOOST_HOME was involved — this is a static docs/metadata finding, so the 20-tap corpus caveat does not apply. I did not run a real <code>pip install</code> (only <code>pip download</code>, which exercises the same resolver and version selection without mutating anything).

NOT CARDED — confirmed independently. I grepped all roadmap item titles, then every item body containing <code>3.9</code> (21 files) and every item body containing <code>footer</code>/<code>foot-note</code> (16 files). None names the docs/*.html install footers or their Python version. Three near misses, all genuinely distinct: - <code>audit-root-findings.md</code> covers the *launcher's* three 3.9 sites and explicitly closes "README already says 3.12+ — no doc change needed"; it never mentions a docs page. - <code>python-floor-moves-to-312.md</code> enumerates pyproject, the CI matrix and telemetry; no docs page. - <code>promote-nav-footer-into-the-shared-style-system.md</code> is about nav/footer *presence and styling*, not their text.

TRAP FOR THE CARD AUTHOR — do not re-import the SyntaxError claim. The finder took it from <code>docs/roadmap/items/audit-root-findings.md:36-43</code>, which is still <code>status: planned</code> but whose premise is already fixed on disk: that card says the launcher "still gates at Python 3.9" at boost:5/:27/:37, and all three now say 3.12. Anyone who reads that card while writing this one will copy a consequence that no longer happens.

<b>Why it is worth doing.</b> Both boards are linked from the README ("Roadmap" section, README.md:490-494) and from the Visual Guide nav, so they are landing surfaces a reader can arrive on first. Their footer is the only install instruction on the page, and it tells the reader a Python 3.9 will do. It will not: stock macOS <code>python3</code> IS 3.9, and the launcher on that interpreter dies with a SyntaxError out of core/workflows.py's match statements. The design board's "targets Python ≥ 3.9" also mis-sets the floor for anyone writing a proposal against it.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
