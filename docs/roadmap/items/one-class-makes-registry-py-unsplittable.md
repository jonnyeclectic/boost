---
id: one-class-makes-registry-py-unsplittable
board: code
section: pipeline
status: inflight
category: CI · Bug
complexity: M
impact: High
wow: 5
note: a 30-line class with zero recorded mutants makes the other 7.3M weight-ms of registry.py one indivisible unit, flooring the mutation gate at 95% of its timeout at every shard count
order: 366
owner: loop/registry-unsplittable-floor
pr: 1027
title: One 30-line class makes <code>registry.py</code> unsplittable, and floors the mutation gate at 95% of its timeout no matter how many shards you add
---
<b>Found by measuring the first eight-shard run on main against its own prediction.</b>
The planner said 28.4 min a shard; run 36959485751 measured 31.2, 39.6, 41.0, 41.0, 42.3,
43.1, 47.5 and 51.5 &mdash; a median of 41.0, which is <b>1.44x the prediction</b>. Job
overhead is not the gap: the <code>mutate shard</code> step alone was 30.6&ndash;42.5 min.
The committed weights simply understate the work, and #1022 is the bot's re-fit that says
so (57,680,336 ms against 42,506,911, a ratio of 1.36).

<b>The part that is a bug, not a drift.</b> #1022 cannot merge: at eight shards its pack
scores a 73.5-minute tail against a 75-minute cap, which <code>plan --timeout-minutes</code>
correctly calls TOO TIGHT. The documented remedy is to re-pack &mdash; and re-packing does
nothing. At 10, 12 and 14 shards the planner returns the <em>identical</em> verdict, because
<code>largest unit: 7309374</code> is <code>registry.py</code> whole, and one indivisible
unit is a floor on the slowest shard that no shard count divides. The only lever the repo
documents is connected to nothing.

<b>Why it is indivisible.</b> <code>top_level_symbols</code> returns <code>[]</code> for any
module holding a class with methods, because mutmut mangles a method's name differently and
a wrong guess leaves mutants unrun. <code>registry.py</code> holds exactly one such class:
<code>Tap</code>, <b>30 lines of 783</b>, which carries <b>no recorded mutants at all</b> &mdash;
its 24 measured symbols sum to 7,309,375 against a file total of 7,309,374. So a class that
contributes nothing to the cost blocks the split of everything that does. Eleven files in
<code>boost_cli/core</code> are in the same position, 18.6% of all mutation work.

<b>The fix is proof, not a guess.</b> <code>cmd_weights</code> writes
<code>millis_by_symbol[file]</code> only when <em>every</em> mutant of the file was timed, and
it derives each key by the exact inverse of the mangling <code>pattern_for</code> applies. So
a complete record both covers every mutant and addresses it. <code>measured_partition</code>
lifts the AST refusal for a module a real run has cleared, under one guard: every recorded
name must be a top-level <code>def</code>, since a name from inside a class would round-trip
to a pattern matching nothing. Over both committed weight generations and all eleven
class-bearing files, <b>no recorded name has ever come from inside a class</b>. The split
still runs over the AST rather than the record, so a function added since the measurement
keeps its unit; and <code>cmd_merge</code> fails closed on any unrun mutant, so the worst
case is a loud red build rather than a score computed over a short set.

<b>Measured result.</b> On #1022's weights the pack goes from TOO TIGHT at every shard count
to <code>split files : registry.py, store.py</code> and a <b>58.8-minute tail at ten shards</b>,
with <code>catalog.py</code> (5,914,538 ms) as the new floor. On the weights committed today
nothing changes at all &mdash; <code>registry.py</code> is under the even share, so it is not
split and the plan is byte-identical.
