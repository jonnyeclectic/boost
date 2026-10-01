---
id: mutation-shard-balance-hints-are-a-release-behind
board: code
section: trust
status: shipped
category: CI · Mutation gate
complexity: S
impact: Med
wow: 2
note: the stale pack cost 1.311x the measured best; a workflow now re-measures it
order: 358
owner: loop/mutation-weights-refresh
pr: 1012
title: "The mutation shard planner is packing for a mutant set that is 14% smaller than the real one"
---
<code>scripts/mutation_weights.json</code> is the measured input the shard planner bin-packs on, and
it was last refreshed on 2026-09-08 by #834, from a CI-measured run. It records <b>23,251 mutants
over 63 files</b>, of which only 59 carry a measured duration. A full local run of the gate on 2026-09-29 counted <b>27,060</b> &mdash; the
planner is balancing six shards against a picture of the work that is 14% light. (23,251 against
27,060 is 14.1% smaller; the other way round, the real set is 16.4% <em>larger</em> &mdash; an earlier
draft of this card quoted the second number as if it were the first.)

<b>The drift is uneven, which is the part that costs balance rather than merely being out of date.</b>
Per file: <code>store.py</code> 2,916 &rarr; 3,962 (+36%), <code>paths.py</code> 110 &rarr; 187
(+70%), <code>dense.py</code> 1,845 &rarr; 1,999 (+8%), <code>gitutil.py</code> 622 &rarr; 710
(+14%), while <code>policy.py</code> went 286 &rarr; 278 (&minus;3%). <code>store.py</code> is the
one file the planner splits per top-level function, so its share is what most decides the pack, and
it is the file that grew most.

<b>What made this visible.</b> On 2026-09-29 <code>mutation-shard (0)</code> on PR #1000 ran 75.6
minutes against the job's <code>timeout-minutes: 75</code>, was killed, and failed the required
<code>mutation</code> check. That one was <em>not</em> a packing defect: the shard plan is
byte-identical on <code>main</code>, #1000 and #1001 (verified by generating all six patterns on
each tree and diffing), and the same shard ran 34 minutes on both of the others, so the immediate
cause was the runner variance the job's own comment already documents &mdash; 2.6x on identical
work. Stale weights are what leaves no headroom to absorb it. The ceiling is ~3.1x the planned
24.1-minute per-shard time, and a pack built from a 14%-light picture spends part of that margin
before a slow runner arrives.

<b>Two smaller corrections fall out of the same reading.</b> The comment above
<code>timeout-minutes: 75</code> in <code>ci.yml</code> dated the weights file to 2026-07-30 where git
says 2026-09-08 &mdash; <em>corrected by #1002 itself</em> (<code>24d66559</code>), so a reader
checking it today finds neither the stale date nor the sentence; this change then deletes those
lines outright. And <code>mutation_shards.py weights</code> rewrites
<code>scripts/mutation_weights.json</code> <em>in place</em> and prints only a summary to stdout, so
the natural-looking <code>weights --source mutants &gt; new.json</code> silently overwrites the
committed file and puts the summary line in <code>new.json</code>.

The fix is the remedy <code>ci.yml</code> already names for this situation: re-measure from a CI
run and re-pack. It must be a CI run, not a laptop one &mdash; that is the convention #834 set,
and it is load-bearing, because the tier-1 weights are milliseconds and a developer machine's
durations are not the runner's. (A local run also cannot be trusted to be complete: a resumed run
leaves whole files with no recorded duration, which the planner then imputes at the mean rate.)

<b>Shipped, and the harm was larger than counts showed.</b> Counts were the
wrong unit: the planner bin-packs on <code>millis_by_file</code>, and against
the times recorded by the 2026-09-30 run on <code>main</code> the committed
file understated the total by 40.5% (393 minutes against 660) over 59 timed
files against 63. Scoring the two packs against those same measurements —
which is what <code>mutation_shards.py drift</code> now does — the plan built
from the committed hints puts <b>150 minutes on its slowest shard and 75 on
its fastest</b>, while the plan built from the measurements is flat at 115.
The committed plan costs <b>1.311x</b> the best those numbers admit.

<b>That model was checked against the wall clock rather than trusted.</b> The
six shards of that run took 46.5 / 40.1 / 37.5 / 37.0 / 25.8 / 22.9 minutes —
a 2.03x spread against the 2.00x predicted, <em>in the same order</em>, with
the predicted/observed ratio between 3.06 and 3.49 across all six (the job's
test parallelism). So the slowest shard's 1.61x headroom under
<code>timeout-minutes: 75</code> becomes about 2.14x once the pack is current,
which is the margin #1000 did not have when a shard ran 75.6 minutes and was
killed.

<b>Three files had never been measured at all</b> — <code>compact.py</code>,
<code>prereq.py</code> and <code>report.py</code> — so the planner was sizing
them by line count. A fourth, <code>chat.py</code>, carried a mutant count but no
duration, so it was imputed at the mean rate instead.

<b>What stops it recurring.</b> <code>mutation-weights-refresh.yml</code>
follows <code>ci</code> on <code>main</code>, takes the
<code>mutation-weights</code> artifact that run already uploads, and opens one
reusable bot PR when the committed plan costs 5% or more than the measured
best. It is a <code>workflow_run</code> and not a cron for a reason the twin
refresh jobs do not have: the artifact's retention is seven days, so a monthly
job would wake up and find nothing.

