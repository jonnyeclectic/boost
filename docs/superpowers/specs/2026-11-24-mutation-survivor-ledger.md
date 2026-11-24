# Mutation survivor ledger: stop re-proving known survivors on full runs

Status: proposed 2026-11-24. Design only; nothing here is implemented yet.
It reverses three recorded constraints, for **survived and timeout verdicts
only, never killed** (see "What this reverses"). The owner's approval of that
reversal is as recorded in the task that commissioned this design
(2026-11-24). For everything this doc does not change, the spec of record is
still `docs/superpowers/specs/2026-10-31-ci-speed-design.md`.

## Why

A full mutation run re-proves verdicts it already has, every time. Here is
what all 26 shard artifacts of push run 45290191649 contain (research of
2026-11-23):

| verdict | mutants | mutant-seconds | share of seconds |
|---|---|---|---|
| survived | 6,494 | 200,319 | 58.4% |
| killed | 47,808 | 131,616 | 38.3% |
| timeout | 61 | 11,327 | 3.3% |
| no tests | 54 | about 0 | 0% |

Score 87.85%, headroom 4,274 kills above 80%. A survivor runs its whole
covering test set to completion, while a kill exits at the first failing test.
That is why 12% of the mutants cost 58% of the time.

Re-running a survivor of a function whose source did not change almost always
says "survived" again. When it does not, because a new test now kills it, the
true score is higher than the recorded one, never lower. That asymmetry is the
whole design.

The runs that would use it are full runs that are not the nightly:

- PR runs that plan full while the diff gate is still in shadow (plan Tasks 7
  and 8);
- pushes to `main` that are not proven.

Each costs 1,597.8-1,600.9 shard runner-min and 149.4-157.8 min of wall clock
(runs 45263898738 attempt 1 and 45290191649).

## What this reverses

The owner's approval of these three reversals is as recorded in the
commissioning task, 2026-11-24.

| where | says today | becomes |
|---|---|---|
| spec 2026-10-31, lines 196-200 | the whole-codebase run is "the only trusted writer of a mutation baseline (... `actions/cache/save` ... never restored by a release workflow)" | A green, unledgered `schedule` or `workflow_dispatch` run on `main` writes the ledger, as an artifact, not a cache. PR runs and push runs read it, including the push run whose success `publish.yml` releases from. `publish.yml` itself stays cache-free and reads nothing new. |
| plan 2026-10-31, line 26 | "No PR run ever writes a mutation baseline or cache. This plan writes none at all" | The first sentence still holds, and no push writes one either. The second is superseded by this design. |
| `scripts/mutation_diff.py:20` | the diff shards name every mutant "so no cached verdict is ever trusted" | Still true of the diff set, which this design does not touch. The full set may carry recorded survived verdicts. |

Still binding and unchanged:

- **Anti-goals** (spec 2026-10-31, "Goals, non-goals, anti-goals"): no green built on stale "killed" verdicts (the
  ledger never holds one), no baseline written from a PR run, and no required
  check skipped into green.
- **Non-goal** (same section): the whole-codebase incremental driver. This
  design never reuses a kill, so it needs none of the test-change tracking that
  driver would.

## Soundness: a ledger can only make the gate stricter

The gate scores killed / (total - skipped) (`scripts/mutation_gate.py:47-49`)
over `mutmut export-cicd-stats` of the merged `.meta` files. Let K be every
mutant mutmut generates at the commit, C ⊆ K the carried set, and p(k) the
code a plain run gives mutant k.

- Every k not in C runs exactly as in a plain run: same commit, same stats,
  same tests.
- Every k in C gets the constant exit code 0, which mutmut's own table calls
  `survived` (`mutmut/stats.py`, `status_by_exit_code`). It adds 0 to killed
  and 1 to the denominator.
- In a plain run, the same k adds:
  - (1, 1) if killed;
  - (0, 1) for any other non-skipped verdict;
  - (0, 0) if skipped.

The two counts therefore relate like this:

- killed, ledgered = killed, plain - |C ∩ killed, plain|
- denominator, ledgered = denominator, plain + |C ∩ skipped, plain|

The ledgered score is therefore never above the plain one, and a ledgered PASS
implies a plain PASS. **This holds for every C**: whatever the ledger
contains, however old it is, whoever wrote it. No exit code is ever read from
the ledger. The ledger decides only which mutants are carried, and so only how
fresh the score is and how much time is saved. A wrong or hostile ledger can
turn the check red, for example by carrying every mutant. It can never turn it
green.

Nondeterministic kills hit plain runs equally, and the ledger neither causes
nor hides them. The one DISAGREE on record is
`store.x__install_project_skill__mutmut_223`, artifact 13610263304.

The implementation must keep each of these invariants, and a test pins each
one (see Test plan):

- **I1. The injected code is a constant.** `CARRIED_EXIT = 0` is never a value
  read from a file. A mutmut-backed test pins
  `status_of(CARRIED_EXIT) == "survived"`.
- **I2. Injection touches only unrun, generated keys.** It writes a key only
  when the shards' `.meta` files list it (mutmut generated it at this commit)
  and every shard has it as `None`. It never adds, removes or overwrites a key.
- **I3. Every key that is not carried is run.** The merge's existing
  fail-closed `None` check (`scripts/mutation_shards.py:1173-1178`) still
  applies after injection. If a shard also ran a carried key, the merge
  refuses it rather than reconciling: the plan and the shards then disagree
  about what ran.
