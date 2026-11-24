# Mutation survivor ledger: stop re-proving known survivors on full runs

Status: approved by the owner on 2026-11-23; implemented, and inert until
the owner sets the repository variable `MUTATION_LEDGER` (see "Rollout").

**The approval, verbatim.** On 2026-11-23 the owner, asked which builds to
make, selected the option labelled "Survivor ledger (#5)", whose text read
exactly:

> Days. The nightly records which mutants survived; PR and push runs skip unchanged ones. Saves 65–85 min per full run.
> Can only under-state the score, but reverses 'never trust a cached verdict'.

That is the whole record, as the task that commissioned this implementation
relayed it on 2026-11-24 (no copy in the owner's own hand was available to
check it against), and this doc claims no approval wider than it. It reverses
three recorded constraints (see "What this reverses"), never for a killed
verdict. Four things this design does are **not in those words**, and each
waits behind the `MUTATION_LEDGER` token named beside it, for the owner to
confirm by setting it:

- carrying **timeout** verdicts as well as survived ones (`write`);
- a `workflow_dispatch` run on `main` writing the ledger, where the text says
  "the nightly" (`write`);
- a **release** resting on a ledgered score: the push run whose success
  `publish.yml` releases from reads the ledger (`push`);
- a ledgered PR run proving its merge push (`ci_proven_tree.py`, fact 2),
  which then skips mutation and releases (`pull_request`).

The first two have no switch of their own: `write` also turns on the nightly
writer that the words do cover, so setting it confirms all three together.

And "Can only under-state the score" is more than this design proves.
"Soundness" retracts it to "carrying never adds a kill": the mutants a
ledgered run does re-run are measured under its own selectors, which can
differ from a plain run's.

For everything this doc does not change, the spec of record is still
`docs/superpowers/specs/2026-10-31-ci-speed-design.md`.

## Why

A full mutation run re-proves verdicts it already has, every time. Here is
what all 26 shard artifacts of push run 45290191649 contain, tallied from
their `.meta` exit codes and `durations_by_key` under mutmut 3.8.0's
`status_by_exit_code` (2026-11-24; no key was run by two shards):

| verdict | mutants | mutant-seconds | share of seconds |
|---|---|---|---|
| survived | 6,496 | 199,982 | 58.6% |
| killed | 47,797 | 131,211 | 38.5% |
| timeout | 70 | 9,988 | 2.9% |
| no tests | 54 | about 0 | 0% |

Score 87.83%, headroom 4,263 kills above 80%. (The research of 2026-11-23
read the same run as 6,494 / 47,808 / 61; the re-tally is what every
measured figure below uses, and its 6,496 + 70 is exactly the 6,566 the
planner carries, so no killed row is carried.) A survivor runs its whole
covering test set to completion, while a kill exits at the first failing test.
That is why 12% of the mutants cost 59% of the time.

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

The owner's selection of 2026-11-23 (see "Status") names the third of
these in its own words and describes the first two. The last column quotes
the words that cover each row, and says what they leave out. Each is still
switched on separately (see "Rollout"):

| where | says today | becomes | the selected option's words |
|---|---|---|---|
| spec 2026-10-31, lines 196-200 | the whole-codebase run is "the only trusted writer of a mutation baseline (... `actions/cache/save` ... never restored by a release workflow)" | A green, unledgered `schedule` or `workflow_dispatch` run on `main` writes the ledger, as an artifact, not a cache. PR runs and push runs read it, including the push run whose success `publish.yml` releases from. `publish.yml` itself stays cache-free and reads nothing new. | "The nightly records which mutants survived; PR and push runs skip unchanged ones." Not in them: `workflow_dispatch` as a writer, timeout verdicts, and that one of those push runs gates a release. |
| plan 2026-10-31, line 26 | "No PR run ever writes a mutation baseline or cache. This plan writes none at all" | The first sentence still holds, and no push writes one either. The second is superseded by this design. | "The nightly records which mutants survived." |
| `scripts/mutation_diff.py:20` | the diff shards name every mutant "so no cached verdict is ever trusted" | Still true of the diff set, which this design does not touch. The full set may carry recorded survived verdicts. | "reverses 'never trust a cached verdict'" |

Still binding and unchanged:

- **Anti-goals** (spec 2026-10-31, "Goals, non-goals, anti-goals"): no green built on stale "killed" verdicts (the
  ledger never holds one), no baseline written from a PR run, and no required
  check skipped into green.
- **Non-goal** (same section): the whole-codebase incremental driver. This
  design never reuses a kill, so it needs none of the test-change tracking that
  driver would.

## Rollout

The repository variable `MUTATION_LEDGER` is a comma-separated list of
tokens. Each token switches on one thing, and each is a separate owner
decision:

| token | switches on | reversal it needs |
|---|---|---|
| `write` | a green, plain `schedule` or `workflow_dispatch` run on `main` writes, self-checks and uploads `mutation-ledger` | spec 2026-10-31:196-200 (a baseline written outside the nightly's cache rules) |
| `pull_request` | attempt 1 of a PR run may carry survivors into its full set. **This alone can already put a ledgered verdict under a release:** a green first-attempt PR run proves its merge push (`ci_proven_tree.py`, fact 2), which then skips the mutation run and releases. Fact 3 still needs a green plain whole-codebase run within 48 h. | plan 2026-10-31:26, `mutation_diff.py:20`, and the release reversal below (spec 2026-10-31:196-200) through the proven push. Not built: `ci_proven_tree` refusing a ledgered PR run as proof, which would close this and cost every such merge a full run. |
| `push` | attempt 1 of an unproven push run to `main` may carry survivors. **That is the run whose success `publish.yml` releases from** (`publish.yml:70-72`), so a release would be gated directly on a score that re-ran no recorded survivor. | spec 2026-10-31:196-200 ("never restored by a release workflow") |

Unset, empty or anything else: the reader job is skipped by its `if`, the
planner stamps and applies nothing, and no run writes a ledger.
`scripts/mutation_ledger.py` re-checks the exact tokens itself; a workflow
`if` is only a shortcut. `tests/unit/test_ci_proven_tree.py` simulates the job
graph with the variable unset and set.

Unset is not byte-for-byte main (3e5fc88e). Every difference on that path:

- **Plans.** Every plan gains a top-level `ledger_eligible`, and a push's
  `mutation_plan.py full` call gains `--ledger-eligible` to set it. Only
  `mutation_ledger.py apply` reads the field; `matrix`, `patterns`, the merge,
  the gate and every `jq` in ci.yml give the same answer with it flipped or
  absent.
- **`mutation-plan`.** It `needs` the skipped `mutation-ledger`, which its
  `!cancelled()` already runs past. It has a new output, `ledgered`
  (`false`), with one more `jq`. Its `BOOST_REQUIRE_MUTMUT` step also runs
  `tests/unit/test_mutation_ledger.py`, about 2 s locally, and that is a new
  way for any relevant run's planner to go red.
- **`mutation`.**
  - The plan is downloaded on every full gate; main downloaded it for a
    shadow only.
  - The new `ledgered` step fails the job when the plan is unreadable, or
    when it holds a ledgered plan on a whole-codebase run.
  - The weights steps also need its `plain == 'true'`.
  - `timeout-minutes` is 34, not 20.
- **`merge --plan`.** It refuses a plan it cannot read, one whose full set
  is not 26 shards, a selector it cannot map to a file, and a plain set that
  is not the committed pack. It deletes a stale `mutation-carried.json`.
  Main never read the plan, so each of these is a new way to go red, and none
  can happen on a plan the planner wrote.
- **`gate --plan`.** It exits 2 on a plan it cannot read.

What does not differ, and how that is shown:

- **The plan files.** `mutation_plan.py full --shards 26` on this tree,
  plain and with `--ledger-eligible`, is main's output plus the field.
- **The merge.** Run 45290191649's real verdicts (76 files, 54,417 mutants)
  were laid out as 26 simulated shards of this tree's pack. Main's merge, this
  merge and this merge with `--plan` give the same exit code, the same stdout
  and byte-identical trees, and they still do when one shard is missing.
- **The planner step.** It was run under bash with the test suite's stubs:
  60 cases of event, relevance, proven and idle, main's ci.yml against this
  one. The call log and `$GITHUB_OUTPUT` are identical, apart from the push
  flag above and the new `ledgered=false`.

These three were one-off runs on 2026-11-24, not tests. The tests that pin
the same things are under "Test plan", "The unset path".

The intended order, each step the owner's:

1. `write` alone. Nightlies write and self-check ledgers; nothing reads them.
   A self-check failure is a `::warning::`, never a red run.
2. Add `pull_request`, and run the A/B (see "The first real observation")
   until its stop rule has had a chance to fire.
3. Add `push` only after the A/B passed **and** at least one green ledgered PR
   run exists under the current machinery digest. Nothing in code enforces the
   second half; see "Residuals".

## Soundness: carrying never adds a kill

*Amended 2026-11-24 after review (major 2). The first draft claimed more than
this, and it was false.*

The gate scores killed / (total - skipped) (`scripts/mutation_gate.py`) over
`mutmut export-cicd-stats` of the merged `.meta` files. Let K be every mutant
mutmut generates at the commit and C ⊆ K the carried set.

- Every k in C gets the constant exit code 0, which mutmut's own table calls
  `survived` (`mutmut/stats.py`, `status_by_exit_code`). It adds 0 to killed
  and 1 to the denominator. No exit code is ever read from the ledger.
- Every k not in C is **measured by this run, under this run's own
  selectors.** That is not "exactly as in a plain run". With mutmut's default
  `process_isolation = fork` (`configuration.py:166`, not overridden in
  setup.cfg), the shard's parent runs the clean tests in-process
  (`isolation.py:920-921`) and forks each mutant from that parent
  (`isolation.py:853`). Which clean tests run depends on the selectors
  (`tests_for_mutant_names`, `__main__.py:1089`): an exact name selects its
  function's tests, a file pattern the file's, a function pattern none (the
  whole suite). Core keeps module-level caches a child inherits
  (`catalog.py:868`, `rag.py:1360`, `rag.py:1611`, `serve.py:317`). A ledgered
  plan exact-names 35,338 of 54,417 mutants on run 45290191649's results,
  where a plain plan names none, so a non-carried verdict can differ from what
  a plain run of the same commit would give. The one DISAGREE on record
  (`store.x__install_project_skill__mutmut_223`, artifact 13610263304) is
  pattern=survived, exact=killed: the direction that would raise a ledgered
  score.

So the guarantee is this, and no more: **for the mutants this run measured,
the ledger adds nothing; for the ones it did not, it adds a survivor.** A
wrong or hostile ledger can make a run slower or redder, never add a kill. It
is **not** a proof that a ledgered PASS implies a plain PASS, and the gate no
longer prints a range a plain run "must lie in" or calls a red "conclusive".
Whether selector-dependent verdicts matter in practice is what the A/B
measures, per key and by direction (see "The first real observation").

Separately, and the owner's call: `process_isolation = forkserver` runs the
clean tests in a child (`isolation.py:814-818`), which would take the clean
run's side effects out of every mutant's verdict, ledgered or plain. Not part
of this design.

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
  as today, re-reads every carried key, and exits 2 unless each one is 0 and
  the installed mutmut reads 0 as `survived`.
- **I5. The nightly never reads a ledger.** It is the only writer, and it must
  stay a plain measurement.
- **I6. No weights from a ledgered run.** A ledgered run never uploads
  `mutation-weights`: the CI `if` decides on the plan file, and `weights`
  itself refuses a merge that wrote `mutation-carried.json`.

Freshness is the other cost. A test that newly kills a carried survivor gets
no credit until the next ledger is written.

## Data model

The ledger is one JSON file, `mutation-ledger.json`, in an artifact named
`mutation-ledger`:

```json
{
  "kind": "mutation-survivor-ledger",
  "schema": 1,
  "source": {"run_id": 0, "run_attempt": 1, "event": "schedule",
             "branch": "main", "head_sha": "<commit>",
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
  `<qualified>__mutmut_<n>`. Measured on 45290191649: 6,566 numbers across
  the 1,027 functions that have any, well under 1 MB.
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
| `mutmut`, `libcst` | installed versions (`importlib.metadata`), read by the planner under `.venv` and stamped into the plan (`mutation_ledger.py stamp`); the writer copies them from the plan, so it never reads its own job's interpreter (review minor) | the generator, and the parser it walks |
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
plain, green nightly has already run on `main`. After a merge that changes any
of them, every run plans plain until the next nightly writes a ledger under
the new machinery.

**What a plain nightly exercises, and what it does not** (review major 3).

- **The ledgered planner, plan-derived ownership and the injection.** The
  writer's self-check (see Writer) plans the nightly's own commit against the
  ledger it just wrote, exactly as a PR would, simulates the shards that plan
  names over the nightly's real results, and runs the real `merge --plan`. So
  a bug in partition, name caps, anchoring, headroom, selector-to-file
  ownership or injection fails the self-check, and no ledger is uploaded,
  before any PR or push can read one.
- **Real mutmut on a mixed argv.** The self-check simulates the shards; it
  does not run mutmut. The first ledgered PR run after a digest reset is the
  first real one. A bug there is red through the fail-closed merge (I2, I3)
  and the gate's re-check (I4), never green. With `push` enabled, that first
  run can be a push; see "Residuals".

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
4. **Opted in.** `MUTATION_LEDGER` names `write`.

Three steps follow the weights steps. All three run under `.venv/bin/python`
(mutmut and PyYAML exist only there), and the generator key and machinery
digest are copied from the plan, where the planner stamped them (review
minor):

1. **Write.** `mutation_ledger.py write --meta mutants --plan PLAN --out
   $RUNNER_TEMP/mutation-ledger.json` builds the ledger from the merged
   `.meta`.
   - It carries only codes whose status is `survived` or `timeout`
     (`mutation_diff.status_of`, `mutation_diff.py:482-494`). Killed, no
     tests, skipped, suspicious, segfault and type-check codes are never
     carried.
   - It refuses a plan with a `carried` list or no generator stamp, an event,
     branch or token outside conditions 1 and 4, and any `None` in the merged
     `.meta`.
2. **Self-check.** `mutation_ledger.py selfcheck --meta mutants --plan PLAN
   --ledger $RUNNER_TEMP/mutation-ledger.json` is a dry run of a ledgered PR
   on this commit (review major 3):
   - it plans the commit against the fresh ledger with the real ledgered
     planner (every function is unchanged, so it carries the most it can);
   - it writes each planned shard's `.meta` as mutmut would, running a key
     only when one of the shard's selectors `fnmatch`es it -- compiled with
     `fnmatch.translate`, independent of the planner's structural reading;
   - it runs the real `merge --plan` over those shards, and checks that every
     row came back with tonight's verdict (carried ones as exactly
     `CARRIED_EXIT`), that killed and the denominator did not move, and that
     the installed mutmut reads `CARRIED_EXIT` as `survived`.
   - Measured on run 45290191649's 54,417 results: 6,566 carried from 1,027
     functions, 70 s locally. A test pins that a merge injecting 1 instead of
     0 fails it.
3. **Upload.** Only when step 2's **outcome** was `success` (a failed
   continue-on-error step *concludes* `success`), upload `mutation-ledger`
   with `retention-days: 30` and `overwrite: true`, so a re-run attempt that
   also passes replaces the ledger rather than leaving two.

All three steps are `continue-on-error: true`, each with its own
`timeout-minutes` (3, 8, 3), and the job's cap grows from 20 to 34 so a hung
ledger step times out as a step, never as the required check (review minor).
**A ledger failure never changes a run's conclusion.** A
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
  if: (github.event_name == 'pull_request' || github.event_name == 'push') && vars.MUTATION_LEDGER != ''
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
     step's `env`. No ledger unless it names this run's event (see
     "Rollout"); and no ledger on an attempt after the first.
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
   - **More than one marker:** no ledger; what the run was is ambiguous. This
     mirrors `ci_proven_tree._inherit` (review minor): a "Re-run all jobs" of
     an idle night carries `inherited-tree-` from attempt 1 and
     `mutated-tree-` plus a ledger from attempt 2.
   - **Exactly one `inherited-tree-` marker and no `mutation-ledger`
     artifact:** step over it. That is an idle night, which mutated nothing
     and inherits an older real run.
   - **Otherwise it is a real run** (a `mutated-tree-` marker or a ledger
     artifact makes it one). It must hold exactly one unexpired
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
  the workspace for the reason given above the shard's `download the plan`.
- The plan step decides on **the file it validates**, never on
  `needs.mutation-ledger.result`. The comment above `mutation-advisory-shard`
  notes that this result is unconfirmed for a continue-on-error job.

**As built, the planner is unchanged and a second command rewrites its
plan.** When `MUTATION_LEDGER` is set and the plan has work, the plan step
runs, after the plan is written:

- `mutation_ledger.py stamp --plan mutation-plan.json`: the generator key and
  machinery digest, for a whole-codebase run's writer to copy;
- on `pull_request` and `push` only, `mutation_ledger.py apply --plan
  mutation-plan.json --ledger L --run-id R --meta mutants`, which rewrites a
  plain full set as a ledgered one or leaves it byte-for-byte and appends
  *"ledger not used: <why>"*.

Neither can fail the step (`|| echo ::warning::`), and `apply` writes the plan
atomically. The plans themselves say whether a ledger may carry into them,
as data: `full_plan(..., ledger_eligible=...)` writes a top-level
`ledger_eligible`, and an absent one is no.

| event | plan | `ledger_eligible` |
|---|---|---|
| `schedule`, `workflow_dispatch` | full; `nightly` (full plus an advisory diff); or none (idle) | **false** (I5): `nightly_plan` forces it, `full` defaults it. The nightly stays a plain full run at 26 on the committed weights. |
| `pull_request` | `diff --shadow` | as the table under "Which functions are carried" says |
| `push`, not proven | `full --ledger-eligible` | **true**. No diff is computed; the machinery digest stands in for the full-run triggers. |
| `merge_group` | `diff --shadow` | `apply` refuses the event. The queue is not enabled. |
| any event, `GITHUB_RUN_ATTEMPT` not 1 | as above | `apply` refuses the attempt. See below. |

**Why a re-run never uses a ledger.** On "re-run failed jobs" GitHub keeps the
outputs of jobs that succeeded, which is why the scope step already guards
idle-nightly's answer on the attempt number (ci.yml:1300-1302). "Re-run all
jobs" is also the escape from a ledgered red (see Escapes).

`stamp` and `apply` run with `.venv/bin/python`, which exists whenever a run
is mutation-relevant. They need no regeneration (review minor): every key,
function hash and mutant count comes from the planner's own `mutants/**/*.meta`,
which the stats run (`mutmut run <one mutant>`) has just written for every file
(`create_mutants_for_file` saves all keys and `hash_by_function_name` before
running anything). Anything that goes wrong inside ledgered planning gives the
plain plan plus a reason that starts `ledger not used:`. That mirrors how `nightly_plan` falls back to
`full_plan` (`mutation_plan.py:366-367, 383-384`). Ledger trouble never fails
the planner.

### Which functions are carried

`diff_plan` returns the plain full plan from four places, and only the first
one is a machinery trigger. So the decision travels as data, never read back
out of reason strings: `full_plan(root, shards, reasons, ledger_eligible=...)`,
and `keep` is the shadow plan's own `sets.diff.functions`.

| call site | what triggered it | ledger |
|---|---|---|
| `mutation_plan.py:247` | `full_run_reasons` fired | **none.** Risk 3: a PR that hits any full-run trigger never uses the ledger. That means the mutation machinery, and also conftest, pytest config and test support (`mutation_diff.py:216-225`). `ledger_eligible: false`, and `apply` records *"ledger not used: this plan is not eligible"*. |
| `:284` | a changed function with no mutants | may be used, nothing kept back |
| `:302` | the scope is too big to pack | may be used, nothing kept back |
| `:319` | the scope is empty under shadow | may be used, nothing kept back |
| `:335` | the shadow plan | may be used, with `keep` = the diff scope (changed functions plus their direct callers) |

At 284, 302 and 319 there is no diff set to compare, and soundness does not
depend on the scope. In the shadow plan, changed functions never match a hash
anyway. Their callers do match, but they run in full in the full set, so the
shadow's per-mutant comparison still compares two measurements.

**The 247 rule is broader than soundness needs.** It follows the commissioning
task, which defines the machinery as "the existing full_run_reasons infra
triggers". That set includes the test-support triggers, but a conftest or
`tests/_*.py` edit changes only how fresh a carried survivor is, never whether
the score is sound. A push with the same edit computes no diff and stays
ledgered.

The cost is real: `tests/conftest.py` changed in 10 of 30 trains (spec
2026-10-31, line 48), and each such PR plans plain. Narrowing 247 to the
machinery triggers is a one-line change, keeping unparsable source and
core-subpackage files plain. That choice is the owner's.

A function is carried only when all of these hold:

1. **The file.** The ledger is well-formed, and its `source.run_id` is the run
   the reader chose (the reader job's `run_id` output).
2. **The global key.** Every part equals this run's: the installed mutmut and
   libcst, the Python minor version, and the config digest.
3. **The machinery.** The machinery digest equals this run's.
4. **The function.** Its hash and mutant count at this commit equal the
   ledger's. Both come from the planner's stats-run `.meta`.
5. **The scope.** The function is not in `keep`.

Its carried mutants are then the ledger's `survived` and `timeout` numbers. A
number with no mutant at this commit means the ledger is malformed, and the
plan is plain. So is a ledger older than 14 days, one whose `source.run_id`
is not the run the reader chose, and one whose source is not a whole-codebase
run on `main`.

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

**A ledgered plan is packed on two constraints: time, and a name budget per
bin** (review minor: packing on time alone puts 10 of 26 bins over the cap).
How the repack works (`mutation_ledger.ledgered_full`, `pack_units`):

- **Unit weights.**
  - A carried function's exact names weigh the ledger's `ms_rerun`; a
    function heavier than an even share is cut into pieces.
  - A changed or un-carried function weighs `ms_rerun + ms_carried`.
  - A new function weighs the mean time per mutant times its count.
  - A file with nothing carried stays one `<module>.*` unit unless it is
    heavier than an even share, when it splits into function patterns.
- **Packing.** Longest first; each unit goes to the least-loaded bin **with
  name room for it**; a named unit no bin has room for is split across the
  bins with the most room. Deterministic: ties break on the unit's sort key
  and the bin index.
- **Un-carry before packing.** If the named mutants exceed 26 × 1,500, the
  functions whose survivors are cheapest to re-run (`ms_carried`) are
  un-carried until they fit: always sound, only slower. The plan says how
  many.
- **Exactly 26 non-empty bins, each anchored.** Every bin must hold an exact
  name or a file pattern; one holding only function patterns takes the
  lightest anchor from a bin with several. A bin of function patterns alone
  selects no clean-run tests and pays the whole-suite clean run (the 11.30-min
  preamble, `mutation_shards.py:239-247`). An empty or unanchorable bin
  (review minor: `matrix` keeps empty shards and `patterns` refuses them) is
  **plain**, with a reason.
- **Headroom.** The pack must pass `headroom_report` at the mutate step's
  190-min cap, or the plan is **plain**, with a reason.

**Measured on run 45290191649's results** (`/private/tmp/claude-501/r45`, the
26 shard artifacts, merged locally): 6,566 carried from 1,027 functions,
0 un-carried, 35,338 names, at most 1,500 in a shard (the fullest at the
cap), and the model's median job time per shard
(`mutation_shards.runner_minutes`) 31.1-35.4 min. That is the
`shard_minutes` list the plan records, for comparison with the first real run.

**The name cap stays at `MAX_NAMES = 1500`** (`mutation_diff.py:318-325`), the
bound the diff shards already run under: about 110 KB of argv, and mutmut's
filter (`key in names or any(fnmatch(...))`, `__main__.py:813`) costs a
ledgered shard what it costs a 1,500-name diff shard.

**Partition check, before the plan is written.** Every generated name must be
covered exactly once, either by the shards' selectors or by the carried list,
and every shard must match at least one mutant (mutmut asserts on an empty
filter, `__main__.py:815`). The selectors are read structurally -- every
selector the planner writes is an exact name or a literal followed by one
`*`, so fnmatch is "equal" or "starts with" -- and a test cross-checks that
reading against `fnmatch.fnmatchcase`. Any gap or overlap is a bug, and the
plan is plain.

### Plan fields

Every plan gains `ledger_eligible` (above). With `MUTATION_LEDGER` set, a
relevant plan also gains `generator` (`{"key": {...}, "machinery": "<sha256>"}`)
and, on a PR or push, a top-level `ledger`: `{"used": false, "why": "..."}`
or `{"used": true}`. On a ledgered plan, `sets.full` gains:

```json
"carried": ["boost_cli.core.store.x_install__mutmut_3", "..."],
"ledger": {"used": true, "run_id": 0, "event": "schedule",
           "created_at": "<ISO 8601>", "head_sha": "<commit>",
           "age_hours": 18.4, "carried": 6566, "carried_survived": 6496,
           "carried_timeouts": 70, "carried_ms": 209969763,
           "functions_carried": 1027, "uncarried": 0, "max_names": 1500,
           "slowest_tail_minutes": 67.5, "shard_minutes": [35.4, "..."]},
"mutants": 54417
```

- `mutants` is the planner's own count of generated names. A plain full plan
  keeps `null`.
- `apply` never writes a `carried` list that is empty: a plan that would carry
  nothing is the plain plan, untouched.
- The planner job gains a new output, `ledgered` (`true` or `false`), read
  from the plan with `jq`; `mutation` only echoes it.
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

- `merge` takes `--plan PLAN [--set full]`, and ci.yml passes it on every full
  gate, plain or ledgered.
- ci.yml's `download the plan` step runs whenever `gate_set == 'full'`, not
  only under shadow.
- Each shard's selectors map to files: `<module>.*`,
  `<module>.<mangled>__mutmut_*`, `<module>.xǁ*` and exact names each resolve
  to one file (`split_qualified`, `mutation_diff.py:330-342`).
- On a plan with no `carried` list, the plan-derived ownership must equal
  `pack()`'s, or the merge refuses. That keeps today's guarantee that the
  planner and the merge agree. The check is keyed on the list's absence, and
  `apply` never writes an empty one or repacks without one (review minor), so
  no ledgered plan can trip it.

**Injection** happens after the per-file union (1145-1162) and before the
unrun check (1173). For each carried name of the file:

- If the name is not a key that the shards' `.meta` lists, the merge refuses:
  *"carried mutant X is not generated at this commit"*.
- If any shard has a code other than `None` for it, the merge refuses:
  *"carried mutant X was also run by shard i"*.
- Otherwise the code is set to `CARRIED_EXIT`.

After injection, the existing check fails closed on any `None` that is left
(I2, I3). **A file whose every mutant is carried** has no selector in any
shard (review minor). Every shard writes every file's `.meta`, with `None`
for what it did not run, so the merge gives such a file shard 0 as its owner
and injects into shard 0's copy; a test pins it. The merge writes
`mutation-carried.json` beside the merged `.meta` (source and carried names),
or removes a stale one on a plain merge. The summary line reads *"merged N
files, M mutants (C carried from ledger run R), from S shards"*.

The merge runs on the runner's `python3`, which has no mutmut, so
`CARRIED_EXIT` is a module constant there. The gate and a mutmut-backed test
pin what it means.

## Gate (`mutation_gate.py`)

The gate takes an optional `--plan PLAN`. On a ledgered plan it:

1. **Checks the injection.** It reads every carried key back from the merged
   `.meta` and exits 2 unless each one is exactly 0 and the installed mutmut
   reads `status_of(0)` as `survived` (I1, I4).
2. **Scores** exactly as today.
3. **Prints provenance** before the score, for example: *"ledgered: 6,566 of
   54,417 mutants carried as survived (6,496 survived and 70 timeout on
   record) from whole-codebase run R (schedule, 2026-11-25T09:31:00Z, 18 h
   old, commit abc1234def56); not re-run on this commit"*. Every value is
   validated (a commit, a UTC time, an event word, integers) before it is
   printed, so nothing from the plan can start a workflow command.
4. **On a FAIL**, says that it is ledgered, what the score would be if every
   carried survivor were killed -- *"arithmetic over this run, not a forecast
   of a plain run"* -- and prints the escapes below. It never calls a red
   conclusive (review major 2).

Exit codes do not change. A ledgered run's lines also go to
`$GITHUB_STEP_SUMMARY`; a plain run writes none, as before.

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

The owner also has a global switch: remove the event's token from the
repository variable `MUTATION_LEDGER`. Each of these routes runs the plain
full gate exactly as it was before this design.

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

`refresh balance hints` and `upload balance hints` gain the condition
`steps.ledgered.outputs.plain == 'true'` (I6), from a step that reads the
downloaded plan file and fails the job when it cannot tell (review minor: an
output string could arrive empty and fail open). And `mutation_shards.py
weights` refuses a source holding `mutation-carried.json`, so even a mis-wired
`if` uploads nothing. A ledgered run's merged `.meta` has no durations for
carried keys, so `weights` would record killed-only time as the whole. (Not
"refuse any key without a duration": no-tests and type-check codes never have
one, in plain runs too.)

`mutation-weights-refresh.yml` already treats a run with no `mutation-weights`
artifact as ordinary: its `download the measured hints` step is
`continue-on-error` (`mutation-weights-refresh.yml:169-177`).

## ci.yml, job by job

| job | change | permissions |
|---|---|---|
| `mutation-ledger` (new) | The reader, on PR and push runs only, and only when `MUTATION_LEDGER` is set. Job-level `continue-on-error`; a stdlib script, then the download and re-upload. | `contents: read`, `actions: read`, `pull-requests: read` |
| `mutation-plan` | `needs` gains `mutation-ledger`. Downloads `mutation-ledger-in` (continue-on-error). A push's full plan passes `--ledger-eligible`; with the variable set, the plan step runs `stamp` and, on a PR or push, `apply`. The `BOOST_REQUIRE_MUTMUT` step also runs `tests/unit/test_mutation_ledger.py` (review minor: the mutmut-backed pins would otherwise skip everywhere). New output `ledgered`. | unchanged: `contents: read` |
| `mutation-shard`, `mutation-advisory-shard` | none | unchanged |
| `mutation` | See the list below. | unchanged: `contents: read` |

The `mutation` job changes in seven places:

- The plan is downloaded whenever `gate_set == 'full'`.
- A new step, `ledgered`, reads the plan file: `plain=true|false`, and it
  fails the job on a ledgered plan on a `schedule` or `workflow_dispatch` run,
  or when it cannot tell.
- `merge` runs with `--plan`.
- `mutation_gate.py` runs with `--plan`.
- The weights steps run only when `steps.ledgered.outputs.plain == 'true'`.
- New writer steps (continue-on-error, own timeouts) upload `mutation-ledger`,
  on green, plain `schedule` and `workflow_dispatch` runs on `main` only.
- `timeout-minutes` 20 → 34, the writer's step caps on top.

What does not change:

- **Required checks.** `mutation-ledger` is advisory, and
  `.github/required-checks.txt` stays as it is.
- **Caches.** No `actions/cache` anywhere.
- **zizmor.** `.github/zizmor.yml` anchors no ignore in ci.yml today, but check
  the anchors again after the edit (`tests/unit/test_zizmor_ignores_still_anchor.py`).
- **Billing.** It stays on GitHub Free for a public repository: standard
  runners, width 26, artifacts only.

With `MUTATION_LEDGER` set, the reader adds one short job ahead of the planner
on every PR and push run, including ones that cannot use a ledger (machinery
PRs, docs-only PRs whose plan is none, proven pushes). It runs beside `proven`,
not after it, so on a push it costs the critical path only what it takes
beyond `proven`; on a PR it is the planner's one extra dependency. On the
20-job account cap it can queue, and that queue time is on the critical path
(review minor). It is the price of keeping the planner's token at
`contents: read`; the first real runs should say what it costs.

## The six risks

| # | risk (from the verifier) | handled by |
|---|---|---|
| 1 | the only writer was down for 12 days | The reader decides on the newest real run within 14 days, and a red one, or one with no ledger, means plain. 11-13 to 11-23 would have been plain throughout. Retention is 30 days, longer than the 14-day bound. |
| 2 | red-gate deadlock | No ledger is used past a red whole-codebase run. A ledgered FAIL says it is ledgered and prints the escapes: re-run all jobs, the label, the repository variable. |
| 3 | a PR judging its own machinery | `full_run_reasons` gives `ledger_eligible: false`, as data rather than read from reason strings. The machinery digest keeps PRs and pushes off a ledger until a nightly under the same machinery has passed the self-check, which dry-runs the ledgered planner and merge. The reader is itself a `scripts/mutation_*.py` file. Push is a separate token, added after the A/B. |
| 4 | documented constraints | "What this reverses", plus dated pointers in the 2026-10-31 spec (196-200) and plan (26) |
| 5 | exact names are required | Only the non-carried mutants of functions with carried ones are named, with patterns everywhere else. The cap stays at 1,500, enforced by a two-constraint pack that splits named functions and un-carries before it would exceed it. |
| 6 | merge ownership, injection, weights, compare, permissions, key | `merge --plan` and its injection rules; invariants I1-I6; the weights guard; compare's `keep` and its refusal; a reader job with `actions: read`; a key that identifies the mutant and never the tests |

## Expected effect

*Model, not measured.* Runner-minutes are not money here: a public
repository on standard runners pays nothing for them, and this design keeps
it that way (no paid plan, no larger runners, width 26, artifacts only). What
an affected run gains is **wall clock on the blocking path and slots under the
20-job cap**:

- **Wall clock per ledgered full run.** The two-constraint pack, run on
  45290191649's results, models each shard's median job at 31.1-35.4 min
  (`runner_minutes`, a model its author calibrated as about 7% optimistic),
  against about 61.5 measured per plain shard (1,598-1,601 shard runner-min
  over 26). Add the planner's stats
  run, the reader ahead of it (and any queue for its slot), the 26 shards
  queued on 18-20 free slots, and the gate. The verifier's earlier end-to-end
  figure, 72-86 min against 149.4 and 157.8 measured, assumed packing on time
  alone and leaves those out; treat it as an upper bound on the saving until
  the first run. No regeneration is added: the planner reads the stats run's
  `.meta`.
- **Slots.** The same 26 shards, each held about half as long, so the shard
  phase occupies the 20-slot cap about half as long, for everything else that
  queues behind it.
- **Runner-min, for context only:** from 1,598-1,601 to about 760-845 per
  ledgered full set (the verifier's arithmetic, including re-runs of changed
  functions' survivors at 8.1% median, 13.4% p75, spec:44).
- **Which runs benefit:**
  - *While the diff gate is still in shadow* (Task 8 is blocked on the
    DISAGREE above), in 11-01 to 11-23:
    - the 11 shadow and 9 empty-scope PR full runs;
    - those of the 4 "other" PR runs that were forced by a changed function
      with no mutants. The conftest and test-support ones stay plain under the
      247 rule.
    - the 7 pushes that were not proven.

    Fewer of those runs completed, and the machinery digest switches some off.
  - *After Task 8:* at most 1 PR set and 7 pushes per 23 days, at most about
    6,000-7,000 runner-min, again minus what the digest switches off. Pushes
    that merge machinery changes are among those 7, and the digest makes them
    plain.
- **What that adds up to, for the owner to weigh against the complexity.**
  After Task 8 it is a few runs a month: at most 1 PR set and 7 pushes per 23
  days, fewer once machinery merges are taken out. Until Task 8 lands, the PR
  runs above as well.
- **The nightly does not change:** about 1,600 runner-min. It is the
  refresher.

## Test plan

*As built:* every bullet below is a test in `tests/unit/test_mutation_ledger.py`
(soundness property, writer, planner, selfcheck, reader, gate),
`test_mutation_shards.py` (merge and injection), `test_mutation_plan.py`
(eligibility and the workflow), `test_mutation_diff.py` (compare) or
`test_ci_proven_tree.py` (the job graph with `MUTATION_LEDGER` unset and set).

Prove every test red first, by reverse-applying its change, never with
`git stash`. Tests that need mutmut run in `mutation-plan`'s
`BOOST_REQUIRE_MUTMUT` step, which now names `test_mutation_ledger.py` beside
`test_mutation_diff.py` and `test_mutation_plan.py` (`test_mutation_shards.py`
needs no mutmut). The rest run in every `tests` cell.

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
  - a carried key that was not generated.
- A file whose every mutant is carried, which no selector names, gets shard
  0's `.meta` to inject into (review minor 4). A file named by no selector
  whose mutants are not all carried still fails "assigned to no shard".
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
- `selfcheck` fails when the merge injects 1 instead of 0, which proves the
  check bites; fails when `CARRIED_EXIT` means a kill; fails when the merge
  refuses; and passes on a correct ledger.

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
- It steps over an idle night to a green real run's ledger, and plans plain
  on a run with two markers.

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

- It exits 2 on a carried key that is not 0, one that is missing, and when
  mutmut does not read 0 as survived.
- A ledgered FAIL says it is ledgered and prints the escapes; it never says
  "conclusive" or "must lie in".

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
  - The weights steps are guarded on the plan-file step's `plain`.
  - The writer steps are guarded and continue-on-error, and their upload
    depends on the self-check.
  - The `ledgered` step refuses a ledgered plan on a whole-codebase run, and
    an unreadable plan.
- **Caches.** No `actions/cache` in any `mutation*` job. This widens the
  existing shard-only test at `test_mutation_plan.py:1032`.

**The unset path** (`test_mutation_plan.py`, `test_mutation_ledger.py`).

- Every plain plan the planner writes is exactly `full_plan`'s set, and
  `merge --plan` reads it exactly as main's plan-less merge did: same exit,
  stdout and tree bytes, and the same refusal. That covers `full` plain and
  `--ledger-eligible`, the shadow, the empty shadow, the three diff-to-full
  fallbacks, and the nightly with and without its shadow.
- The same holds at 1 to 26 shards on a tree with a split file, a class
  file, a subpackage, two `__init__.py` and empty bins.
- The gate prints, returns and writes the same with and without a plain
  `--plan`, on PASS and on FAIL.
- The `ledgered` step answers `plain=true` for every plain shape.
- `ledger_eligible` is read by `mutation_ledger.py` alone, and `matrix` and
  `patterns` give the same bytes with it flipped or absent.
- An applied plan goes through the real `matrix`, then each shard's
  `patterns` argv, then mutmut's filter, `merge --plan` and `gate --plan`.

**Housekeeping.**

- `make lint`.
- The SPDX header on `scripts/mutation_ledger.py`.
- A pointer in the `mutation_diff.py:20` docstring.

## The first real observation

Nothing changes until a green nightly writes a ledger under the merged
machinery:

1. **The implementation PR** edits `scripts/mutation_*.py` and
   `jobs.mutation*`, so it plans plain (a full-run trigger). **Its merge push**
   is most likely proven, and then runs no mutation at all. If it is not
   proven, it finds no ledger (*"the newest real whole-codebase run R wrote no
   ledger"*) and plans plain.
2. **The next nightly** (09:30 UTC) runs plain at 26 shards, about 1,600
   runner-min as today. On a green gate it writes, self-checks and uploads
   `mutation-ledger`.
   - If the survivor count is still near 45290191649's 6,496 plus 70 timeouts,
     expect about 6,566 carried numbers across about 1,027 functions.
   - If its `mutation` is red, nothing is written, and the next day decides.
3. **The next PR or push that is neither machinery nor proven** shows three
   things:
   - in `mutation-ledger`: *"mutation-ledger: ledger of whole-codebase run R
     (schedule, T)"*;
   - in the plan reason: the carried count, the functions carried and
     un-carried, and the age;
   - in the gate: the provenance line, then the score.

   Expect up to 26 shards with a mutation phase of about 20-30 min each, and a
   whole run near 72-86 min. Every number here is a model until this run.
4. **One A/B comparison on the same SHA.**
   - Open a throwaway draft PR with a test-only change, which is no trigger.
   - After its ledgered attempt 1, and **before re-running**, download
     attempt 1's `mutation-full-shard-*` and `mutation-plan` artifacts. Shard
     results are kept for 1 day (ci.yml:2013), and a re-run uploads under the
     same names.
   - Then choose "Re-run all jobs". Attempt 2 is plain on the same merge
     commit.
   - Compare the two attempts' per-mutant codes, **per key, over the
     non-carried keys, by direction** (review major 2; totals would let stale
     carried rows hide a shift in kills):
     - *up*: killed in the ledgered attempt, not killed in the plain one;
     - *down*: the reverse.
     - **Stop rule:** stop, and remove `pull_request` from
       `MUTATION_LEDGER`, if *up* exceeds *down* plus the keys on the
       known-flaky list (which starts with
       `store.x__install_project_skill__mutmut_223`, artifact 13610263304,
       pattern=survived, exact=killed). Selector-dependent verdicts that lean
       toward "killed" are the one way a ledgered run can score above a plain
       one.
     - For carried keys, the number plain killed measures how stale the
       ledger was. Any carried key not exactly 0 in the ledgered attempt is
       an injection bug, which the gate already refuses.
   - The cost is one more plain full set, in free minutes on a public
     repository.

## What could not be verified locally

- **The owner's selection.** The verbatim option text under "Status" is as
  relayed by the task that commissioned this implementation. No copy in the
  owner's own hand was available here to compare it with.
- **A ledgered shard end to end.** That mutmut takes a mixed argv of file
  patterns, function patterns and up to 1,500 names, and what its clean run
  costs with mixed selectors. The self-check simulates shards with `fnmatch`,
  as mutmut's filter does; it does not run mutmut.
- **The real per-shard name counts on a future commit.** On run 45290191649's
  results the pack's maximum is 1,500 and the total 35,338, measured locally
  by the planner itself.
- **The cross-run download.** `action.yml` was read at the pinned SHA, but the
  download was not run.
- **Re-run behaviour.** Four things are unconfirmed:
  - what `GITHUB_RUN_ATTEMPT` is on "Re-run all jobs";
  - whether a re-run's success fires `publish.yml`'s `workflow_run`;
  - whether `vars` is read again on a re-run;
  - how artifacts with the same name behave across run attempts. The A/B
    step, `overwrite: true` and the reader's "exactly one ledger" rule all
    depend on it.
- **Free artifact storage.** That artifact storage stays free on a public
  repository. It is consistent with the 90-day shadow reports already kept.
- **The time saving.** It is a model that its own author calibrated as about 7%
  optimistic.
- **The mutmut version.** The mutmut 3.8.1 source was read from an extracted
  wheel. The shared local venv holds 3.8.0, and nothing was installed into it;
  the mutmut-backed tests ran against 3.8.0.
- **The reader against the real API, `vars` in `if:` expressions, and the
  `MUTATION_LEDGER` variable itself.** The reader ran only against a fake API;
  actionlint and zizmor were not run locally.

## Residuals

- **After a machinery-digest reset, the first ledgered run is the first real
  mixed-argv run under that machinery** (review major 3). With only
  `pull_request` enabled that is a PR, and a bug there is a red PR with three
  escapes. With `push` enabled it can be a push to `main`, whose red holds the
  release until "Re-run all jobs" (about 150 min) or the owner removes `push`.
  The self-check dry run moves every planner, partition, ownership and
  injection bug to the nightly; it cannot move a mutmut one. Closing this
  fully would need the reader to require a green ledgered PR run under the
  same digest before a push may read the ledger. That is not built; the
  rollout asks the owner to add `push` only after one exists.
- **A ledgered PR run can prove its merge push.** `ci_proven_tree` fact 2
  takes a green first-attempt PR run as the push's mutation verdict, so with
  only `pull_request` enabled a release can rest on a ledgered score (fact 3
  still requires a green plain whole-codebase run within 48 h). Making
  `ci_proven_tree` refuse a ledgered PR run would close it and cost each such
  merge a full run; it is the owner's choice and not built.
- **Selector-dependent verdicts** (review major 2) are measured by the A/B,
  not prevented. `forkserver` isolation would remove the cause, and is a
  separate decision.
- **Freshness.** A test that kills a carried survivor gets no credit until a
  nightly writes the next ledger.

## Review findings, and where each is handled

The adversarial review of this design (verdict *fix-then-ship*) and what the
implementation does about each finding:

| severity | finding | handled |
|---|---|---|
| blocker | the reversals were recorded as owner-approved with no owner words to show it | Status, "What this reverses" and both 2026-10-31 amendments now carry the owner's dated selection of 2026-11-23, quoted verbatim, and claim nothing wider than its words. What the words do not cover is listed in Status: timeouts, `workflow_dispatch` as a writer, a release resting on a ledgered score, and a ledgered PR proving its push. Each reversal is still a separate `MUTATION_LEDGER` token, unset by default, and "Rollout" says plainly that `push` gates the release. |
| major | soundness assumed non-carried mutants run as in a plain run | "Soundness" restated; the gate no longer claims a range or a conclusive red; the A/B stop rule is per key and by direction; `forkserver` noted as the owner's separate option |
| major | the release path would be the first test of ledgered code, after every digest reset | `push` is its own token, added after the A/B; "Rollout" says that `pull_request` alone also reaches a release, through a proven push; the nightly self-check is a dry run of the ledgered planner and merge; the mixed-argv gap is stated under "Residuals". Adding `push` only after a green ledgered PR run is the owner's ordering in "Rollout"; the reader does not enforce it ("Residuals") |
| minor | the 1,500-name cap binds on packing by time alone | two-constraint pack (time, names per bin), measured on 45290191649: max 1,500, 0 un-carried |
| minor | a fully carried file has no owner | the merge gives it shard 0; tested |
| minor | the pack-equality check keyed on "carries nothing" | keyed on the absence of `carried`; `apply` never writes an empty one |
| minor | the writer's interpreter and key source | `.venv/bin/python`; key and digest stamped by the planner, copied from the plan |
| minor | the upload was not continue-on-error, and gated on conclusion | all three writer steps continue-on-error with own timeouts; gated on `outcome`; pinned in `test_mutation_plan.py` |
| minor | the weights guard read an output string | decided from the plan file; `weights` refuses a ledgered merge's sidecar |
| minor | mutmut-backed tests would skip in CI | `test_mutation_ledger.py` added to the `BOOST_REQUIRE_MUTMUT` step |
| minor | regeneration and the reader's queue were missing from the cost model | no regeneration (the stats run's `.meta` is read); the reader's cost is named in "ci.yml, job by job" and "Expected effect" |
| minor | the reader classified runs more loosely than `_inherit` | more than one marker is no ledger; a `mutated-tree-` marker or a ledger makes a run real |
| minor | empty bins and failed headroom were unstated | exactly 26 non-empty anchored bins and a passing `headroom_report`, else plain with a reason |
| minor | the expected effect led with runner-minutes | it leads with wall clock and slots, and the post-Task-8 run count |

## Left to the owner

- Whether to set `MUTATION_LEDGER`, and which tokens, in the order "Rollout"
  gives. Setting a token is also what confirms the parts of it that the
  selected option's words do not cover (see "Status").
- Creating the `mutation-no-ledger` label.
- Whether to evaluate `process_isolation = forkserver`.

## Sources

- **Research and its adversarial verification**, with run, job and artifact
  ids: `mut-research.txt` in the session scratchpad (P1, and its verdict).
- **mutmut 3.8.1:**
  - `__main__.py:198-215, 730-751, 805-817, 1028-1030, 1089-1098`;
  - `stats.py`;
  - `mutation/file_mutation.py:43-118`.
- **This tree:** the files and lines cited inline.
