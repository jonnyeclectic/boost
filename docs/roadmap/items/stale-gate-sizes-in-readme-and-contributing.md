---
id: stale-gate-sizes-in-readme-and-contributing
board: code
section: planned
status: planned
category: Quality · Docs
complexity: S
impact: Low
wow: 2
note: README.md:515 says make smoke is "176 checks" and CONTRIBUTING.md:123 says bash tests…
order: 235
owner:
pr:
title: The contributor-onboarding gate tables state three wrong suite sizes, and README and CONTRIBUTING disagree with each other
---
<b>Measured.</b> One command (<code>make smoke</code> is literally <code>bash tests/smoke.sh</code>, Makefile:48-49) is documented as three different sizes in three files — 176 in README.md:515, 170 in CONTRIBUTING.md:123 and 170 again in docs/openssf-badge.md:123 — while it actually runs 183 checks, a figure that is deterministic and statically derivable as 102 top-level <code>run</code> lines plus 81 <code>--help</code> entries in the CMDS heredoc.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>sed -n '48,49p' Makefile          # make smoke == bash tests/smoke.sh</code><br>
<code>bash tests/smoke.sh 2&gt;&amp;1 | tail -1 # == results: 183 passed, 0 failed</code><br>
<code>sed -n '515p' README.md            # "176 checks"</code><br>
<code>sed -n '123,124p' CONTRIBUTING.md  # "170 end-to-end checks" ; "11 features, 47 scenarios"</code><br>
<code>HOME=$TMPDIR/audit-bdd BOOST_HOME=$TMPDIR/audit-bdd/.boost .venv/bin/behave tests/bdd/features --dry-run 2&gt;&amp;1 | tail -2</code>

<b>Verification found nothing to correct.</b> Every number, <code>file:line</code> and command output above was independently re-derived and matched exactly.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

1. THE FINDING UNDERCOUNTS THE BLAST RADIUS. It names two files; there are three. <code>docs/openssf-badge.md:123</code> carries both stale numbers ("170 end-to-end checks" and "11 features, 47 scenarios") in the row that answers the OpenSSF <code>test</code> MUST criterion. That makes five stale statements across three files, not three across two. The finder's not_carded_check grepped roadmap bodies but never grepped <code>docs/</code>, which is how it missed this. A card that fixes only README and CONTRIBUTING leaves a stale count in the file that argues boost's test coverage to an external badge audit.

2. TWO ARE DRIFT, ONE WAS WRONG ON DAY ONE — do not write the card as uniform "drift". Re-deriving the count at each blame commit: README's 176 was CORRECT at 3aaf4ba4 (2026-08-28, PR #579) and has since drifted to 183; CONTRIBUTING's 170 was CORRECT at c043bb3f (2026-07-24, PR #233) and was never touched again; CONTRIBUTING's "47 scenarios" was CORRECT at 17bd5003 (2026-07-28, PR #292). But docs/openssf-badge.md's 170 was WRONG WHEN IT WAS WRITTEN — at 560652b1 (2026-08-28, PR #563) the suite already ran 176. It copied CONTRIBUTING's already-stale number rather than measuring. That is the sharper story: the count is not just drifting, it is being propagated by copy from whichever file the author happened to read, which is exactly the failure mode the finding's "no way to tell which is authoritative" line predicts.

3. 183 IS DETERMINISTIC — a card author must not "correct" it.

<b>Why it is worth doing.</b> These two tables are the contributor's map of what <code>make check</code> will do to their PR, and a first-time contributor reads whichever file they landed on. Seeing 183 where the doc promised 176 (or 170) is a signal the gate changed under them; worse, the two files disagree, so there is no way to tell which is authoritative without running the suite. The BDD row is the same failure in a suite that is not even in <code>make check</code>, where a wrong size is the only signal a contributor has that scenarios were added.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CONFIRMED</b>. No fix is prescribed here — the measurement is the contribution.</em>