- **I4. The gate checks the injection.** It scores the merged `.meta` exactly
  as today, re-reads every carried key, and exits 2 unless each one is 0.
- **I5. The nightly never reads a ledger.** It is the only writer, and it must
  stay a plain measurement.
- **I6. No weights from a ledgered run.** A ledgered run never uploads
  `mutation-weights`.

Freshness is the cost. A test that newly kills a carried survivor gets no
credit until the next ledger is written. That cost is bounded: killed, plain
≤ killed, ledgered + |C|. So the gate can print the range a plain score must
lie in (see Gate).

## Data model

The ledger is one JSON file, `mutation-ledger.json`, in an artifact named
`mutation-ledger`:

```json
{
  "kind": "mutation-survivor-ledger",
  "schema": 1,
  "source": {"run_id": 0, "run_attempt": 1, "event": "schedule",
             "branch": "main", "head_sha": "<commit>", "tree": "<tree>",
             "created_at": "<ISO 8601>"},
  "key": {"mutmut": "3.8.1", "libcst": "1.9.0", "python": "3.14",
          "config": "<sha256 of mutmut's settings>"},
  "machinery": "<sha256 of the mutation machinery>",
  "score": {"killed": 47808, "denominator": 54417},
  "functions": {
    "boost_cli.core.store.x_install": {
      "hash": "<12 hex, from .meta hash_by_function_name>",
      "mutants": 412,
      "ms_rerun": 123456,
      "ms_carried": 987654,
      "survived": [3, 17],
      "timeout": [42]
    }
  }
}
```

- `functions` lists every function the writer's merged `.meta` names, not only
  the ones with survivors, because `mutants` and `ms_rerun` are what a ledgered
  run packs on (see Planner).
- A carried mutant is stored by its `__mutmut_<n>` number, so its full name is
  `<qualified>__mutmut_<n>`. *Estimate:* about 2,035 functions and 6,555
  numbers, well under 1 MB.
- `ms_rerun` sums `durations_by_key` over the function's mutants that are not
  carried, and `ms_carried` sums it over those that are. The merge already
  carries `durations_by_key` into the merged `.meta`
  (`mutation_shards.py:1158-1162`).
- `score` is provenance only.

### The key identifies a mutant, never the tests

A carried number means "this same mutant survived last time". It is the same
mutant when the same generator ran over the same function:

| part | read from | why it is in the key |
|---|---|---|
| `mutmut`, `libcst` | installed versions (`importlib.metadata`) | the generator, and the parser it walks |
| `python` | major.minor of the running interpreter | the function hash is `sha256(ast.dump(node))[:12]` (`mutmut/mutation/file_mutation.py:43-60`), and `ast.dump` is version-specific |
| `config` | sha256 of mutmut's settings, read with the parsers `full_run_reasons` already uses for setup.cfg `[mutmut]` and pyproject `[tool.mutmut]` (`mutation_diff.py:139-187`) | settings such as `source_paths` and `do_not_mutate` change what is generated |
| per-function `hash` | the merged `.meta`'s `hash_by_function_name`, which the merge already keeps (`mutation_shards.py:1182-1183`) | an edited function regenerates all its mutants, exactly as mutmut resets them itself (`mutmut/__main__.py:200-215`, 3.8.1) |
| per-function `mutants` | the function's key count | a `# pragma: no mutate` edit leaves the AST hash alone (comments are not in the AST) but renumbers mutants, and a count mismatch catches most of those |

A mismatch in a global part means nothing is carried. A mismatch in a
per-function part means that function is not carried.

**Nothing about the tests is in the key, on purpose.**

- Keying on `tests/` is why #801's cache was restored 0 times in 263 saves. It
  was removed in ce3c7088, and `tests/unit/test_mutation_plan.py:1032` forbids
  an `actions/cache` step in the shards.
- Tests decide a verdict, not which mutant it is. Stale tests can only leave a
  carried survivor under-credited.
- pytest's version stays out for the same reason.

Some gaps remain, and each one costs freshness, never soundness:

- a pragma moved within a function without changing its mutant count;
- a libcst release that renumbers mutants without changing anything the key
  reads.

### The machinery digest: no ledgered verdict from untested machinery

`machinery` is a sha256 over:

- the bytes of every `scripts/mutation_*.py`;
- `requirements/mutation-tools.txt`;
- the canonical JSON of ci.yml's `jobs.mutation*`, read with `_mutation_jobs`
  (`mutation_diff.py:189-200`).

A run may use a ledger only when its own digest equals the ledger's. So every
ledgered verdict comes from the same planner, merge, gate and pins that a
plain, green nightly has already run on `main`, self-check included (see
Writer). After a merge that changes any of them, every run plans plain until
the next nightly writes a ledger under the new machinery.

This is the push half of risk 3. Its cost, measured on `main`'s first-parent
history: 14 of the 25 merges from 11-01 to 11-23 touched one of those files,
on 7 distinct days. That is an upper bound. It counts ci.yml edits outside
`jobs.mutation*`, which the digest ignores, and it covers the month the
CI-speed work itself was landing.

## Writer

The `mutation` job of a `ci` run writes a ledger only when all of these hold:

