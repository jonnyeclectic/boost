# CI speed: getting a PR from green to released in under an hour

Status: approved 2026-10-31 (options: B with red-nightly fallback; old survivors count).

## Why

A PR takes most of a working day to merge, and most of that is CI wall
clock. Measured on the last 30 merges to `main` (all figures below are from
the research run of 2026-10-31 unless marked *estimate*):

- **Mutation dominates.** The 24 mutation shards are 78-88% of job-minutes and
  each runs 103-160 min. Every one of the 24 "runner lost communication"
  failures in 55 sampled runs was a mutation shard past 103 min, and each costs
  a rerun.
- **Main re-proves what the PR already proved.** In 17 of 17 merges the merge
  commit's tree was byte-identical to a PR head with a green run (`behind_by`
  0). Main still re-runs everything, so `publish.yml` (which waits for a green
  push run) fires 191-454 min after merge.
- **The next bottleneck is the Windows test cells.** A PR run with zero
  mutation shards (run 41164311690) took 63 min, ending on
  `tests (windows-latest, 3.12)` at 62 min. The Windows pytest step went from
  ~31 to ~60 min between 10-18 and 10-31. Every cell runs pytest serially with
  `--cov`.
- **The 20-job cap.** One PR's non-mutation jobs already use 20 slots. While
  mutation or the `shards` workflow runs, other jobs waited a median 31 min
  (max 196); when neither runs, the median wait is 0.1 min.

Success: a typical PR's `ci` run finishes in about 30 min and its release
publishes within minutes of the merge, without letting untested code through.

## What the research ruled out

**Switching to Stryker.** It has no Python support.

**Turning on mutmut's built-in incremental reuse for the whole codebase.**
mutmut 3.8 already reuses results per function hash, and CI defeats it by
naming mutants (`mutmut run $PATTERNS` forces re-runs, `__main__.py:1028-1030`)
and by a cache key that never matches (263 caches, 2.1 GB, 0 restores). Fixing
that properly is possible, but the cost is not in the source changes: it is in
the test changes.

| Re-run fraction per gated run (median / p75) | release train | single branch |
|---|---|---|
| Source delta only (functions whose hash changed) | 8.1% / 13.4% | 0.8% / 1.7% |
| Whole-codebase incremental, conftest change = full run | 61.5% / 100% | 25% / 44% *estimate* |
| Whole-codebase incremental, conftest not a trigger | 55.3% / 69.7% | 23% / 41% *estimate* |

24 of 30 trains touch tests; `tests/conftest.py` changed in 10 of 30. A sound
whole-codebase reuse needs a driver that clears results for changed tests,
callers, module-level edits and fixture changes. Toy experiments showed mutmut
leaving stale "killed" verdicts in two of those cases (a caller that stopped
calling, and a weakened test). So the whole-codebase incremental design costs
about 2x speed-up for the highest complexity and a false-pass risk. Not
recommended as the PR gate.

Two corrections to what was said earlier in the conversation:

- "Touch every source after restoring the cache" is unnecessary.
  `also_copy = boost_cli/` in `setup.cfg` already forces mutmut to regenerate
  every file, and restoring only `.meta` files (not mutant sources) avoids the
  mtime trap anyway.
- "conftest change forces a full run" would have fired on a third of trains.
  It only matters where results are reused; the recommended PR gate below runs
  everything in scope fresh, so it does not need it.

## Recommendation

### Part 1: policy-neutral speed-ups (no change to any guarantee)

Each can land on its own, in this order.

1. **Collect mutmut stats once.** Each shard spends 5.5-8.8 min re-collecting
   the same test-to-function stats before its first mutant. A planner job
   collects `mutants/mutmut-stats.json` once and shards restore it (mutmut
   re-collects only for test IDs missing from `duration_by_test`,
   `mutmut/runners/harness.py:64-88`). Stats must come from the same commit
   and config, or mutmut's config invalidation (`__main__.py:624-643`) forces a
   full re-collection. Saves ~9 min wall clock per shard and ~3.5 h of
   job-minutes per run *estimate*.
2. **Windows cells: pytest-xdist, coverage in one place.** Add `pytest-xdist` to
   the hash-pinned `requirements/test-tools.txt`. Run with `-n auto` in every
   cell. Enforce `--cov`/`fail_under` in ubuntu-3.12 only and run plain pytest
   in the others. `patch-coverage` (a ~20 min second full suite run) keeps its
   job name, because the ruleset requires it, but downloads ubuntu-3.12's
   `coverage.xml` as an artifact instead of re-running the suite. *My call.* Expected Windows cell: 60 → 20-25 min
   *estimate*. Windows runners have 4 vCPU, so expect less than the 3.26x
   measured elsewhere.
3. **Fix or quarantine the Windows flake**
   `test_state_file_locking.py::TestRaces::test_project_lock_removals_and_writes_interleave`.
   It failed in runs 39615438937, 40143859588 and 40143864868 on the critical
   path cell, each costing a 60 min rerun.
