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

CI runs `python3 scripts/build_registries.py --check` and fails on drift; the
same guard lives in `tests/unit/test_registries_fresh.py`. Regenerating last also
keeps line-adjacent JSON conflicts between parallel branches rare.

## Pull requests

Branch from `main`, keep PRs focused, and write the PR description in the
commit message (it becomes the release notes via release-drafter).