1. **Event and ref.** The event is `schedule` or `workflow_dispatch` on
   `refs/heads/main`. These are `WHOLE_CODEBASE_EVENTS`
   (`ci_proven_tree.py:258`), the one definition of a whole-codebase run that
   fact 3, the idle walk and `nightly-watch.yml` already share.
2. **A plain full plan.** The gate set is `full` and the plan carried
   nothing, so every verdict in it was measured on this commit.
3. **A green gate.** The merge and `mutation_gate.py` both passed.

Three steps follow the weights steps:

1. **Write.** `mutation_ledger.py write --meta mutants --plan PLAN --out
   mutation-ledger.json` builds the ledger from the merged `.meta`.
   - It carries only codes whose status is `survived` or `timeout`
     (`mutation_diff.status_of`, `mutation_diff.py:482-494`). Killed, no
     tests, skipped, suspicious, segfault and type-check codes are never
     carried.
   - It refuses a plan with a `carried` list, an event or branch outside
     condition 1, and any `None` in the merged `.meta`.
2. **Self-check.** `mutation_ledger.py selfcheck --meta mutants --ledger
   mutation-ledger.json` round-trips the ledger through the merge's own
   injection function.
   - It copies the merged codes, sets every ledger key to `None`, and
     re-injects them with the same function `merge` calls.
   - It then asserts that killed and the denominator are unchanged and that no
     `None` is left. The carried keys are exactly this run's survivors and
     timeouts, both non-killed, so any difference is an injection bug.
   - This is the only place the injection path runs before a PR or a push
     relies on it, which is why the machinery digest exists.
3. **Upload.** Only when step 2 succeeded, upload `mutation-ledger` with
   `retention-days: 30` and `overwrite: true`, so a re-run attempt that also
   passes replaces the ledger rather than leaving two.

Steps 1 and 2 are `continue-on-error: true`, like `refresh balance hints`
(ci.yml:2445-2455). **A ledger failure never changes a run's conclusion.** A
red `mutation` on a nightly would switch off the proven-tree skip (fact 3) and
open the failure tracker, over something that says nothing about the score. A
failed write leaves no ledger on the newest real run, so the reader plans plain
and says why (next section). Step 2 also emits `::warning::` and a summary line,
so a missing ledger is visible.

**Why push runs do not write.** *My call.* A full push run is also a fresh
measurement of `main`, but:

- it may itself be ledgered;
- push is not one of `WHOLE_CODEBASE_EVENTS`;
- the refresh it would add is available on demand: a dispatch on `main` is
  always a plain full run (ci.yml:1533), and writes a ledger when green.

**Retention, and what it has to outlive.** Retention is 30 days, longer than
the reader's 14-day age bound, so a ledger always stops being used at the
bound (with a reason in the log), never at an expiry.

The last outage is the case to check. No nightly mutated anything from 11-12
to 11-23: 11-12 ran no shards, and 11-13 to 11-23 all failed at `collect
mutmut stats once` on the clock-dependent test (for example job 138049346459).
Every one of those nightlies had a red `mutation`, so the reader would have
planned plain throughout: slower, never wrong.

## Reader: the `mutation-ledger` job

The reader is a new job that runs before `mutation-plan`. It has to be a
separate job: the planner must keep `permissions: {contents: read}`
(`tests/unit/test_ci_base_mutation.py:101`), and fetching another run's
artifact needs `actions: read`.

```yaml
mutation-ledger:
  if: github.event_name == 'pull_request' || github.event_name == 'push'
  continue-on-error: true
  runs-on: ubuntu-latest
  timeout-minutes: 5
  permissions:
    contents: read        # the checkout that carries the script
    actions: read         # ci's whole-codebase runs, their jobs and artifacts
    pull-requests: read   # the PR's labels, read live
  outputs:
    run_id: ${{ steps.find.outputs.run_id }}
    reason: ${{ steps.find.outputs.reason }}
```

Its steps:

1. **Setup.** harden-runner (audit) and a checkout, as in `idle-nightly`.
2. **Find.** `python3 scripts/mutation_ledger.py find`: stdlib only, no
   setup-python, and it exits 0 whatever it finds.
3. **Download.** When `find` named a run, `actions/download-artifact` at the
   pinned v8.0.2 fetches it with `name: mutation-ledger`, `run-id` and
   `github-token: ${{ github.token }}`. The pinned `action.yml` declares
   `github-token`, `repository` and `run-id`, and leaves `digest-mismatch` at
   its default, `error`.
4. **Re-publish.** `actions/upload-artifact` uploads the file again as this
   run's `mutation-ledger-in` with `retention-days: 1`, so the planner reads it
   with no token at all.

`find` reads, in order:

1. **The off switches.**
   - The repository variable `MUTATION_LEDGER`, read through `vars` in the
     step's `env`. `off` means no ledger.
   - On a `pull_request`, the label `mutation-no-ledger`. It is read with `GET
     pulls/{number}` when the job runs, not from the event payload, because a
     re-run replays the payload as it was.
