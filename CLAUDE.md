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
make test                                      # unit + functional with 90% coverage gate
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
| `eval`     | `ensure_eval_corpus.sh` + `eval_retrieval.py --build -k 10` with four floors | BM25 recall@k **≥ 0.78**, hit@1 ≥ 0.40, MRR ≥ 0.52, nDCG@k ≥ 0.58 |
| `test`     | `pytest tests/unit tests/functional --cov`     | **90%** coverage (`fail_under = 90`, `branch = true`) |
| `smoke`    | `bash tests/smoke.sh`                           | 0 failed |
| `mutation` | `python3 scripts/mutation_gate.py --run --min 80` | **80%** of `boost_cli/core` mutants killed |

The `eval` gate is the Tier 1 retrieval-quality check: it runs boost's RAG
engines over the golden set (`tests/eval/golden.jsonl`) and floors **four**
metrics on BM25 — recall@k, hit@1, MRR and nDCG@k. Flooring recall alone was a
hole rather than a simplification: a ranker that finds the right answer every
time and never ranks it first scores recall@10 1.000 with hit@1 0.000, and
passed. The golden set grades real catalog items **by name**, so it needs a
corpus: `scripts/ensure_eval_corpus.sh` first taps the pinned repo list in
`tests/eval/taps.txt` (the minimal set covering all golden targets — `boost tap
--defaults` is NOT enough, it omits every rule/workflow repo). The list is
**twenty** repos: the first six cover every golden target, the rest exist so the
corpus is a realistic size. That matters more than it sounds — over the six
alone (743 entries) BM25 scores 0.978 / 0.791 / 0.854 / 0.882, and over the
twenty (10,152) it scores **0.852 / 0.473 / 0.605 / 0.657** on the same golden
set, so three of the four old floors fail once the corpus stops being tiny.

**The ranked list de-duplicates on the content hash, not the name.** A grade key
decides both relevance and identity, and keying identity on the name collapsed
13 different skills called `code-reviewer` into one rank slot — crediting the
ranker with a compression that existed only in the scoring code, and worth about
one query of recall@10. That is where the old "recall is 1.000" folklore came
from; the six-repo corpus measures 0.978 once mirrors collapse and homonyms do
not. Relevance is still decided by name (or by content class when a golden row
pins an `exemplar`), so the sets can migrate a row at a time.

Each floor sits ~10% under its measured value — loose enough that upstream drift
can't flake the build, tight enough to catch a collapse. Regression-vs-baseline
stays relaxed (`--regression-eps 1`), so the absolute floors are the real gate.

**Every row of `taps.txt` pins a commit SHA**, and `scripts/eval_corpus.py`
checks each clone out at it — the corpus is 10,152 entries, of which one
third-party repo is 6,309 (62%), so an unpinned list left a required check
hostage to someone else's push. CI and `make eval` must invoke the gate with
identical floors; `tests/unit/test_eval_corpus.py` fails the build if they
diverge, which they had (CI floored recall alone at 0.85 against a measured
0.863 — a buffer of 1.15 queries out of 91 — and applied none of the other
three). Moving a pin means regenerating the baseline; the file says how.

**Baselines are keyed by query set** (`name@content-digest`), so one file holds
both `golden.jsonl` and `golden-natural.jsonl` without either overwriting the
other. Before that, running the natural-language set printed eight confident
"REGRESSION vs baseline" lines that were only the gap between two different
question sets. Add `--floor NAME=VALUE` (repeatable) to gate any metric; a
misspelled metric name is a hard error rather than a silently skipped floor.
Edit `taps.txt` → regenerate `tests/eval/baseline.json`. It runs in CI's
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
- **`est_items` is measured, and `len(scan_dir(repo))` is not the measurement.**
  Run `python3 scripts/measure_registry.py <clone>`; it hashes each item's body
  with the frontmatter dropped and agent dotdir tokens normalized, so one skill
  rendered into `.claude/`, `.cursor/`, `.gemini/`, … counts once. Registries
  increasingly ship a copy per agent: a raw walk of `pbakaus/impeccable` finds
  40 items for the 9 it has, and `Owl-Listener/ai-design-skills` shipped as 80
  for years because `claude-plugin/<pack>/commands/x.md` and
  `commands/<pack>/x.md` were counted as two commands.
  `measure_registry.py --self-check ~/.boost/repos` re-derives committed counts
  from local clones, so the convention stays falsifiable.