4. **Delete the dead per-shard `actions/cache` step** (2.1 GB, never restored).
5. **Fix `mutation_shards.py merge` dropping `hash_by_function_name`**
   (`scripts/mutation_shards.py:1115-1121`) and add a round-trip test. Today a
   baseline built from merged output treats every function as changed (720 of
   720 reset in the scratch test). Needed before any result reuse.
6. **Refresh `scripts/mutation_weights.json`.** It says 46,088 mutants; main has
   49,905-50,371, so shard packing is about 9% off.
7. **Cheaper test fixture (measure first).** About 1,282 unit tests clone and
   install the fixture tap in setup (11 git subprocesses, 0.197 s). Survivors
   are 12.5% of mutants but 57% of mutant time, because each one re-runs every
   covering test with that setup. A session-scoped template copied per test
   (0.04 s, measured) is estimated at 20-30% off mutation time. Start with the
   clone-only variant (keep `store.install` per test) and compare the mutation
   score against main before adopting, because mutmut credits session fixture
   code to the first test only and the score can drop.

### Part 2: the PR mutation gate becomes diff-scoped

The surveyed practice (Google, Arcmutate/pitest, cargo-mutants, Infection,
gooze, irradiate) is to mutation-test the change on the PR and the whole
codebase elsewhere. That fits boost, because today's whole-codebase gate barely
binds a PR: main scores 87.8% (43,792 of 49,905), so one PR could add about
4,800 entirely unkilled mutants and still pass 80%.

**Scope.** Mutants of every function in `boost_cli/core` whose mutmut hash
changed against the merge base, plus their direct callers from the stats'
`function_dependencies` (+1.4% median on trains). Module-level edits produce
no mutants of their own and do not widen scope. *My call.*

**Run fresh.** Mutants in scope are run by explicit name, so mutmut re-runs
them with no cached verdict trusted. This is the mechanism CI uses today
(`mutation_shards.py plan` already turns paths into patterns). No baseline cache
is needed for the PR gate.

**Gate.** At least 80% of in-scope mutants killed, counted exactly as
`mutation_gate.py` counts today (no-tests counts against the score). With fewer
than 10 mutants in scope, the gate fails on any survivor instead of a
percentage (one equivalent mutant out of 3 would read as 66.7%). Survivors go
to the job summary and as annotations on the changed lines, capped at one per
line. *My call on 10 and on keeping today's counting rule.*

**Old survivors count (approved 2026-10-31).** Every mutant of a
changed function counts, including survivors that predate the PR. This is
mutmut's own granularity: a changed hash regenerates all of a function's
mutants, so "only the new ones" would need extra code that maps each mutant to
diff lines. Measured on main's full run at b5d9c4ec (21 of 24 shards, 44,506
mutants; 291 of 1,717 functions sit below 80%), replaying the changed-function
sets of past merges: **0 of 21 release trains** would fail (lowest 83.2%,
median 87.8%), and 7 of 160 single branches would (median 88.6%). The trains are
what get gated, so the rule costs nothing there. Approximation: the scores are
today's verdicts for those functions, not the verdicts at each merge.

**Full-run triggers.** Anything `mutation_shards.py scope` already treats as
relevant that is not a `core` source file — `setup.cfg [mutmut]`,
`requirements/mutation-tools.txt`, `scripts/mutation_*.py`, the mutation jobs in
`ci.yml` — forces the full 24-shard run on the PR, so a mutmut bump or a planner
edit is never gated on zero mutants. Test-only changes no longer run the gate
(see the accepted gap). *My call.*

**Shard count follows the work.** A planner job lists in-scope mutants, packs
them by measured duration into `ceil(N / ~1500)` shards, capped at 16, and
emits indexes only (`fromJSON`). The plan itself travels as an artifact.
Empty scope means zero shards. The zero-shard path and the aggregator's
"skipped counts as a pass only when scope says irrelevant" rule already exist
(`ci.yml:530-571`, `950-985`); the change is that the planner, not the path
filter, now decides the count. Of the mutation jobs, only `mutation` is a
required check (ruleset and classic protection, read 2026-10-31); no shard
name is, so a variable matrix cannot break branch protection.

Expected cost *estimate*: a median train is ~4,000 mutants at ~7.5 s, about
3 shards of ~30 min; a single branch is ~140 mutants, one short shard. Shards
then never approach the 103 min runner-loss line.

**Accepted gap.** A test-only change that weakens a test covering unchanged
code passes the PR gate. The whole-codebase run below catches it.

### Part 3: where the whole-codebase 80% lives

Both options keep Parts 1 and 2 as written.

