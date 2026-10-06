---
id: the-shard-model-has-no-per-job-fixed-cost
board: code
section: trust
status: planned
category: CI · Model
complexity: M
impact: Med
wow: 3
note: the plan divides by every shard added, so it flatters every width above the one it was fitted at
order: 367
owner:
pr:
title: "The shard model runs through the origin, so <code>plan</code> gets more optimistic with every shard added"
---
<b>The cleanest statement of it needs no weights at all.</b> Going from eight shards to twelve,
a model that divides work by the shard count predicts the median job falls to <b>0.667</b> of
itself. It fell to <b>0.83</b> &mdash; 41.8 min over the 24 jobs of the three eight-shard runs to
34.6 over the 24 jobs of the two twelve-shard runs. Correcting for the one thing the weights
do say &mdash; #1032 re-timed the same mutants 0.884&times; cheaper &mdash; moves the prediction
to <b>0.589</b> and widens the gap, so the uncorrected figure is the conservative one. No value
of <code>RUNNER_EFFICIENCY</code> produces either, because the error is in the shape and not in the
constant: <code>runner_minutes</code> is <code>weight / (RUNNER_WORKERS &times;
RUNNER_EFFICIENCY)</code>, linear through the origin, and what is missing is a per-job
<em>fixed</em> cost.

<b>Graded like for like, the two widths disagree by 40%.</b> Each width has to be scored against
weights measured at that width: #1029's 66,708,651 ms total was measured on an eight-shard run,
and #1032's 58,969,820 was re-timed from CI run 37200431822 &mdash; which is
<code>58ace415</code>, one of the two twelve-shard runs being graded. On that footing eight
implies an efficiency of <b>0.832</b> and twelve implies <b>0.593</b>. Reading both against one
frozen total hides this, and understates the gap as 24%.

<b>C is large and five routes do not agree on how large.</b> They differ in whether they use
medians or machine-minute sums, and in whether #1032's 0.884x re-timing is read as the work
really getting cheaper between the two widths: <b>20.2</b> and <b>24.2</b> min a job from the two
p50s, <b>14.4</b> and <b>19.8</b> from the matrix totals (347.6 machine-minutes at eight over
four runs, 404.9 at twelve over two), and <b>26.9</b> from the six-to-eight step of 2026-10-02
&mdash; 287.2 &rarr; 341.0 machine-minutes two hours apart with the width the only change. So
<b>C is 14 to 27 min a job</b>. A two-point solve is exactly determined and therefore not
falsifiable; fitting C needs a third width, not more runs at twelve.

<b>And C cannot be bolted on beside the efficiency, which is the part that makes this a card
rather than a one-line patch.</b> Subtract any C in that range from the matrix total and the
parallel work left over implies a speedup above four on a four-vCPU runner: C = 14.4 leaves 232.4
min against 1,111.8 weight-minutes, which is <b>4.78</b> effective workers, and C = 24.2 leaves
154.0, which is <b>7.22</b>. An efficiency over 1.0 is a contradiction, not a tight fit, so the
weights overstate real serial work by roughly the same factor and
<code>PLANNED_TOTAL_MS</code> cannot serve as the fixed reference a re-fit is measured against.
A hypothesis, named as one because it has not been measured: mutmut times each mutant while four
of them run at once, so a per-mutant duration may already carry the contention
<code>RUNNER_EFFICIENCY</code> exists to apply.

<b>The naive remedy is worse than the status quo, so it is worth writing down as refuted.</b>
Adding C to the existing conversion with the committed efficiency &mdash; <code>C +
runner_minutes(w)</code> at C = 20, each width on its own weights as this card requires &mdash;
predicts <b>62.7 min at eight</b> against an observed 41.8 and <b>45.2 at twelve</b> against an
observed 34.6: over-predicting by <b>50%</b> and <b>31%</b>. The bias is not even, which is the
point &mdash; a fixed term added to an unchanged efficiency does not just shift the answer, it
gets the width dependence wrong in the other direction. The tail it produces at twelve is
<b>86.2 min, 115% of the cap</b>: the planner would refuse the width CI
runs green today. C and <code>RUNNER_EFFICIENCY</code> have to move together, and whatever they
do to the predicted median then has to be reconciled with
<code>TAIL_MULTIPLIER</code>, whose over-estimate is currently covering for the median being low.

<b>It is not CI setup, and that is the cheap half to check.</b> Stepping all 24 twelve-shard jobs
through the Actions job API, everything that is not the <code>mutate shard</code> step is a
median <b>0.5 min</b> &mdash; the 1.7% the constant's docstring already measured at six, still
true. So the fixed cost is inside mutmut: a baseline test run (the <code>tests</code> job on
those two runs took 7.8 and 8.6 min) and per-job mutant collection are the candidates, and
neither has been measured. Measuring them would turn the 14-27 range into a mechanism.

<b>Why it matters even though nothing is red.</b> Twelve sits at 74% of the cap empirically and
the gate passes. But <code>plan</code> reported 64% on #1032's pack against that same
measured 74%, and goes on reporting 48% at sixteen, where the real floor is <code>C &times;
TAIL_MULTIPLIER</code> however many shards are added. So the one question the planner exists to
answer &mdash; "is this width safe?" &mdash; is answered optimistically for every width above the
fitted one, and the answer gets more optimistic the further you go. Until C is fitted,
<code>test_the_committed_width_has_actually_run</code> refuses a <code>SHARDS</code> nothing has
been observed at, and <code>test_todays_pack_under_predicts_the_worst_twelve_shard_job</code>
pins the 7.8-minute shortfall so it cannot drift unnoticed.