- **Category comes from the names of the items a repo ships, not its README or
  its own name.** `bergside/awesome-design-skills` reads like an index and is a
  67-item visual-style corpus (`brutalism`, `claymorphism`, `bento`);
  `Owl-Listener/ai-design-skills` reads like design and is prompt/agent design
  (`chain-of-thought-design`, `guardrail-design`), so it is `ai`, not `ui`.
  `tests/unit/test_registry_categories.py::TestDesignDomain` pins both
  directions.
- **A tap clone holds Markdown and nothing else.** Taps clone
  `--filter=blob:none --sparse` with a cone covering exactly what
  `catalog.scan_dir` opens (`gitutil.SPARSE_PATTERNS`, pinned against catalog's
  own constants by `tests/unit/test_gitutil_sparse.py` — `gitutil` can't
  import `catalog`, `catalog` imports `gitutil`). 458 taps held 12 GB to index
  1.9 GB of Markdown; `Shopify/agent-skills` was 611 MB for its 30 SKILL.md
  files and is 11 MB under the cone, with a byte-identical catalog. So
  **anything reading a tap's real files must go through
  `store.source_dir_for`**, which calls
  `gitutil.materialize` first — a skill's own `scripts/`/`assets/` sit outside
  the cone, and `_copy_skill` is a `copytree` that would copy the half of the
  directory that exists and report success. Use `sparse-checkout add`, never
  `set`: `set` replaces the pattern list and un-fetches every skill materialized
  before it. `boost import` clones `sparse=False` — it reads the whole repo.
  `boost compact` narrows clones that predate this (offline; measured 177 MB →
  93 MB), and must `update-index --refresh` first, because git silently declines
  to remove a path whose stat data looks dirty and otherwise reports success
  having changed nothing.
- **Tapping many registries goes through `registry.add_many`, and the reason is
  the config file.** `add` ends in `config.load()` -> append -> `config.save()`,
  which is read-modify-write on one JSON file: run it from N threads and taps
  vanish at random. `add_many` clones in a `ThreadPoolExecutor` and writes the
  config **once**, on one thread, after every clone has finished
  (`tests/unit/test_registry_parallel.py` asserts the single write and the
  concurrency separately). It is worth it because a clone is *latency*, not
  bandwidth or CPU: ~1.6 s whether one runs or twelve, so `boost tap --catalog`
  was 463 x 1.6 s = 13 minutes of waiting and is now **2 min 10 s** for the same
  463 registries. Scanning stays serial on the caller's thread — it is 3 ms per
  registry and writes a per-tap cache file, so parallelising it buys nothing and
  scrambles output order. Cleanup after a failed clone must tolerate a
  directory that was never created: `util.rmtree`'s read-only retry hook calls
  `chmod` on the missing path and raises `FileNotFoundError`, which out of a worker thread
  turns one 404 into a crashed catalog tap.

- **`~/.boost/cache/` holds boost's own indexes, not just tap catalogs.**
  `paths.INTERNAL_CACHE_FILES` names them. `boost clean` sweeps `cache/*.json`
  whose stem is not a configured tap, which described `rag_index.json` and
  `discovery.json` perfectly — it deleted the BM25 index on every run, and
  rebuilding it re-parses every tap catalog on the machine (~71k items). A new
  derived artifact goes in that set or `tests/unit/test_clean_internal_cache.py`
  fails.
- **Sandbox tests via env, and export separately.** boost state lives under
  `HOME`/`BOOST_HOME`; tests point them at a tempdir. In zsh, one-line chains
  like `export A=$(...) B=$A/x` leave `B` broken — use separate `export`
  statements.
- **Versioning is setuptools-scm from git tags.** **Only `vX.Y.Z` tags count**, and
  two settings say so: `git_describe_command`'s `--match v[0-9]*` decides which
  tag is *found* and `tag_regex` decides how it is *parsed*. Both are load-
  bearing since the repo gained a deliberate non-version tag — `shards-latest`,
  the rolling release hosting the vector shards. At defaults, `git describe`
  returned `shards-latest-1-g82c3e6a`, the build called itself
  `vshards-latest-…`, and `boost self-update` then reported "already up to
  date" against a newer PyPI release, because it compares version tuples and
  that string parses as none. A silent wrong answer in the command whose job is
  to detect being behind. There is no `__version__`
  constant and `boost_cli/_version.py` is generated + gitignored. Don't hardcode
  or assert exact versions; version tests are shape-only (`^boost \S+$`). The
  publish workflow filename must stay `publish.yml` (PyPI Trusted Publisher
  matches on it).
