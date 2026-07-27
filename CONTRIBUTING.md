# Contributing to boost

Thanks for taking an interest! boost is deliberately small and dependency-free,
so contributing is mostly about keeping the quality gates green.

## Dev setup

```bash
git clone https://github.com/jonnyeclectic/boost && cd boost
make venv          # every gate tool, hash-pinned — runtime stays stdlib-only
```

Every test runs against a throwaway `$HOME`, so nothing touches your real
agent configs.

### The toolchain is hash-pinned

`make venv` and every CI job install from the generated
[`requirements/*.txt`](requirements/), which pin an exact version **and every
artifact's sha256** for the full transitive closure — pip enforces those hashes,
so a yanked or tampered dependency fails the install instead of silently
changing a build. Your venv and the CI runner get identical bytes.

To change a tool, edit the `.in` file and regenerate:

```bash
python3 scripts/lock_toolchain.py            # rewrite the .txt files
python3 scripts/lock_toolchain.py --upgrade  # re-resolve to newest allowed
python3 scripts/lock_toolchain.py --check    # what `make lint` runs
```

Commit both the `.in` and the regenerated `.txt`; a stale lock fails `make lint`.
Regenerating needs `uv` (installed by `make venv`); *installing* never does.

### Reproduce the whole gate — `nox`

[`noxfile.py`](noxfile.py) runs the exact gate the CI jobs run, in isolated
venvs, across the supported interpreters:

```bash
pipx install nox        # or: pip install nox
nox                     # lint + tests on every installed interpreter
nox -s lint             # one session
nox -s "tests-3.12"     # tests on a single interpreter
nox -s smoke -s mutation
```

Each session installs the same tools and runs the same commands as `make` and
CI, so "green on my machine" and "green in CI" mean the same thing.

### Pre-commit hooks (recommended)

Catch the `make lint` findings *before* they reach CI:

```bash
pip install pre-commit && pre-commit install   # once
pre-commit run --all-files                      # or run everything now
```

`git commit` then runs ruff, mypy, codespell and the whitespace fixers on your
staged files. The hooks in [`.pre-commit-config.yaml`](.pre-commit-config.yaml)
are pinned to the same tool versions the lint gate uses, and
[pre-commit.ci](https://pre-commit.ci) runs them on every PR and pushes any
auto-fixes straight back onto the branch.

## Optional dashboards (Codecov, SonarCloud)

Two hosted dashboards are wired up but **inert until someone onboards them**.
Both are deliberately *non-blocking*: boost's own gates run offline and are the
authoritative ones, and a merge should never hinge on a third party's uptime.

| Dashboard | To enable | Config |
|---|---|---|
| **Codecov** — PR diff-coverage comments, file sunburst, trend | add a `CODECOV_TOKEN` repo secret | [`codecov.yml`](codecov.yml) |
| **SonarCloud** — bugs, smells, security hotspots, duplication | import the repo at [sonarcloud.io](https://sonarcloud.io) (Analysis Method: GitHub Actions), then add the generated token as `SONAR_TOKEN` | [`sonar-project.properties`](sonar-project.properties) |

Without the secret each step skips itself — the `if:` reads the token through
`env`, since a secret can't be referenced directly in an `if`. The SonarCloud job
also writes a note to the run summary saying what to do, so a skipped run
explains itself instead of looking broken. Neither is in the required-checks
list, and neither should be added to it.

## The gates (CI runs all of these)

| Command | Gate |
|---|---|
| `make test` | unit + functional suites, **≥80% line coverage** |
| `make patch-coverage` | changed-line coverage vs `main`, **≥80% of the diff** (PRs) |
| `bash tests/smoke.sh` | 170 end-to-end checks through the real `./boost` shim |
| `make mutation` | mutmut over `boost_cli/core`, **≥80% mutants killed** |
| `ruff check boost_cli tests` | lint, zero findings |
| `mypy` | type check, zero errors |
| `pyright` | second type checker over `core/` — None-flow & narrowing, zero errors |
| `lint-imports` | layering: `core/` imports no `commands/`/`cli`; CLI depends inward |
| `vulture` | dead-code radar: no unused imports / unreachable code (confidence ≥80) |
| `xenon` | complexity ratchet: aggregate cyclomatic complexity can't regress (avg ≤B) |
| `refurb boost_cli` | modernization smells the ruff families miss, zero findings |
| `scripts/lock_toolchain.py --check` | the hash-pinned toolchain matches its `.in` declarations |

## Ground rules

- **Stdlib only** at runtime. No third-party imports in `boost_cli/`.
- New commands live in `boost_cli/commands/<group>.py` as
  `def cmd_<name>(argv) -> int` and are dispatched lazily from `cli.py`.
- **Respect the layers** (`cli → commands → core`): `core/` is the engine and
  must import neither `commands/` nor `cli`; `commands/` must not reach up into
  `cli`. `import-linter` enforces this — see `[tool.importlinter]` in
  `pyproject.toml` (the one allowlisted edge is `completions` reading the
  `COMMANDS` registry).
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
| `docs/commands.html` | the CLI itself — `COMMANDS` + each command's argparse parser | `python3 scripts/build_command_reference.py` |

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
- **Require status checks to pass** — the list is no longer prose. It lives in
  [`.github/required-checks.txt`](.github/required-checks.txt), and
  `scripts/check_required_checks.py` (part of `make lint`, so part of CI) fails
  if a name there stops matching a real job that runs on `pull_request`. Get the
  exact payload with `python3 scripts/check_required_checks.py --print-api`.
- Tick **Require branches to be up to date before merging**. This is the key one:
  it forces each PR to be rebased onto the latest `main` and re-pass the full
  gate before it can merge, so an incompatible pair can't both land — the second
  PR must include the first and re-run CI.

> Check names must be **unique across workflows** — GitHub matches a required
> check by name alone. Three names collided before this was written (`lint` in
> ci/markdownlint/theme-lint, `audit` in lighthouse/pip-audit, `analyze` in
> codeql/sonarcloud), so the older advice here to "select `lint`" named three
> different jobs and could not be applied as written. The gate now refuses any
> duplicate.

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
