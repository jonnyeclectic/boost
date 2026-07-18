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

## Pull requests

Branch from `main`, keep PRs focused, and write the PR description in the
commit message (it becomes the release notes via release-drafter).