2. **The newest real whole-codebase run.** It walks completed `schedule` and
   `workflow_dispatch` runs of ci.yml on `main` created in the last
   `MAX_LEDGER_AGE = 14` days, newest first. Each run must name the event and
   branch it was listed under, as `_whole_window` checks
   (`ci_proven_tree.py:907-933`). For each run:
   - **Its `mutation` job (latest attempt) is not `success`:** no ledger,
     *"whole-codebase run R is red (mutation: failure)"*. This is risk 2's red
     rule: no ledger is used past a red whole-codebase verdict.
   - **It carries exactly one `inherited-tree-` marker:** step over it. That
     is an idle night, which mutated nothing and inherits an older real run.
   - **Otherwise it is a real run.** It must hold exactly one unexpired
     artifact named `mutation-ledger` that belongs to that run, and that
     artifact is the ledger. Zero, two or expired means no ledger: *"the newest
     real whole-codebase run R wrote no ledger"*. The walk never reaches past a
     real run to an older ledger, because a real run whose write failed has
     measured things its predecessor's ledger does not know.
   - **No run in the window qualifies:** no ledger, *"no green real
     whole-codebase run on main in the last 14 days"*.

**Why 14 days.** *My call.*

- An idle nightly inherits a real run up to 7 days old (`MAX_INHERIT_AGE`,
  `ci_proven_tree.py:315`), so a quiet week must not switch the ledger off.
- 14 is that week plus one week of missing nightlies.
- `nightly-watch.yml` alarms after 36 h, so by day 14 a stopped nightly has
  been reported for twelve days.

**The script is self-contained.** It has its own small stdlib HTTP client and
does not import `ci_proven_tree.py`.

- Its name puts it under `scripts/mutation_*.py`, so editing it is a full-run
  trigger (`mutation_diff.py:249-254`) and changes the machinery digest.
  Importing `ci_proven_tree.py`'s helpers would put code that decides ledger
  use outside both.
- Any exception, unexpected shape, rate limit or timeout means "no ledger",
  with the reason, as `ci_idle_nightly.py` does.
- The reader is off the soundness path, since soundness holds for any carried
  set. It decides only freshness and whether the ledger is used at all.

## Planner (`scripts/mutation_plan.py`)

Changes to `mutation-plan`:

- `needs` gains `mutation-ledger`.
- A new step, `continue-on-error: true`, downloads `mutation-ledger-in` to
  `$RUNNER_TEMP/mutation-ledger/` when the reader named a run. It lands outside
  the workspace for the reason given at ci.yml:1941-1943.
- The plan step decides on **the file it validates**, never on
  `needs.mutation-ledger.result`. The comment above `mutation-advisory-shard`
  notes that this result is unconfirmed for a continue-on-error job.

Which plans get `--ledger`:

| event | plan today | with the ledger |
|---|---|---|
| `schedule`, `workflow_dispatch` | full; `nightly` (full plus an advisory diff); or none (idle) | **never** (I5). The nightly stays a plain full run at 26 on the committed weights, so its headroom test, `SHARDS` and the weights refresh keep describing one workload. |
| `pull_request` | `diff --shadow` | `diff --shadow --ledger L` |
| `push`, not proven | `full` | `full --ledger L`. No diff is computed; the machinery digest guards the machinery. |
| `merge_group` | `diff --shadow` | never. The queue is not enabled (spec 2026-10-31, "Constraints"), so the path is not added. |
| any event, `GITHUB_RUN_ATTEMPT` not 1 | as above | **never**. See below. |

**Why a re-run never uses a ledger.** On "re-run failed jobs" GitHub keeps the
outputs of jobs that succeeded, which is why the scope step already guards
idle-nightly's answer on the attempt number (ci.yml:1300-1302). "Re-run all
jobs" is also the escape from a ledgered red (see Escapes).

A ledgered push plans with `.venv/bin/python`, because `--ledger` needs mutmut's
generator; the venv exists whenever a push is mutation-relevant. Anything that
goes wrong inside ledgered planning gives the plain plan plus a reason that
starts `ledger not used:`. That mirrors how `nightly_plan` falls back to
`full_plan` (`mutation_plan.py:366-367, 383-384`). Ledger trouble never fails
the planner.

### Which functions are carried

`diff_plan` returns the plain full plan from four places, and only the first
one is a machinery trigger. So the decision travels as data, never read back
out of reason strings: `full_plan(root, shards, reasons, ledger=None,
keep=frozenset())`.

| call site | what triggered it | ledger |
|---|---|---|
| `mutation_plan.py:247` | `full_run_reasons` fired | **none.** Risk 3: a PR that edits the mutation machinery or the test support never uses the ledger. The plan records `"ledger": {"used": false, "why": "full-run trigger"}`. |
| `:284` | a changed function with no mutants | may be used, nothing kept back |
| `:302` | the scope is too big to pack | may be used, nothing kept back |
| `:319` | the scope is empty under shadow | may be used, nothing kept back |
| `:335` | the shadow plan | may be used, with `keep` = the diff scope (changed functions plus their direct callers) |

At 284, 302 and 319 there is no diff set to compare, and soundness does not
depend on the scope. In the shadow plan, changed functions never match a hash
anyway. Their callers do match, but they run in full in the full set, so the
shadow's per-mutant comparison still compares two measurements.

A function is carried only when all of these hold:

1. **The file.** The ledger is well-formed and names this run in
   `source.run_id`.
2. **The global key.** Every part equals this run's: the installed mutmut and
   libcst, the Python minor version, and the config digest.
3. **The machinery.** The machinery digest equals this run's.
4. **The function.** Its hash and mutant count at this commit equal the
   ledger's. Both come from `mutate_file_contents` under
   `mutation_diff.mutmut_config` (`mutation_diff.py:345-389`).