- **Target Python ≥ 3.12** (`requires-python = ">=3.12"`). Structural pattern
  matching and runtime `X | Y` unions are now legal. The `typing.List` → `list`
  sweep is **done**: UP006/UP035/UP045 are selected, not ignored, and report zero
  violations. (This entry described the sweep as deferred long after it landed —
  measure before trusting a "not done yet" note.) `UP031` printf-formatting *is*
  still ignored, and deliberately: it is an unsafe fix over ~1,000 call sites in
  `boost_cli` alone. Write new code in the modern style; don't bulk-rewrite old
  code in an unrelated PR.
- **A catalog entry has two identities, and they are not interchangeable.**
  *Row* identity is `(tap, skill_md)` (`rag.entry_key`) — which file, in which
  tap. *Content* identity is `entry["content"]`, a truncated sha256 of
  `name + "\n" + description + "\n" + body` stamped by `catalog._content_digest`
  at scan time. Use the row key to address a row and the digest to ask whether
  two rows are the same thing. The digest must stay byte-identical to what
  `rag.read_body` assembles — `tests/unit/test_content_identity.py` pins the
  parity, because a digest that drifts keeps *looking* right while clustering
  nothing. Name-based keys are wrong at both layers: over 60,047 real entries,
  hashing the body alone merges 259 clusters spanning different names, and
  name+description over-collapses 3,383 clusters of genuinely different prose.
  Consumers must degrade cleanly when `content` is absent (a cache written
  before `CACHE_FORMAT`, or a synthesised entry) — and must never treat two
  absences as a match.
- **The tap cache is versioned; bump `catalog.CACHE_FORMAT` to backfill.** It is
  how a new entry field reaches 460 caches on a real machine without a re-tap:
  `load_tap` rescans a stale cache *when the clone is still there*, and serves
  the stale entries as-is when it is not. Never make a stale cache an error —
  that trades a missing field for a missing catalogue.
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
- **A long line is either chrome or data, and only chrome may be wrapped.**
  `out.wrap()` folds prose to the pane, and the emitters take it opt-in —
  `warn`/`info`/`dim`/`kv` accept `wrap=True` and each pays for its own prefix,
  so continuations align under the message rather than folding to column zero.
  It is opt-in because always-on wrapping would fold the lines that must stay
  long: `pulse`'s `source=` paths and `fingerprint`'s 64-character hash are the
  information the line exists to carry, and a hash split across two lines
  cannot be compared by eye. **A backtick span is one atomic token**, spaces
  and all — `doctor` and `search` both interpolate `dense.fix_hint()`, whose
  answers end in `pip install 'boost-skill-cli[rag]'`, and a wrap that splits
  that hands the user a command which does not run. A token wider than the pane
  overflows whole rather than breaking. Wrap *before* adding color: `out.role`
  brackets its argument with a start code and a reset, so coloring first and
  splitting after leaves line one unterminated and line two plain. And
  budget the emitter's own indent — wrapping to the full `term_width()` and
  then letting `out.info` add two spaces is what put `boost search`'s hint one
  column past the pane it had just been fitted to.

- **A new source file needs the licence header, and a new prose file needs
  adding to the vale list.** Every `.py`/`.sh` under `boost_cli`,
  `boost_langchain`, `evals`, `scripts`, `tests` plus `./boost` and
  `noxfile.py` opens with `# Copyright the boost contributors.` and
  `# SPDX-License-Identifier: GPL-3.0-only`. Run
  `python3 scripts/add_spdx_headers.py` (idempotent) — the file list and the
  expression live there, so changing `-only` to `-or-later` is one edit rather
  than 314. Separately, `prose-lint.yml` names the Markdown files vale checks
  **explicitly**: a new doc that is not added to that list is never linted, and
  `make lint` will not tell you.

