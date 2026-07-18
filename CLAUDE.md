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

## Parallel work & concurrent loops

More than one agent (or `/loop` session) may be working this repo at once. To
keep them from clobbering each other:

- **Never edit a checkout that has someone else's branch checked out.** The user
  works live in `~/boost`; long-running loops use a separate `git worktree`
  (e.g. `~/boost-loop`, which needs its **own** `.venv` because mutmut wants an
  editable `pip install -e .` pointed at that tree). Run `git worktree list` and
  `git status` before touching a tree — staged or unstaged changes mean another
  agent is mid-edit there, so pick a different worktree.
- **Branch off `origin/main`, one topic per branch.** `git fetch origin main`
  then `git checkout -B loop/<topic> origin/main`. Keep changes additive and
  file-scoped so parallel branches merge without conflicts.
- **Coordinate through PRs, not the working tree.** `gh pr merge` is server-side
  and won't touch anyone's local checkout. Before committing a file, inspect
  `git status` / `git diff` — if another session has it staged or dirty, leave
  it to that owner rather than committing over their in-flight work.
- **Every merge to `main` cuts a PyPI release.** Land one coherent change per PR,
  never merge onto a red release, and after merging confirm the publish workflow
  goes green — not just the PR checks.

### The roadmap is data-driven — add items, never hand-edit the HTML

`docs/roadmap.html` is **generated** from one file per item under
`docs/roadmap/items/*.md` by `scripts/build_roadmap.py` (this is what stopped the
roadmap being the repo's #1 merge-conflict source). To add or change a card:

1. Create/edit `docs/roadmap/items/<id>.md` — a Markdown-with-frontmatter file
   (`id, board: code, section, status, category, complexity, impact, wow, note,
   order, owner, pr, title` + the card body after the `---`).
2. Run `python3 scripts/build_roadmap.py` (or `make generate`) and commit both
   the item file and the regenerated HTML. Counters ("Loop finds" etc.) are
   **computed** — never hand-type them.

Never hand-edit the `<article>` cards or snapshot counters in `docs/roadmap.html`:
CI's `build_roadmap.py --check` and `tests/unit/test_roadmap_fresh.py` fail on
drift. Two loops adding two items now touch two *different files* → clean merge.

**Claiming an item (so two loops never pick the same one):** set `status:` and
`owner: loop/<topic>` in that item's file on your branch and open the PR. Two
loops claiming *different* items edit different files (no conflict); two loops
claiming the *same* item edit the same small file, so the second merge conflicts —
the intended "already claimed" signal, first-to-merge wins. (`docs/design-roadmap.html`
is still hand-edited until the Phase 1b migration lands.)

## Layout

- `boost_cli/commands/` — CLI command groups   · `boost_cli/core/` — engine (the mutation-gated code)
- `boost_cli/data/` — shipped catalog data (generated)   · `scripts/` — build/gate tooling
- `tests/unit`, `tests/functional`, `tests/smoke.sh` — the three test tiers
- `docs/` — `overview.html` (visual guide), `DEBUGGING.md`; `roadmap.html` is generated from `docs/roadmap/items/*.md` (see above)