5. **The scope.** The function is not in `keep`.

Its carried mutants are then the ledger's `survived` and `timeout` numbers. A
number with no mutant at this commit means the ledger is malformed, and the
plan is plain.

### What the shards run, and how they are packed

The carried mutants have to be left out by naming, not by state:

- mutmut 3.8.1 re-runs every mutant that its argv names or matches
  (`__main__.py:1028-1030`).
- A pre-seeded `.meta` works only for an unnamed run. `:200-215` keeps
  verdicts, and `:1028` skips them only when there is no filter, so an unnamed
  run would run every other shard's mutants too.

Each unit gets one kind of selector:

| unit | selector | splittable |
|---|---|---|
| a file with no carried function | `<module>.*`, as today | no; a file heavier than an even share splits into function units, as `units_for` does |
| a function with no carried mutant, in a file that has some | `<module>.<mangled>__mutmut_*` (a method spells `xǁClassǁm`) | no |
| a function with carried mutants | the exact names of its mutants that are **not** carried | yes, at name granularity |

**A ledgered plan is packed on killed-only time.** *My call.* Keeping the
committed pack instead would leave shards uneven: on today's pack the
killed-only phase per shard ranges from 10.5 to 36.9 min (verifier), and the
run waits for the slowest. How the repack works:

- **Unit weights.**
  - An unchanged function weighs the ledger's `ms_rerun`.
  - A changed or un-carried function weighs `ms_rerun + ms_carried`.
  - A new function weighs the mean time per mutant times its count.
- **Packing.** Longest first into at most 26 bins, ties broken by name. It is
  deterministic, like `pack` (`mutation_shards.py:844-879`).
- **No function-pattern-only bins.** Every bin gets at least one exact name or
  file pattern. A bin of function patterns alone selects no clean-run tests,
  so it pays the whole-suite clean run: the 11.30-min preamble measured for
  function-only shards (`mutation_shards.py:239-247`).
- **Headroom.** The pack must pass `headroom_report` at the mutate step's
  190-min cap. It should, because every ledgered unit is at most its plain
  counterpart.

**The name cap stays at `MAX_NAMES = 1500`** (`mutation_diff.py:318-325`). It
is a measured bound: about 110 KB of argv against ARG_MAX, and 12.3 s for
mutmut's fnmatch filter.

- **Expected load.** The verifier counted 35,344 names when only the
  non-carried mutants of functions with survivors are named. That is a mean of
  1,359 per shard against a capacity of 26 × 1,500 = 39,000, about 9% slack.
  The per-shard counts on the real tree are **not measured**.
- **Over the cap, the plan degrades and never falls back to plain:**
  1. Named functions split across bins to fill the free name room.
  2. If the total still exceeds 39,000, functions are **un-carried**, cheapest
     `ms_carried` first. Each becomes a function pattern that runs every
     mutant, survivors included: always sound, only slower. This repeats until
     the total fits.

  The plan says how many functions it un-carried.
- **Why not raise the cap.** That would trade a measured bound for an
  extrapolated one: about 16 s and 134 KB at 1,841 names, by the verifier's
  arithmetic. Revisit with the first run's real counts.

**Partition check, before the plan is written.** Every generated name must be
covered exactly once, either by the shards' selectors or by the carried list.
The selectors are read structurally (file, function or exact name), not by
fnmatching 51k names against 2k patterns. Any gap or overlap is a bug, and the
plan falls back to plain.

### Plan fields

On a ledgered plan, `sets.full` gains these fields:

```json
"carried": ["boost_cli.core.store.x_install__mutmut_3", "..."],
"ledger": {"used": true, "run_id": 0, "created_at": "<ISO 8601>",
           "head_sha": "<commit>", "age_hours": 18.4, "carried": 6412,
           "carried_timeouts": 59, "carried_ms": 205000000,
           "functions_carried": 1020, "uncarried": 0},
"mutants": 54417
```

- `mutants` is the planner's own count of generated names. A plain full plan
  keeps `null`.
- The planner job gains a new output, `ledgered` (`true` or `false`).
- The plan's reason line names the ledger's run, its age and the carried
  count.
- `matrix` and `patterns` do not change (`mutation_plan.py:414-438, 559-586`).
  The shards already take any mix of patterns and exact names, NUL-separated,
  after `--`.

## Shards

`mutation-shard` does not change. A ledgered shard is shorter and runs a mix
of selectors. The 190-min step cap, the 200-min job cap and the headroom test
on the committed pack all keep describing the nightly, the heaviest workload.

## Merge (`mutation_shards.py merge`)

Today the merge rebuilds ownership from `pack(root, args.shards)`
(`mutation_shards.py:1112-1119`), and ci.yml:2441 passes it no plan. A
ledgered repack moves units between shards, so that ownership would read moved
mutants as unrun. That is red rather than unsound, but it would make every
ledgered run red.

**Ownership comes from the plan.**

