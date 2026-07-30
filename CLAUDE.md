# CLAUDE.md — working rules for the boost workspace

boost is a "Homebrew for AI coding skills": a Python CLI (`boost_cli`) that finds,
installs, and governs the skill/rule/workflow files that AI coding agents run on.
Package name on PyPI is `boost-skill-cli`; the command is `boost`.

## Common commands

```bash
make venv                                      # .venv from the hash-pinned requirements/*.txt
.venv/bin/pytest tests/unit/test_catalog.py -q                    # one test file
.venv/bin/pytest tests/unit/test_catalog.py::test_scan_dir -q     # one test
.venv/bin/pytest tests/functional -q -k install                   # functional tests matching "install"
make lint                                      # the whole static tier — read the recipe, it is long
make test                                      # unit + functional with 80% coverage gate
make check                                     # the full required gate — see table below

# run boost itself against a disposable HOME (never your real ~/.boost):
export HOME=/tmp/boost-sandbox && mkdir -p $HOME
python3 tests/make_fixture.py /tmp/fixture-tap
./boost tap /tmp/fixture-tap
./boost install brainstorming
./boost doctor
```

`make venv` installs from `requirements/*.txt`, which are hash-pinned and are the
same files CI installs (`scripts/lock_toolchain.py --check` gates them against
drift) — so a dev venv and a runner resolve to identical bytes. Don't `pip
install` a lint or test tool by hand; add it to the right requirements file and
regenerate the lock, or `make lint` passes for you and fails in CI.

The functional/unit `sandbox` fixture (`tests/conftest.py`) also sets
`BOOST_NO_AI=1` and `BOOST_ASSUME_YES=1` so tests are deterministic and never
block on a confirm prompt or a real AI call — override explicitly in a test
that means to exercise the AI or confirmation path.

## The one gate that matters

Before calling any change done, run the full gate:

```bash
make check          # == lint eval test smoke mutation
```

It is five gates and **all must pass**:

| Gate       | Command                                        | Threshold |
|------------|------------------------------------------------|-----------|
| `lint`     | `ruff check boost_cli tests` + `mypy`          | zero errors |
| `eval`     | `ensure_eval_corpus.sh` + `eval_retrieval.py --build -k 10 --fail-under 0.85` | BM25 recall@k **≥ 0.85** over the pinned corpus |
| `test`     | `pytest tests/unit tests/functional --cov`     | **80%** coverage (`fail_under = 80`) |
| `smoke`    | `bash tests/smoke.sh`                           | 0 failed |
| `mutation` | `python3 scripts/mutation_gate.py --run --min 80` | **80%** of `boost_cli/core` mutants killed |

The `eval` gate is the Tier 1 retrieval-quality check: it runs boost's RAG
engines over the golden set (`tests/eval/golden.jsonl`) and floors BM25
recall@k. The golden set grades real catalog items **by name**, so it needs a
corpus: `scripts/ensure_eval_corpus.sh` first taps the pinned repo list in
`tests/eval/taps.txt` (the minimal set covering all golden targets — `boost tap
--defaults` is NOT enough, it omits every rule/workflow repo). Over that corpus
BM25 recall is 1.000, so the 0.85 floor has wide margin; regression-vs-baseline
is relaxed in the gate (`--regression-eps 1`) so upstream repo drift can't flake
it. Edit `taps.txt` → regenerate `tests/eval/baseline.json`. It runs in CI's
`lint` job (pure-stdlib BM25, no `ANTHROPIC_API_KEY`; needs network to tap). The
opt-in evals stay out of `check` and all degrade cleanly:

- `make eval-ai` / `eval-rec` — key-gated LLM evals (Tier 2a rerank / 2b recommend).
- `make eval-stats` — Tier 1b `ranx` paired-t-test between engines (`--stats`).
- `make eval-explain` — Tier 2c `ragas` faithfulness for `boost explain`; needs
  the `[eval]` extra **and** a judge key (`OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`
  with `langchain-anthropic`) plus boost AI to generate the explanations.

The `[eval]` extra (`pip install -e '.[eval]'`) carries `ranx` + `ragas`; nothing
in it is ever imported by the CLI or the required gate. It pins the langchain 0.3
stack because ragas 0.2.x breaks against langchain ≥1.0 — an isolated cost of the
ragas dependency.

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
  `workflow` (commands/agents/workflows Markdown). **All three install**, and
  each honors `scope`: `store.install` dispatches to `_install_rule` /
  `_install_workflow` and only raises for a kind outside those three. They land
  in different places, which is the part to get right — a skill is copied into
  the canonical store and symlinked out, a rule is materialised into each
  agent's context file (`rules.CONTEXT_FILES`, e.g. `~/.claude/CLAUDE.md`), and
  a workflow is rendered per agent (TOML for Gemini, see
  `workflows.TOML_COMMAND_AGENTS`). Installing a rule therefore edits a file the
  user reads every session — treat it as more invasive than a skill, not less.

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
the intended "already claimed" signal, first-to-merge wins.

Both boards are data-driven: `docs/roadmap.html` from `board: code` items and
`docs/design-roadmap.html` from `board: design` items (track/impact/wow, rendered
into the per-track sections; the filter JS and counters are computed). Same rule
for both — edit items, run `build_roadmap.py`, never touch the HTML by hand.

## Architecture

**CLI dispatch.** `boost_cli/cli.py` holds `COMMANDS`, the single
source-of-truth list of `(name, group, module, summary)` for all 78 commands.
Each command is implemented as `def cmd_<name_with_underscores>(argv) -> int`
inside `boost_cli/commands/<module>.py`, and `_dispatch` imports that module
lazily on invocation — so `boost --help` stays instant and command modules are
decoupled from each other. To add a command: add a row to `COMMANDS`, add the
`cmd_*` function to the named module, and it's live. `docs/commands.html` is
**generated** from `COMMANDS` by `scripts/build_command_reference.py`, so a new
row means regenerating it (`make generate`) or the `--check` gate fails.

**commands/ vs core/.** `boost_cli/commands/` is thin CLI glue — argument
parsing, output formatting, calling into `core/`. `boost_cli/core/` is the
actual engine (catalog scanning, install/link logic, the lock file, registries,
search) and is what the mutation gate targets — put behavior there, not in
the command layer, so it's covered by both the unit suite and mutation
testing.

**Storage layout**, all resolved at call time from `$HOME` (or `$BOOST_HOME`)
in `boost_cli/core/paths.py`, which is what makes `HOME=<tempdir>` sandboxing
work in tests and the dev loop:

```text
~/.boost/repos/     shallow git clones of tapped registries
~/.boost/cache/     JSON catalogs built from SKILL.md/rule/workflow frontmatter
~/.boost/logs/      rotating diagnostic log + crash reports
~/.boost/state/     pins, tags, policy, profiles, pulse feed, snapshots
~/.boost/config.json
~/.agents/skills/                canonical store — single source of truth for installed skills
~/.agents/skills/.skill-lock.json   v3 lock file
~/.claude/skills/  ~/.windsurf/skills/  ~/.cursor/skills/   symlinked out from the canonical store
~/.gemini/                       rules (GEMINI.md) + workflows only — see below
```

**Four agent targets, but only three get symlinks.** Gemini CLI implements the
Agent Skills standard and discovers `~/.agents/skills` — the canonical store —
*directly*, so it is configured with `links_skills: false`. Linking into
`~/.gemini/skills` too would put one skill in two of its discovery tiers, where
the `.agents` alias out-ranks whatever we linked, costing the user a "Skill
conflict detected" line per skill per session and buying nothing. Consequences
for code you write:

- Iterate `agents.linking_agents()` for anything symlink-shaped (link, unlink,
  stale-link sweeps, coverage counts). `agents.enabled_agents()` is still right
  for rules and workflows, which materialize into `~/.gemini/` like any other
  agent's dotdir. `agents.native_store_agents()` is the complement, for reporting.
- Per-agent *formats* differ and are pure functions in `core/`: `rules.CONTEXT_FILES`
  maps an agent with no rules dir to its context file (`claude-code` → CLAUDE.md /
  CLAUDE.local.md, `gemini` → GEMINI.md for both scopes), and
  `workflows.TOML_COMMAND_AGENTS` marks agents whose slash commands are TOML.
  Gemini's `commands/` slot is `.toml` (`workflows.render_gemini_command`); its
  `agents/` slot stays verbatim Markdown. Getting that backwards produces a file
  the agent silently never loads.
- `core/mcphost.py` holds the per-host `mcp add`/`remove` grammar. Claude and
  Gemini disagree on name position, the `--` separator, and whether unregister
  needs an explicit scope — all three verified against the real CLIs and pinned
  by `tests/unit/test_mcphost.py`. Don't "simplify" them into one shape.

`core/catalog.scan_dir` walks a tap's clone and classifies each file into one
of the three item kinds (see Non-obvious rules above); `core/store.py` owns
install, uninstall and sync — copying into the canonical store, symlinking into
each agent's skills dir, and updating the lock file.

**Search has two engines**, both in `core/`: `rag.py` is the always-on,
zero-dependency BM25 engine (full-content index, auto-builds on first
search — this is what the required `eval` gate floors at recall@k ≥ 0.85).
`dense.py` is optional dense/vector retrieval behind the `[rag]` extra plus
an embeddings key (`VOYAGE_API_KEY`/`OPENAI_API_KEY`); it's used when both
are present and falls back to BM25 otherwise. `core/ai.py` wraps the
opt-in LLM-assisted paths (`search --smart`, `explain`, `distill`, `infer`,
`absorb`, `evolve`, `simulate`, …), shelling out to the `claude` CLI or
`ANTHROPIC_API_KEY` when available and degrading to heuristics when not.

## Layout

- `boost_cli/data/` — shipped catalog data (generated)   · `scripts/` — build/gate tooling
- `tests/unit`, `tests/functional`, `tests/smoke.sh` — the three test tiers
- `docs/` — `index.html` (visual guide), `commands.html` (every flag, generated), `DEBUGGING.md`; `roadmap.html` is generated from `docs/roadmap/items/*.md` (see above)
