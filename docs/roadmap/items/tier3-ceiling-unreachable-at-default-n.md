---
id: tier3-ceiling-unreachable-at-default-n
board: code
section: planned
status: planned
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: eval_tools.py judges the should-NOT-call ceiling against the Wilson UPPER bound, but …
order: 238
owner:
pr:
title: Tier 3's false-call ceiling is unreachable at its own default N, and tolerates zero false calls at the N <code>make eval-tools</code> uses
---
<b>Measured.</b> At the argparse default <code>--runs 1</code> (scripts/eval_tools.py:388), a flawless host — 8/8 should-call, 0/8 false-call — is reported <code>FAIL: false-call rate 0.00 [0.00-0.32] over ceiling 0.20 (0/8)</code>, because the Wilson upper bound at k=0 is z²/(n+z²) = 3.8416/(8+3.8416) = 0.3244 and cannot fall under the 0.20 ceiling until n ≥ 16, i.e. <code>--runs ≥ 2</code> over this 8-row half.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>.venv/bin/python - &lt;&lt;'EOF'</code><br>
<code>import importlib.util</code><br>
<code>spec=importlib.util.spec_from_file_location("et","scripts/eval_tools.py")</code><br>
<code>m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)</code><br>
<code>rows=m.load_set(m.DEFAULT_SET); call,nocall=m.halves(rows)</code><br>
<code>print("set: %d call rows, %d no-call rows"%(len(call),len(nocall)))</code><br>
<code>for runs in (1,2,3):</code><br>
<code>    obs={r["id"]:[True]*runs for r in call}</code><br>
<code>    obs.update({r["id"]:[False]*runs for r in nocall})   # a PERFECT host</code><br>
<code>    met=m.score_host(rows,obs); v=m.verdict(met,0.60,0.20)</code><br>
<code>    print("runs=%d  call %d/%d lo=%.4f | false %d/%d hi=%.4f -&gt; %s"%(runs,</code><br>
<code>        met["call_rate"]["k"],met["call_rate"]["n"],met["call_rate"]["lo"],</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

No defect figure is wrong. Every operative number re-derives exactly: 8 call / 8 no-call rows; hi=0.3244 (n=8), 0.1936 (n=16), 0.1380 (n=24), 0.2024 (n=24,k=1); n&gt;=16 required for k=0 to clear 0.20; ceiling tolerates 0 of 24 while the floor tolerates 4 of 24 (fails at 5 = 16.7% miss). Cited locations all correct: scripts/eval_tools.py:388 <code>--runs</code> default=1; docstring lines 53 and 54 pass no --runs (line 51 is --dry-run, 52 carries --runs 3, so "two of four Usage lines" is right); Makefile:176 is the <code>eval-tools:</code> target with <code>--runs 3</code> on 177.

One non-defect number is wrong: the <code>not_carded_check</code> says "Read all 318 <code>^title:</code> lines" — there are 432 item files and 432 title lines. That is the finder's audit-process count, not a figure that would ship on a card. I redid the carded check independently over all 432 and its conclusion holds.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope of my repro: I drove the shipped <code>load_set</code>/<code>halves</code>/<code>score_host</code>/<code>verdict</code> directly and re-derived the Wilson algebra from scratch. I did NOT drive a real host (no <code>claude</code> run, no tokens spent) — that is not needed, because the defect is in the scoring arithmetic, which is fully deterministic and host-independent.

Scoping the finding's one overstatement (a wording nuance, not a wrong number): "can only ever print FAIL" is conditional. <code>main()</code> exits 0 *before* reaching <code>verdict()</code> when <code>claude</code> is not on PATH or <code>BOOST_NO_AI</code> is set, and the ceiling clause is skipped entirely if <code>f["n"]==0</code> (every no-call row unreachable). The precise, proven claim is: <b>whenever the ceiling is actually evaluated at n ≤ 8, FAIL is guaranteed for every possible k</b> — I minimised the upper bound over all k at each n from 1 to 8 and the best case is 0.3244 at n=8.

Three things the finder did not report that a card author will want:

1. <b>The test suite corroborates it by omission.</b> <code>tests/unit/test_eval_tools.py::test_a_perfect_host_passes</code> asserts only the two *rates* and never calls <code>verdict()</code>. On its own 2-call/2-no-call fixture, <code>verdict()</code> returns TWO failures — including <code>false-call rate 0.00 [0.00-0.66] over ceiling 0.20 (0/2)</code>. A test named "a perfect host passes" would fail if it asserted the thing its name claims. The only test that does clear the ceiling, <code>test_enough_runs_do_clear_it</code>, uses 30 runs (n=30, hi=0.1135), and its comment explains the FLOOR, not the ceiling — so the reachable-N constraint is nowhere stated in the suite either.

2.

<b>Why it is worth doing.</b> The card that introduced this tier argues its whole value is having two numbers rather than one — a floor on should-call AND a ceiling on should-not-call — because scoring call rate alone rewards an assertive MCP surface. But the ceiling half is either unsatisfiable (N=8) or a zero-tolerance trip-wire (N=24), while the floor half absorbs a 16.7% miss rate. Anyone running the documented <code>python3 scripts/eval_tools.py …</code> invocation sees a red result on a host that behaved perfectly, learns the tier is broken, and stops running it; anyone running <code>make eval-tools</code> spends the card's own estimate of $30-50 per invocation to discover a ceiling that only ever reports 0-or-fail.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CONFIRMED</b>. No fix is prescribed here — the measurement is the contribution.</em>