- `merge` takes `--plan PLAN --set full`.
- ci.yml's `download the plan` step (2271-2272) runs whenever `gate_set ==
  'full'`, not only under shadow.
- Each shard's selectors map to files: `<module>.*`,
  `<module>.<mangled>__mutmut_*`, `<module>.xǁ*` and exact names each resolve
  to one file (`split_qualified`, `mutation_diff.py:330-342`).
- On a plan that carries nothing, the plan-derived ownership must equal
  `pack()`'s, or the merge refuses. That keeps today's guarantee that the
  planner and the merge agree.

**Injection** happens after the per-file union (1145-1162) and before the
unrun check (1173). For each carried name of the file:

- If the name is not a key that the shards' `.meta` lists, the merge refuses:
  *"carried mutant X is not generated at this commit"*.
- If any shard has a code other than `None` for it, the merge refuses:
  *"carried mutant X was also run by shard i"*.
- Otherwise the code is set to `CARRIED_EXIT`.

After injection, the existing check fails closed on any `None` that is left
(I2, I3). A carried name in a file that no shard owns is also refused. The
summary line reads *"merged N files, M mutants (C carried from ledger run R),
from S shards"*.

The merge runs on the runner's `python3`, which has no mutmut, so
`CARRIED_EXIT` is a module constant there. The gate and a mutmut-backed test
pin what it means.

## Gate (`mutation_gate.py`)

The gate takes an optional `--plan PLAN`. On a ledgered plan it:

1. **Checks the injection.** It reads every carried key back from the merged
   `.meta` and exits 2 unless each one is exactly 0 and the installed mutmut
   reads `status_of(0)` as `survived` (I1, I4).
2. **Scores** exactly as today.
3. **Prints provenance** before the score, for example: *"ledgered: 6,412 of
   54,417 mutants carried as survived (6,353 survived and 59 timeout on
   record) from whole-codebase run R (schedule, 2026-11-25T09:31Z, 18 h old,
   commit abc1234); not re-run on this commit"*.
4. **On a FAIL, prints the range** a plain run must fall in: from
   killed / denominator to (killed + carried) / denominator.
   - If the top of that range is below the floor, the red is **conclusive**: no
     fresh run could pass.
   - Otherwise it is **inconclusive**, and the gate prints the escapes below.

Exit codes do not change. The same lines go to `$GITHUB_STEP_SUMMARY`.

## Escapes from a ledgered red

This is risk 2.

**What still causes a red.** A ledger is used only while the newest
whole-codebase verdict is green (see Reader). So a red `main` switches the
ledger off for everyone, and a fix PR is scored plain. That leaves one case: a
PR or push whose ledgered score misses 80% while a fresh one would pass. Only
kills of *carried* survivors can do that, because every regression is measured
fresh: a weakened test, a caller that stopped calling, new survivors in a
changed function.

There are two deterministic routes to a plain run, and neither bypasses
anything:

- **Re-run all jobs.** Attempt 2 never uses a ledger, on a PR or a push.
  - "Re-run failed jobs" is not enough, because it reuses the ledgered plan.
  - On a PR this route costs the proven-tree skip later. Fact 2 accepts only a
    first-attempt PR run (`ci_proven_tree.py:17-18`), so the merge's push runs
    in full.
- **Add the label `mutation-no-ledger` and push a commit** (PR only). Attempt 1
  of the new head is plain, and a green one still proves the merge's push.

The owner also has a global switch: the repository variable
`MUTATION_LEDGER=off`. Each of these routes runs the plain full gate exactly
as it was before this design.

## Diff-shadow compare

Carried rows never enter a comparison:

- A shadow plan never carries a diff-scope function (`keep`).
- `compare` reads the full shards only over the diff scope's functions
  (`mutation_diff.py:1032-1033`).

If `sets.full.carried` does name a mutant of a diff-scope function, `compare`
refuses with INCOMPLETE, rather than reading the shards' `None` as a missing
result. The nightly's advisory shadow is unaffected, because the nightly
carries nothing.

## Weights

`refresh balance hints` and `upload balance hints` (ci.yml:2445-2462) gain the
condition `needs.mutation-plan.outputs.ledgered != 'true'` (I6). A ledgered
run's merged `.meta` has no durations for carried keys, so `weights` would
record killed-only time as the whole.

`mutation-weights-refresh.yml` already treats a run with no `mutation-weights`
artifact as ordinary: its `download the measured hints` step is
`continue-on-error` (`mutation-weights-refresh.yml:169-177`).

## ci.yml, job by job

| job | change | permissions |
|---|---|---|
| `mutation-ledger` (new) | The reader, on PR and push runs only. Job-level `continue-on-error`; a stdlib script, then the download and re-upload. | `contents: read`, `actions: read`, `pull-requests: read` |
| `mutation-plan` | `needs` gains `mutation-ledger`. Downloads `mutation-ledger-in` (continue-on-error). The plan step passes `--ledger` as the table above says, never on an attempt after the first. New output `ledgered`. | unchanged: `contents: read` |
| `mutation-shard`, `mutation-advisory-shard` | none | unchanged |
| `mutation` | See the list below. | unchanged: `contents: read` |

The `mutation` job changes in six places:

- The conclusive step refuses `ledgered == true` on a `schedule` or
  `workflow_dispatch` run.
- The plan is downloaded whenever `gate_set == 'full'`.
- `merge` runs with `--plan`.
- `mutation_gate.py` runs with `--plan`.
- The weights steps skip ledgered runs.
- New writer steps (continue-on-error) upload `mutation-ledger`, on green,
  unledgered `schedule` and `workflow_dispatch` runs on `main` only.

What does not change:

- **Required checks.** `mutation-ledger` is advisory, and
  `.github/required-checks.txt` stays as it is.
- **Caches.** No `actions/cache` anywhere.
- **zizmor.** `.github/zizmor.yml` anchors no ignore in ci.yml today, but check
  the anchors again after the edit (`tests/unit/test_zizmor_ignores_still_anchor.py`).
- **Billing.** It stays on GitHub Free for a public repository: standard
  runners, width 26, artifacts only.

The reader adds one short job ahead of the planner on every PR and push run.
On a busy account it queues the way `proven` does. That is the price of keeping
the planner's token at `contents: read`.

## The six risks

| # | risk (from the verifier) | handled by |
|---|---|---|
| 1 | the only writer was down for 12 days | The reader decides on the newest real run within 14 days, and a red one, or one with no ledger, means plain. 11-13 to 11-23 would have been plain throughout. Retention is 30 days, longer than the 14-day bound. |
| 2 | red-gate deadlock | No ledger is used past a red whole-codebase run. The gate says whether a FAIL is conclusive or not. Escapes: re-run all jobs, the label, the repository variable. |
| 3 | a PR judging its own machinery | `full_run_reasons` gives `ledger=None`, as data rather than read from reason strings. The machinery digest keeps PRs and pushes off a ledger until a nightly under the same machinery has passed the self-check. The reader is itself a `scripts/mutation_*.py` file. |
| 4 | documented constraints | "What this reverses", plus dated pointers in the 2026-10-31 spec (196-200) and plan (26) |
| 5 | exact names are required | Only the non-carried mutants of functions with carried ones are named, with patterns everywhere else. The cap stays at 1,500, degrading first by splitting, then by un-carrying. |
| 6 | merge ownership, injection, weights, compare, permissions, key | `merge --plan` and its injection rules; invariants I1-I6; the weights guard; compare's `keep` and its refusal; a reader job with `actions: read`; a key that identifies the mutant and never the tests |

## Expected effect

*Model, not measured.* These figures are the verifier's corrected arithmetic
on runs 45290191649 and 45263898738.

- **Runner-min per ledgered full set:** from 1,598-1,601 to about 760-845, a
  saving of 757-845 (47-53%). That already allows for re-running the survivors
  of changed functions, at the spec's re-run fractions: 8.1% median, 13.4% p75
  (spec:44, borrowed).
- **Wall clock per ledgered full run:** the simulated shard phase is about
  60-72 min on 18-20 free slots, against 138-144 today. The whole run is about
  72-86 min, against 149.4 and 157.8 measured: 65-85 min saved on the blocking
  path.
- **Which runs benefit:**
  - *While the diff gate is still in shadow* (Task 8 is blocked on the
    DISAGREE above): PR full runs that are not infra-triggered, which were 11
    shadow, 9 empty-scope and 4 other runs in 11-01 to 11-23, plus the 7 pushes
    that were not proven. Fewer of those runs completed, and the machinery
    digest switches some off.
  - *After Task 8:* about 1 PR set and 7 pushes per 23 days, roughly
    6,000-7,000 runner-min, again minus what the digest switches off. Pushes
    that merge machinery changes are among those 7, and the digest makes them
    plain.
- **What that adds up to.** After Task 8 the durable saving is a few runs a
  month. Most of the value is the blocking-path wall clock on each of those
  runs, plus the PR runs until Task 8 lands.
- **The nightly does not change:** about 1,600 runner-min. It is the
  refresher.

## Test plan

Prove every test red first, by reverse-applying its change, never with
`git stash`. Tests that need mutmut run in `mutation-plan`'s
`BOOST_REQUIRE_MUTMUT` step (ci.yml:1422-1426). The rest run in every `tests`
cell.

**Soundness property** (`tests/unit/test_mutation_ledger.py`). Use seeded
random code assignments over mutmut's whole exit-code table, with random
carried subsets. The test asserts:

- ledgered killed ≤ plain killed;
- ledgered denominator ≥ plain denominator;
- ledgered score ≤ plain score.

**Injection** (`test_mutation_shards.py`).

- It writes exactly 0, and only into keys that are `None` everywhere.
- It refuses:
  - a carried key that some shard ran;
  - a carried key that was not generated;
  - a carried name in a file no shard owns.
- It still fails closed on an uncarried `None`.
- With no carried list, plan-derived ownership equals `pack()`'s.
- The verifier's bug: a ledgered repack merges with `--plan` and is refused
  without it.

**`CARRIED_EXIT`** (needs mutmut): `status_of(CARRIED_EXIT) == "survived"`.

**Writer.**

- It carries only survived and timeout.
- It refuses:
  - a ledgered plan;
  - a source run that is not on `main` or not whole-codebase;
  - a `None` in its input.
- `selfcheck` fails when the injection function is patched to return 1, which
  proves the check bites, and passes on a correct ledger.

**Reader** (a fake API, as `test_ci_proven_tree.py` uses).

- It plans plain on each of these:
  - a red newest run;
  - a real run with no ledger, or with two;
  - an expired ledger;
  - a run older than 14 days;
  - an API error, or a response of the wrong shape;
  - a run on another branch or event;
  - the label;
  - the repository variable.
- It steps over an idle night to a green real run's ledger.

**Planner.**

- Key and digest:
  - any global key part that mismatches → plain;
  - a per-function hash or count that mismatches → that function is not
    carried;
  - a digest mismatch → plain.
- Scope and call sites:
  - diff-scope callers are never carried;
  - the four `full_plan` call sites set `ledger` as specified.
- Packing:
  - the partition check refuses an overlap and a gap;
  - every bin is within `MAX_NAMES`, and going over the cap un-carries rather
    than falling back to plain;
  - every bin holds a name or a file pattern.
- Any exception → plain, with a `ledger not used:` reason.

**Gate.**

- It exits 2 on a carried key that is not 0.
- It prints the range line.
- It prints the conclusive and inconclusive messages.

**Compare.** It reports INCOMPLETE when a carried name sits in the diff scope.

**Workflow** (`test_mutation_plan.py`, `test_ci_base_mutation.py`).

- **The reader job.** Its `if`, permissions, `continue-on-error` and download
  inputs.
- **The planner.**
  - Its permissions are still exactly `{contents: read}`.
  - `schedule` and `workflow_dispatch` never pass `--ledger`.
  - The attempt check sits in the plan step.
- **The `mutation` job.**
  - `merge --plan` and `gate --plan`.
  - The weights steps are guarded on `ledgered`.
  - The writer steps are guarded and continue-on-error, and their upload
    depends on the self-check.
  - The conclusive step refuses a ledgered plan on a whole-codebase run.
- **Caches.** No `actions/cache` in any `mutation*` job. This widens the
  existing shard-only test at `test_mutation_plan.py:1032`.

**Housekeeping.**

- `make lint`.
- The SPDX header on `scripts/mutation_ledger.py`.
- A pointer in the `mutation_diff.py:20` docstring.

## The first real observation

Nothing changes until a green nightly writes a ledger under the merged
machinery:

1. **The implementation PR** edits `scripts/mutation_*.py` and
   `jobs.mutation*`, so it plans plain (a full-run trigger). **Its merge push**
   finds no ledger (*"the newest real whole-codebase run R wrote no ledger"*)
   and also plans plain.
2. **The next nightly** (09:30 UTC) runs plain at 26 shards, about 1,600
   runner-min as today. On a green gate it writes, self-checks and uploads
   `mutation-ledger`.
   - If the survivor count is still near 45290191649's 6,494 plus 61 timeouts,
     expect about 6,500 carried numbers across about 1,026 functions.
   - If its `mutation` is red, nothing is written, and the next day decides.
3. **The next PR or push that is neither machinery nor proven** shows three
   things:
   - in `mutation-ledger`: *"ledger: run R (schedule, created T)"*;
   - in the plan reason: the carried count, the functions carried and
     un-carried, and the age;
   - in the gate: the provenance line, then the score.

   Expect up to 26 shards with a mutation phase of about 20-30 min each, and a
   whole run near 72-86 min. Every number here is a model until this run.
4. **One A/B comparison on the same SHA.**
   - Open a throwaway draft PR with a test-only change, which is no trigger.
   - After its ledgered attempt 1, choose "Re-run all jobs". Attempt 2 is plain
     on the same merge commit.
   - Compare the two attempts' per-mutant codes:
     - non-carried keys should agree, apart from known nondeterministic kills,
       which are listed;
     - for carried keys, the number plain killed measures how stale the ledger
       was;
     - ledgered killed must not exceed plain killed, nor the ledgered score
       the plain one. Either would be an injection bug: stop, and switch the
       ledger off with the repository variable.
   - Exact-name and pattern runs have already disagreed once on one SHA
     (artifact 13610263304), so expect few non-carried disagreements, not
     zero.
   - The cost is one more plain full set, in free minutes on a public
     repository.

## What could not be verified locally

- **A ledgered shard end to end.** That mutmut takes a mixed argv of file
  patterns, function patterns and up to 1,500 names, and what its clean run
  costs with mixed selectors.
- **The real per-shard name counts.** 1,359 is the verifier's mean.
- **The cross-run download.** `action.yml` was read at the pinned SHA, but the
  download was not run.
- **Re-run behaviour.** Three things are unconfirmed:
  - what `GITHUB_RUN_ATTEMPT` is on "Re-run all jobs";
  - whether a re-run's success fires `publish.yml`'s `workflow_run`;
  - whether `vars` is read again on a re-run.
- **Free artifact storage.** That artifact storage stays free on a public
  repository. It is consistent with the 90-day shadow reports already kept.
- **The time saving.** It is a model that its own author calibrated as about 7%
  optimistic.
- **The mutmut version.** The mutmut 3.8.1 source was read from an extracted
  wheel. The shared local venv holds 3.8.0, and nothing was installed into it.

## Left to the builder

- The exact names of subcommands, flags and plan fields. Three names are fixed:
  - `mutation-ledger` (it must match `jobs.mutation*`);
  - `scripts/mutation_ledger.py` (it must match `scripts/mutation_*.py`);
  - `CARRIED_EXIT = 0`.
- How heavy files with nothing carried are split.
- How the ledger is compressed.
- How the summary is formatted.
- Creating the `mutation-no-ledger` label.

## Sources

- **Research and its adversarial verification**, with run, job and artifact
  ids: `mut-research.txt` in the session scratchpad (P1, and its verdict).
- **mutmut 3.8.1:**
  - `__main__.py:198-215, 730-751, 805-817, 1028-1030, 1089-1098`;
  - `stats.py`;
  - `mutation/file_mutation.py:43-118`.
- **This tree:** the files and lines cited inline.