- **Sub-actions of one action repo move in lockstep.** `github/codeql-action/{init,
  analyze,upload-sarif}` and `actions/cache{,/save,/restore}` are each *one repo at
  one commit*, but Dependabot tracks one `uses:` path as one dependency and raises a
  PR per sub-action — none of which can be merged on its own (`init` stamps its
  version into the config and `analyze` rejects another release's). `.github/
  dependabot.yml` groups them so a release arrives as one PR;
  `tests/unit/test_action_pin_lockstep.py` fails the build if a split lands anyway,
  and is parametrised over the families the workflows use, so a new multi-path
  action must be grouped before it passes. Bump all of a family's pins together, to
  the **peeled** commit SHA (`git ls-remote … 'refs/tags/vX.Y.Z^{}'`) or zizmor's
  `ref-version-mismatch` fails the PR.

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
source-of-truth list of `(name, group, module, summary)` for all 81 commands.
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
~/.boost/repos/     blobless, sparse git clones of tapped registries
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
- **Boost not linking there does not mean nothing else does**, and the warning
  costs the user the same either way. `store.duplicate_discovery()` walks
  `native_store_agents()` for entries that resolve back into the canonical
  store — one skill in two of that agent's discovery tiers, whoever wrote it.
  On a real machine 24 of the 25 entries in `~/.gemini/skills` led to
  `~/.claude/skills` directories boost does not manage, and one resolved into
  the store, so the test is **topology, not ownership**: a sweep of "boost's
  stale links" would have deleted two dozen files belonging to another tool.
  `boost doctor` counts each hit as an issue; `boost heal` names them and
  removes nothing; `boost heal --prune-duplicates` removes them, re-checking at
  the point of deletion that the entry is still a symlink still resolving into
  the store. A real directory is never touched.
- **`points_into_store` and `resolves_into_store` answer different questions.**
  The first reads one `readlink()` because it judges *broken* links, where
  there is nothing to resolve. The second follows the whole chain, because the
  live shape is `~/.gemini/skills/x -> ../../.claude/skills/x -> the store` and
  one hop lands in another agent's dir. It resolves **both sides**: on macOS a
  `$HOME` under `/var/folders` resolves to `/private/var/...`, so resolving
  only the target compares a real path against a nominal one and never matches.
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
- **`core/hookhost.py` is the same idea for hooks, and two hosts have them.**
  `boost hooks` writes Claude Code's `~/.claude/settings.json` (the default,
  unchanged) or, behind `--host gemini`, the `~/.gemini/settings.json` that
  Gemini CLI reads;
  `core/claude_settings.py` takes `host=` throughout and asks the table for the
  differences. The `hooks` key and the `{matcher, hooks: [{type, command,
  timeout}]}` block shape are *identical* between them, which is exactly what
  makes the three real differences easy to ship wrong:
  - **`timeout` units.** Claude's is **seconds**; Gemini's is **milliseconds**
    (`DEFAULT_HOOK_TIMEOUT = 6e4`, fed straight to `setTimeout`). Callers pass
    seconds and `hookhost.hook_entry` converts, so boost's `--timeout 10` is ten
    seconds on both. Gemini's own `hooks migrate --from-claude` copies the number
    verbatim, which turns a 10-second Claude hook into a 10-**millisecond**
    Gemini one; don't copy that.
  - **Event names.** Only `SessionStart`, `SessionEnd` and `Notification` are
    spelled alike. `CLAUDE_TO_GEMINI` maps all ten Claude events explicitly and
    `tests/unit/test_hookhost.py` fails if one is missing. `SubagentStop` and
    `SubagentStart` map to **`None`** — Gemini has no sub-agents, so boost
    refuses the hook and says why. (The upstream `EVENT_MAPPING` means to fold
    them into `AfterAgent` but keys `SubAgentStop`, a spelling Claude never
    emits, so `migrate` writes an event Gemini can never fire.)
  - **The `name` field.** Gemini's hook config takes one — it is what
    `/hooks panel` shows and `/hooks enable <name>` targets — and Claude's does
    not. The `# boost:<name>` command marker stays the ownership mechanism for
    both; `name` is added on top for Gemini, never instead.
  A `matcher` is **not** translated: `boost hooks add` is not porting a config,
  so it stays host-native — for a Gemini tool event it is a regular expression
  over *Gemini* tool names like `run_shell_command`, and for a lifecycle event
  it is an exact string. All of this was established against Gemini CLI
  0.57.0's own bundle — the `docs/hooks/` it ships, the `HookEventName` list and
  `EVENT_MAPPING` in the bundled JS, and an observed `migrate` run — and those
  sources are named at the top of `hookhost.py` so the next person can re-check
  them against a newer release.

`core/catalog.scan_dir` walks a tap's clone and classifies each file into one
of the three item kinds (see Non-obvious rules above); `core/store.py` owns
install, uninstall and sync — copying into the canonical store, symlinking into
each agent's skills dir, and updating the lock file.

- **A tap pin lives in `config.json`, and `boost update` is what makes it real.**
  `boost tap --at <sha>` used to check a commit out and record nothing, so the
  next `boost update` reset the clone to the default branch — measured on a
  two-commit fixture: tapped at `fb61736`, updated, `6206d22`. That silently
  invalidates any shard imported for the old commit (stale vectors, still
  present, no error), which is also the reason **search must never refresh taps
  in the background**: `_hint_stale_taps` reads one mtime
  (`paths.tap_refresh_marker`, stamped by `registry.update`) and prints one
  line rather than fetching. `registry.update` skips a pinned tap; `--force`
  moves it *and* drops the pin, because deciding to move a tap is deciding to
  stop holding it still. After any tap actually moves, `pkg._resync_vectors`
  asks the manifest whether a shard exists for the new commit — importing it
  costs a download instead of an hour of CPU — and says plainly when one does
  not.

- **The shard matrix is packed, not sliced, and 256 is a hard ceiling.**
  GitHub runs at most 256 matrix jobs per workflow, so `shards.yml` cannot take
  one job per registry once the scope is the 463-registry catalogue — the run
  fails before a job starts. `scripts/shard_plan.py` bin-packs by the measured
  `est_items` (longest-processing-time-first), which matters because cost is
  uneven: the largest catalogued registry is 880 items against a median of 30,
  so slicing puts several giants in one job while others idle, against a
  6-hour per-job ceiling. Packing is deterministic on purpose — a rerun that
  repacked differently would re-embed registries whose shards were already
  published. A matrix entry is a **space-separated list**, split in Python
  inside the job, never by shell word-splitting.

- **A published shard is only importable while three things match, and every
  mismatch is silent if waved through.** `core/shards.py` fetches
  `manifest.json` from a rolling `shards-latest` **prerelease** on this repo —
  prerelease and `--latest=false` deliberately, so release-drafter (which
  resolves the next version from published non-prereleases), the shields badge
  in the README and setuptools-scm's `--match *[0-9]*` all keep ignoring it.
  The manifest carries the embedding *space* once at the top, so
  `shards.incompatible()` can refuse before downloading 129 MB; each row pins
  the registry *commit*, checked in `shards.sync` and again in
  `dense.import_shard`, because a stale shard makes `dense.build` mark that tap
  "reused" forever; and each row's *sha256* is verified over the bytes written.
  A shard URL off the manifest's own host is refused — a manifest names what
  boost downloads, so it must not widen where the download goes. `boost tap
  --at <sha>` exists for the commit rule: `boost quickstart` pins each registry
  to the commit its vectors describe rather than tapping HEAD and hoping.
  **Publish keyless vectors only** — a shard exported from a machine holding
  `VOYAGE_API_KEY` is 1024-d `voyage-4` and can only be imported *or queried*
  by another key-holder; `scripts/publish_shards.py manifest` refuses to
  describe two spaces in one file.

**Search has two engines**, both in `core/`: `rag.py` is the always-on,
zero-dependency BM25 engine (full-content index, auto-builds on first
search — this is what the required `eval` gate floors at recall@k ≥ 0.78).
`dense.py` is optional dense/vector retrieval behind the `[rag]` extra —
**no API key required**: `embed.py` tries Voyage, then OpenAI, then a local
`BAAI/bge-small-en-v1.5` that ships with the extra, so a key is a quality
upgrade rather than the entry fee. When both engines are built, `retrieve_any`
fuses them with reciprocal rank fusion (`rag.rrf_fuse`, `RRF_K = 60`) and
reports `hybrid RRF`; it degrades to whichever single engine is ready, and to
BM25 alone otherwise. `dense.status()` names which of the three links (extra,
backend, built store) is missing, and `dense.fix_hint()` maps that to the one
next action — both `boost doctor` and `boost search` read that same table, so
they can't give contradictory advice.

**The dense store ranks twice, and `vec0` is why.** `sqlite-vec` has no ANN
index: a float32 `MATCH` scores *every* vector in the store, which on a real
750,416-chunk / 1024-d install is 3.08 GB and **28.2 s per query** — it was ~85%
of a 33.9 s `boost search`. So a query runs a coarse pass over
`vec_chunks_bin` (binary-quantized, one bit per dimension — 114 MB, Hamming) and
re-ranks the top `RESCORE_POOL` (2048) on their exact float32 vectors from
`vec_raw`. Measured: **28.2 s → 1.05 s at recall@60 = 1.000** — the same rows in
the same order. Both stages are required: the binary pass alone recovers 0.667
of the true top 60, so deleting the rescore as an "optimization" is a quality
regression, and `tests/unit/test_dense_quantized.py` fails if it goes.
`vec_raw` is an ordinary rowid-keyed table on purpose — `id IN (...)` against a
vec0 table plans as a full scan (256 point lookups measured 3.2 s), so the
rescore would cost more than the thing it replaced.

Consequences for code you write here:

- **`dim` must be a multiple of 8** for `bit[N]`, so `_quantizable()` gates the
  layout and a non-conforming width keeps the old float32 `vec_chunks`. The
  toy 3-d fixtures elsewhere in the suite are what keep that fallback covered;
  `tests/unit/test_dense_quantized.py` uses 8-d.
- **`dense.quantize()` migrates in place and re-embeds nothing** — it re-encodes
  vectors already on disk. It counts rows into `vec_raw` and refuses to drop
  `vec_chunks` unless the copy is complete, because re-embedding 750k chunks is
  a bill, not an inconvenience. `boost reindex --dense` runs it; `boost doctor`
  names a ready-but-unquantized store. **It costs disk**: a plain table pays
  overflow-page overhead on 4 KB blobs that vec0's packed storage does not, so
  the measured trade is **3.40 GB → 3.87 GB (+14%), in 1360 s**, peaking at
  ~2× while both copies coexist. Don't describe it as size-neutral — an earlier
  draft of this section did, from prediction rather than measurement.
- **Embedding reports progress and commits as it goes.** `dense.build` takes
  `on_progress(done, total)` and `_embed_and_store` commits every
  `_COMMIT_EVERY` rows. Both are bug fixes, not polish: a full catalogue is
  tens of thousands of distinct chunks under one fixed spinner label, which a
  user reported as a hang after hours; and every row used to land in a single
  transaction that committed after the last one, so an interrupt threw away the
  whole build. Periodic commits are safe because `build` deletes each changed
  tap's rows *before* re-inserting, so a partial store is replaced rather than
  doubled. The total counts **distinct** texts, not rows — 42.9% of chunks on a
  real install are repeats and are embedded once — so a progress total taken
  from row count would over-report the work.

- **Nothing on the search path may count `chunks`.** `SELECT COUNT(*)` scans the
  `chunks_tap` covering index — 8,419 pages / 34.5 MB, measured 1.94 s — and
  both `ready()` and `status()` did it on every search, the latter only to word
  one muted hint. The total now comes from `meta["chunks"]`, emptiness from a
  `LIMIT 1` probe, and the scan only when `status(count=True)` asks. A store
  that never recorded a total reports `chunks: None`, **not 0**: `fix_hint`
  reads a zero as an unfinished install and would send that user to the one
  remedy that re-embeds everything.

`core/ai.py` wraps the opt-in LLM-assisted paths (`search --smart`, `explain`, `distill`, `infer`,
`absorb`, `evolve`, `simulate`, …), shelling out to the `claude` CLI or
`ANTHROPIC_API_KEY` when available and degrading to heuristics when not.

## Layout

- `boost_cli/data/` — shipped catalog data (generated)   · `scripts/` — build/gate tooling
- `tests/unit`, `tests/functional`, `tests/smoke.sh` — the three test tiers
- `docs/` — `index.html` (visual guide), `commands.html` (every flag, generated), `DEBUGGING.md`; `roadmap.html` is generated from `docs/roadmap/items/*.md` (see above)
BE BRIEF
