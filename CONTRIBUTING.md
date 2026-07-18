# Contributing to boost

Thanks for taking an interest! boost is deliberately small and dependency-free,
so contributing is mostly about keeping the quality gates green.

## Dev setup

```bash
git clone https://github.com/jonnyeclectic/boost && cd boost
make venv          # pytest, coverage, mutmut, ruff, mypy — runtime stays stdlib-only
```

Every test runs against a throwaway `$HOME`, so nothing touches your real
agent configs.

## The gates (CI runs all of these)

| Command | Gate |
|---|---|
| `make test` | unit + functional suites, **≥80% line coverage** |
| `bash tests/smoke.sh` | 152 end-to-end checks through the real `./boost` shim |
| `make mutation` | mutmut over `boost_cli/core`, **≥80% mutants killed** |
| `ruff check boost_cli tests` | lint, zero findings |
| `mypy` | type check, zero errors |

## Ground rules

- **Stdlib only** at runtime. No third-party imports in `boost_cli/`.
- New commands live in `boost_cli/commands/<group>.py` as
  `def cmd_<name>(argv) -> int` and are dispatched lazily from `cli.py`.
- Behavior changes need tests — functional tests drive the CLI in-process via
  `boost_cli.cli.main` (see `tests/conftest.py` for the fixtures).
- Anything under `boost_cli/core/` is mutation-tested; expect to add unit
  tests that actually kill your mutants.

## Generated files — never hand-edit

Some checked-in files are build outputs. Edit the source, regenerate, and commit
the result **as the final step before opening the PR** so the artifact never
drifts from its source (CI fails the build otherwise):

| Generated file | Source of truth | Regenerate with |
|---|---|---|
| `boost_cli/data/registries.json` | `SKILLS`/`RULES`/`WORKFLOWS` tuples in `scripts/build_registries.py` | `python3 scripts/build_registries.py` |
| `docs/roadmap.html` | one file per item (`board: code`) under `docs/roadmap/items/` | `python3 scripts/build_roadmap.py` |
| `docs/design-roadmap.html` | one file per item (`board: design`) under `docs/roadmap/items/` | `python3 scripts/build_roadmap.py` |

Or regenerate everything at once with `make generate`. CI runs the matching
`--check` for each and fails on drift; the same guards live in
`tests/unit/test_registries_fresh.py` and `tests/unit/test_roadmap_fresh.py`.

### The roadmap is data-driven — add items, don't edit the HTML

To add or change a roadmap card (either board), create/edit a small
Markdown-with-frontmatter file under `docs/roadmap/items/` (set `board: code` or
`board: design`) and run `python3 scripts/build_roadmap.py`.
**Never hand-edit the cards or the counters in `docs/roadmap.html` /
`docs/design-roadmap.html`** — they are regenerated, and the counters are
computed. This
is what lets parallel loops work the roadmap without colliding: two loops adding
two items create two different files (clean merge); a status change edits one
small file instead of a shared line in a 1,400-line document. Regenerating last
also keeps line-adjacent conflicts rare.

## Pull requests

Branch from `main`, keep PRs focused, and write the PR description in the
commit message (it becomes the release notes via release-drafter).

## Release safety — require branches be up to date

Every merge to `main` cuts a PyPI release, and two PRs that are each green in
isolation can still land a broken *combination*. Guard against it in the `main`
branch ruleset (**Settings → Rules → Rulesets**):

- **Require a pull request before merging.**
- **Require status checks to pass** — select `lint`, every `tests (…)` matrix job,
  `mutation`, and `CodeQL`, and tick **Require branches to be up to date before
  merging**. This is the key one: it forces each PR to be rebased onto the latest
  `main` and re-pass the full gate before it can merge, so an incompatible pair
  can't both land — the second PR must include the first and re-run CI.

Then land PRs with `gh pr merge --squash` once green (never onto a red release).

### Merge queue (organization-owned repos only)

GitHub's **merge queue** auto-batches and re-tests queued PRs against the current
tip — a stronger, hands-off version of the "up to date" rule above. It is only
available on **organization-owned** repositories, so it does **not** appear in the
ruleset for this user-owned repo. The CI workflow already listens for the
`merge_group` event (it runs on a `gh-readonly-queue/*` ref and never triggers the
release), so if this repo is ever transferred to an org, enable **Require merge
queue** in the ruleset and it activates with no code changes — then merge with
`gh pr merge --squash --auto`.
