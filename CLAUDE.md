# CLAUDE.md — working rules for the boost workspace

boost is a "Homebrew for AI coding skills": a Python CLI (`boost_cli`) that finds,
installs, and governs the skill/rule/workflow files that AI coding agents run on.
Package name on PyPI is `boost-skill-cli`; the command is `boost`.

## The one gate that matters

Before calling any change done, run the full gate:

```bash
make check          # == lint test smoke mutation
```

It is four gates and **all must pass**:

| Gate       | Command                                        | Threshold |
|------------|------------------------------------------------|-----------|
| `lint`     | `ruff check boost_cli tests` + `mypy`          | zero errors |
| `test`     | `pytest tests/unit tests/functional --cov`     | **80%** coverage (`fail_under = 80`) |
| `smoke`    | `bash tests/smoke.sh`                           | 0 failed |
| `mutation` | `python3 scripts/mutation_gate.py --run --min 80` | **80%** of `boost_cli/core` mutants killed |

New/changed core logic needs tests that both cover it *and* kill mutants —
untested code counts as unkilled mutants, so the mutation gate fails even at 80%
line coverage. Target `boost_cli/core` behavior with assertions, not just imports.

## Non-obvious rules

- **`boost_cli/data/registries.json` is GENERATED — never hand-edit it.** The
  source of truth is `scripts/build_registries.py` (the `SKILLS` / `RULES` /
  `WORKFLOWS` tuples). Edit those, then regenerate:
  `python3 scripts/build_registries.py`. Each row is
  `(owner/repo, category, focus, est_items, confidence)`. Add awesome-list repos
  to `LIST_ONLY` so item-count math stays honest. Verify a repo is real
  (`gh api repos/<owner/repo>`) before adding it.
- **Sandbox tests via env, and export separately.** boost state lives under
  `HOME`/`BOOST_HOME`; tests point them at a tempdir. In zsh, one-line chains
  like `export A=$(...) B=$A/x` leave `B` broken — use separate `export`
  statements.
- **Versioning is setuptools-scm from git tags.** There is no `__version__`
  constant and `boost_cli/_version.py` is generated + gitignored. Don't hardcode
  or assert exact versions; version tests are shape-only (`^boost \S+$`). The
  publish workflow filename must stay `publish.yml` (PyPI Trusted Publisher
  matches on it).
- **Target Python ≥ 3.9** (`requires-python = ">=3.9"`). Avoid 3.10+-only syntax
  (structural pattern matching, `X | Y` runtime unions in non-annotation context).
- **Three item kinds, one scanner.** `core/catalog.scan_dir` indexes `skill`
  (SKILL.md), `rule` (.mdc/.cursorrules/.windsurfrules/.clinerules), and
  `workflow` (commands/agents/workflows Markdown). **Only `skill` installs** —
  `store.install` refuses non-skill kinds; rules/workflows are search/tap-only.

## Layout

- `boost_cli/commands/` — CLI command groups   · `boost_cli/core/` — engine (the mutation-gated code)
- `boost_cli/data/` — shipped catalog data (generated)   · `scripts/` — build/gate tooling
- `tests/unit`, `tests/functional`, `tests/smoke.sh` — the three test tiers
- `docs/` — `overview.html` (visual guide), `DEBUGGING.md`