<b>Eight findings fell out of building it.</b> The first draft floored the
<em>absolute</em> makespan, which declares a refresh worth it on weights that
have not drifted at all — a unit heavier than an even share is a floor no
packer can get under, and the shipped fixture reads 1.200 with the two
files identical. The verdict is a ratio between the two plans instead. And
<code>runs_unattended</code> in
<code>tests/unit/test_failure_alerting_covers_unattended.py</code> only looked
for a cron or a push, so the three <code>workflow_run</code> workflows that
run on main were invisible to the guard whose stated rule covers them —
including <code>release</code>, which is what uploads to PyPI on every merge.
All three are now watched.

The next four came out of reviewing two successive drafts, and two of them turned the refresh into
the thing it was meant to prevent. <b><code>drift</code> failed open.</b> A candidate that was not a usable
measurement &mdash; a truncated download, <code>{}</code>, a counts-only file &mdash; scored the committed
plan 1.438x behind (1.588x for the counts-only one) and reported <code>moved=true</code>, so the
workflow would have committed an empty file over the real measurements. And <b>the refusal then failed
the job</b>: <code>cmd_drift</code> returned 0 without writing <code>--summary-md</code>, while the
workflow step's last command was an unguarded <code>cat</code> of that file, whose exit status is the
step's. "Keeping the committed hints" &mdash; a designed outcome &mdash; would have reddened
<code>main</code> and, through the watch list this very change added, filed an issue against a workflow
whose header says a failure here blocks nothing. The coverage guard had a matching one-way door: it
compared file counts without asking which files still exist, so deleting a module from
<code>boost_cli/core</code> would have refused every candidate afterwards, with the blocked refresh as
the only thing that could clear it.

<b>The fourth of those was a fork guard.</b> The new workflow holds <code>contents: write</code> and
<code>pull-requests: write</code>, and <code>branches: [main]</code> filters the <em>triggering</em>
run's head_branch rather than the event or the repository &mdash; <code>ci.yml</code> runs on
<code>pull_request</code>, so a fork PR raised from a branch called <code>main</code> reaches it. It now
carries the two conditions <code>publish.yml</code> and <code>sbom.yml</code> document at length, and a
test asserts the repository half for every <code>workflow_run</code> workflow granting
<code>contents: write</code>.

<b>The last two arrived from CI itself, and the first of them hid the second.</b> All three <code>tests (windows-latest, 3.1x)</code> jobs failed on
the first push: the report is written <code>encoding="utf-8"</code> and contains an em dash, and the test
read it back with a bare <code>read_text()</code>, which is cp1252 on a Windows runner. Every text read
and write in the planner and its tests now names its encoding; the repo-wide sweep of the other 73
sites is <code>text-io-leaves-its-encoding-to-the-locale</code> (73 and not the 116 first reported:
the walker was counting <code>tarfile.open</code>, <code>os.open</code> and binary
<code>Path.open("rb")</code>, and 16 of the 17 it attributed to <code>boost_cli</code> were not text
IO at all). The next Windows run failed
again, on the half naming the encoding does not cover: text mode translates <code>\n</code> to the
platform separator on <em>write</em>, so the file held CRLF where <code>sys.stdout.write</code>
emitted LF, and the same comparison failed for an entirely different reason. The step summary and
the log beside it are one report written twice and have to agree byte for byte, and
<code>$GITHUB_OUTPUT</code> is parsed a line at a time, so every writer in the script now pins
<code>newline="\n"</code> &mdash; gated by a second AST walk, over writers only, since universal
newlines already fold CRLF on the way in.

<b>A note on the method, because two anomalies here had two different causes.</b> Each behaviour
above was reverted in place and the matching test confirmed to fail. One revert produced the
stranger result &mdash; a test failing against source that was demonstrably correct &mdash; and that
was stale <code>__pycache__</code>: restoring a file from a backup of the same byte length within
the same second (<code>candidate</code> and <code>committed</code> are both nine) leaves the
<code>.pyc</code> header's <code>(mtime, size)</code> pair valid, so Python keeps running the
pre-revert bytecode. Every run is now under <code>PYTHONDONTWRITEBYTECODE=1</code>. The other
anomaly survived clearing the cache and was a real gap: the latch test asserted the refusal's
absence from the <code>--github-output</code> file, where it never appears, rather than from
stdout, so the filter it was written to protect had no test at all. A falsification that cannot
fail is worth less than no falsification, because it is recorded as evidence.

A second pass — twenty agents re-deriving every number and trying to refute every guard,
independently of the author — returned seven more defects, and the lesson above arrived a second
time with it. One was another test that could not fail, in the fix for the first: the
rename-tolerance test asserted <code>rc == 0</code> and <code>"moved=" in out</code>, and
<code>moved=false</code> is written on <em>every</em> refusal path, so it held whether the
candidate was compared or rejected &mdash; and its fixture renamed nothing. Three were blind spots
in the new guards themselves: the workflow sweep globbed <code>*.yml</code> only, so the
<code>.yaml</code> half of the directory was silently out of scope; its <code>on:</code> scanner
read a block mapping and nothing else; and the encoding walker read <code>p.open(mode)</code> as
having no mode and accepted every <code>.open</code> attribute call, which is where 43 of a
claimed 116 unencoded sites came from. The last three were prose that did not survive
re-measurement: the sweep count (116 &rarr; 73), <code>PLW1514</code> (a preview rule, reporting 1
site on main rather than 0), and a stale <code>ci.yml</code> date that #1002 had itself already
corrected. Each of the four code fixes is now pinned by a revert that fails.