| | A: full run on every merge | B: proven-tree skip + nightly |
|---|---|---|
| Main push run | Full 24-shard whole-codebase gate, as today (faster with Part 1) | If the merge tree equals a green PR head's tree and `behind_by` is 0, skip tests and mutation; still run lint, zizmor and pip-audit, and report success. Otherwise full run. The coverage badge (inside the ubuntu-3.12 cell, `ci.yml:494-502`) then updates from the proven PR run's `coverage.json` artifact |
| Whole-codebase 80% | Checked before every release | Checked nightly (off-hours, scheduled workflow), auto-issue on failure |
| Release delay after merge | ~2-2.5 h *estimate* | Minutes |
| Worst case | Slow releases | A release can ship below 80% whole-codebase for up to 24 h; the gap is code that passed its own diff gate |

The CLAUDE.md rule is "every merge to main cuts a PyPI release". Under A that
rule also means "every release passed the whole-codebase gate". Under B it
means "every release passed the diff gate, and the whole codebase was checked
within a day". The ~4,800-mutant slack means the whole-codebase number moves
slowly, so B's risk is a drift that the nightly flags, not a sudden drop.

**Recommendation: B, with a red-nightly fallback (approved 2026-10-31).** If the
most recent nightly whole-codebase run is red, the proven-tree skip turns off and
main runs the full gate (option A) until a green run clears it. That restores
"never merge onto a red release" without a human watching the issue. Why B: 17
of the last 17 merges had a tree identical to a green PR head, so A re-proves
what the PR already proved, at 2-2.5 h per release. Under the diff gate the
whole-codebase score can only fall through unchanged code: a weakened test, or a
caller more than one hop from a change. Falling from 87.8% to 80% takes about
3,900 kills turning into survivors in one day, which no past train has come
close to.

In either option, the run that checks the whole codebase is the only trusted
writer of a mutation baseline (`.meta` files plus `mutmut-stats.json`, saved
with `actions/cache/save` under `push`/`schedule` on `main` only, never
restored by a release workflow), so a later whole-codebase incremental mode
remains possible without cache poisoning.

## Goals, non-goals, anti-goals

- Goals: typical PR `ci` ≤ ~30 min; publish soon after merge; no lost runners;
  the per-PR mutation gate still binds the PR's own code at 80%.
- Non-goals: replacing mutmut; redesigning release trains (a 30-min PR run
  removes most of their reason, but that is a separate decision); the
  whole-codebase incremental driver (deferred, see above).
- Anti-goals: a green gate built on stale "killed" verdicts; a baseline ever
  written from a PR run; a required check that can be skipped into green; a
  change that quietly drops the whole-codebase 80% check entirely.

## Constraints

- GitHub Free, user-owned repo: 20 concurrent jobs, no merge queue, no larger
  runners, 10 GB cache (2.78 GB used, 2.1 GB of it the dead shard cache).
- `strict` up-to-date checks with no bypass (ruleset 19130332).
- `publish.yml` releases only after a successful `ci` push run on `main`, and
  must stay cache-free (zizmor `cache-poisoning`).
- Editing workflows shifts the `file:LINE` anchors in `.github/zizmor.yml`
  (`tests/unit/test_zizmor_ignores_still_anchor.py`).
- `mutation-weights-refresh.yml` consumes weights from every green `ci` push.
  A diff-scoped run produces partial weights, so the upload must be gated on
  full runs or the refresh will repack on partial data. The refresh accepts
  only `event == 'push'` (`mutation-weights-refresh.yml:80-83`); under option B
  it must also accept the nightly workflow's `schedule` runs, or weights never
  refresh.
- New `.py` files need the SPDX header; new `core` logic needs tests that kill
  its mutants.

## Validation before switching the gate

1. Replay 5 recent trains in diff mode and confirm each one's in-scope verdicts
   match the same mutants' verdicts in that commit's full run.
2. Run one full whole-codebase run and one diff run on the same `main` SHA and
   compare per-mutant exit codes for the in-scope set.

   Bar for 1 and 2: zero killed/survived disagreements. Mutants that time out
   in either run are excluded and listed. For Part 1.7, the killed count may
   not drop at all against main on the same SHA (timeouts excluded). *My
   call.*
3. After Part 1.2, confirm the Windows cell time and that the coverage gate
   still reads 90% from the one enforcing cell.

## Left to the builder

- Exact planner and aggregator implementation (`mutation_shards.py plan-diff`
  or similar), shard size (start at ~1,500 mutants), and how callers are read
  from stats.
- Job and step names other than the required `mutation`.
- Annotation format for survivors.
- Nightly schedule time (off-hours, outside Dependabot and `shards` bursts).
- Fixing the drift between `.github/required-checks.txt`, classic protection
  and the ruleset is noted, not in scope.

## Sources

Research output (all six investigations, with commands and file:line
evidence): `tasks/wurkfn1mj.output` in the session scratch directory; delta
analysis scripts and `final.json` under `scratchpad/mutdelta/`.
