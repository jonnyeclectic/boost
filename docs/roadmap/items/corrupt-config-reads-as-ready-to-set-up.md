---
id: corrupt-config-reads-as-ready-to-set-up
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: M
impact: Med
wow: 3
note: Doctor has no config-integrity check. When ~/.boost/config.json fails to parse, confi…
order: 202
owner:
pr:
title: With a corrupt config.json, doctor reports "no registries tapped" and verdicts "● ready to set up" exit 0 while search is dead; heal says "nothing to heal"
---
<b>Measured.</b> With a corrupt <code>~/.boost/config.json</code> on a machine holding 1 tap clone (<code>repos/verify-30-fix</code>) and its catalog cache (<code>cache/verify-30-fix.json</code>), <code>boost doctor --json</code> returns <code>{"issues": 0, "ok": true, "verdict": "ready to set up — tap a registry to make boost searchable"}</code> with exit 0 and no corruption entry anywhere in its <code>checks</code> array, on the same machine where <code>boost search brainstorm</code> exits 1 with "no taps configured — nothing to search" — because the only notice of the corruption is emitted by <code>config.load()</code> before <code>report.Report</code> exists and is routed to stderr (<code>config.py:205-210</code>), so it can never be counted, never reach <code>--json</code>, and never reach <code>boost doctor &gt; health.log</code>.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt; || exit 1</code><br>
<code>export HOME=$TMPDIR/audit-doctor-verify3; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>python3 tests/make_fixture.py $TMPDIR/audit-doctor-fix3 &gt;/dev/null</code><br>
<code>./boost tap $TMPDIR/audit-doctor-fix3 &gt;/dev/null 2&gt;&amp;1</code><br>
<code>BOOST_ASSUME_YES=1 ./boost install brainstorming &gt;/dev/null 2&gt;&amp;1</code><br>
<code>printf '{"taps": [' &gt; "$BOOST_HOME/config.json"</code><br>
<code>ls -1 "$BOOST_HOME/repos" | wc -l          # 1 clone still on disk</code><br>
<code>./boost doctor; echo "DOCTOR_EXIT=$?"      # "no registries tapped" ... "● ready to set up", 0</code><br>
<code>./boost heal; echo "HEAL_EXIT=$?"          # "✓ nothing to heal", 0</code><br>
<code>./boost search brainstorm; echo "SEARCH_EXIT=$?"   # "no taps configured", 1</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The BEHAVIOUR is exactly as claimed. Every source citation in the finding is wrong.

1. FILE PATH. The finding says "quality.py" with no directory and implies core. The file is <code>boost_cli/commands/quality.py</code>. There is no <code>boost_cli/core/quality.py</code> (<code>sed</code> on that path errors: No such file or directory).

2. VERDICT BRANCH. Finding says <code>quality.py:744-750</code>. Actual: the block is lines <b>727-736</b>, with <code>if issues == 0 and not taps:</code> on line <b>728</b> and <code>rep.verdict(True, "ready to set up — tap a registry to make boost searchable")</code> on 729-730.

3. ORPHANED-STORE-DIR CHECK. Finding says <code>quality.py:646-651</code>. Actual: <b>612-618</b> (<code>orphans = [c.name for c in sorted(root.iterdir()) ...]</code> at 613, <code>bad("orphans", ...)</code> at 617-618).

4. These line numbers were never right. I checked HEAD, HEAD~1, HEAD~2, HEAD~3, HEAD~5 and HEAD~10 (verdict line 728/728/723/723/720/720; orphan line 617/617/614/614/611/611) and the three other copies in the tree (.claude/worktrees/bmad-autopilot: 631/537; build/lib: -/510; mutants/: the block is absent). Nothing anywhere has 744 or 646, so this is not stale line numbers from a recent move — it is a miscount.

5. WORDING OF THE FINDING'S "printed above doctor's own heading".

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SCOPE OF MY REPRO — do not let a card overstate it: - I measured <b>1 clone + 1 catalog cache</b> on disk against "0 taps synced". The finding's "a user who has been using boost for months" is extrapolation, not measured. State the disparity as "N clones on disk vs 0 taps reported" and cite N=1 as what was actually verified. - I did NOT test <code>boost tap --defaults</code> (needs network). The claim that following doctor's advice re-taps defaults over the real list is unverified; what IS verified is that any tap write quarantines the old file to <code>config.json.corrupt</code> first, so the list is recoverable. That mitigation is why Med holds rather than High. - Fixture-tap repro only; no claim about a starter/default registry set.

THREE ROADMAP PRECEDENTS — none is a duplicate, all must be cited by the author: - <code>docs/roadmap/items/audit-doctor-findings.md</code> (shipped, PR #656) fixed THIS EXACT CLASS — an "!" line that wears the issue glyph but is never counted, under a "● healthy" exit-0 verdict — but only for the crash-report notice. The config-corrupt warning is a second instance that fix did not reach, and is harder because it originates outside doctor's own code. - <code>docs/roadmap/items/audit-verify-drift-say-nothing-installed-exit-0-and-doctor-says-lo.md</code> (shipped, PR #674) is the lock-file sibling and ships the FIX PATTERN to copy: <code>lockfile.check()</code> returning ok/missing/corrupt instead of the empty skeleton <code>read()</code> collapses to, plus <code>store.has_content()</code> to tell a genuinely empty install from one whose record vanished.

<b>Why it is worth doing.</b> This is the worst wording doctor can choose for the state: a user who has been using boost for months is told they are a new user who has not set anything up yet, with a zero exit code, and the repair command agrees there is nothing wrong. Following the printed advice (<code>boost tap --defaults</code>) re-taps the defaults over their real registry list — recoverable only because a <code>.corrupt</code> sidecar happens to be written, which neither doctor nor heal mentions. Doctor already knows how to compare on-disk state against a record (the orphaned-store-dir check); the same comparison against <code>repos/</code> would turn this into one accurate line.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
