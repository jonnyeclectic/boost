# boost — a package manager for AI coding skills

[![CI](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml/badge.svg)](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jonnyeclectic/boost)](https://github.com/jonnyeclectic/boost/releases/latest)
[![Python 3.9–3.14](https://img.shields.io/badge/python-3.9%E2%80%933.14-blue)](https://github.com/jonnyeclectic/boost/blob/main/.github/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fjonnyeclectic%2Fboost%2Fbadges%2Fcoverage.json)](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml)
[![Mutation score](https://img.shields.io/badge/mutation_score-%E2%89%A580%25_killed-blueviolet)](https://github.com/jonnyeclectic/boost/blob/main/scripts/mutation_gate.py)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/jonnyeclectic/boost)](LICENSE)

**boost** is a CLI that finds, installs, and keeps track of AI coding skills
pulled from GitHub-hosted registries, then hooks them straight into
**Claude Code, Windsurf, and Cursor** in one pass. Instead of hand-copying
skill files into three different agent folders and hoping you remember to
update all of them, you run one command.

<p align="center">
  <img src="docs/demo.gif" alt="boost demo: tap a registry, search for a skill, install it into every agent, then run doctor" width="820">
  <br>
  <sub><em>tap a registry → search → install into every agent → doctor — one flow</em></sub>
</p>

## Roadmap

boost is built in the open. Two living boards — generated from
`docs/roadmap/items/*.md` — track what's shipped, in flight, and planned:

- **[Code roadmap](https://jonnyeclectic.github.io/boost/docs/roadmap.html)** — engine, correctness, and tooling work
- **[Design roadmap](https://jonnyeclectic.github.io/boost/docs/design-roadmap.html)** — the Visual Guide and docsite aesthetics

Both are reachable from the [Visual Guide](https://jonnyeclectic.github.io/boost/) nav.

## What's a "skill," exactly?

A **skill** is just a `SKILL.md` file — Markdown plus a bit of YAML up top —
that gives an AI agent a repeatable capability: a workflow to follow, a set
of house rules, or some domain knowledge it wouldn't otherwise have. Agents
like Claude Code pick these up automatically out of `~/.claude/skills/`.

Where it gets tedious is everything around that file: tracking down good
skills, wiring each one into every agent you use, keeping versions in sync,
and handing them off to teammates. That's the part boost takes over —
package-manager mechanics for skills, in the same spirit as Homebrew for
Mac binaries or npm for JS packages.

## Install

Needs Python 3.9+ and `git`.

```bash
pipx install boost-skill-cli        # or: pip install boost-skill-cli
boost --version
boost tap --defaults          # pull in the 5 starter registries
```

The default install is **zero-dependency** (pure stdlib). `boost search` and the
`boost_search` MCP tool rank results with a built-in full-content BM25 engine
(run `boost reindex` once to build the index). For optional **dense semantic
search**, install the `[rag]` extra and set an embeddings key — retrieval then
embeds every skill and ranks by vector similarity, falling back to BM25 whenever
the extra or key is absent:

```bash
pip install "boost-skill-cli[rag]"            # adds the sqlite-vec vector store
export VOYAGE_API_KEY=...                      # or OPENAI_API_KEY
boost reindex --dense                          # embed chunks into the vector store
```

Want the whole ecosystem instead of the starter set? boost ships a **curated
registry catalog** — 100+ classified GitHub registries of skills, Cursor/Windsurf
**rules**, and Claude Code **workflows** (slash commands & subagents),
collectively indexing thousands of items. Categories include a curated
**`rag`** set — official Weaviate, Pinecone, and DSPy skill libraries plus
Graph-RAG and agentic-RAG toolkits for building retrieval pipelines:

```bash
boost tap --catalog --dry-run                 # browse the classified catalog
boost tap --catalog --type skill --limit 20   # tap the 20 biggest skill packs
boost tap --catalog --type rule               # every rules registry
boost tap --catalog --category rag            # RAG / vector-search skill packs
boost tap --catalog --category security       # filter by category
```

boost indexes three item kinds out of the same registries: `SKILL.md` **skills**,
`.mdc`/`.cursorrules`/`.windsurfrules` **rules**, and command/agent **workflows**
(Markdown under `commands/`·`agents/`·`workflows/`, or carrying subagent
frontmatter). Rules and workflows are searchable today; only skills install.

Or run it straight from a checkout — the runtime is stdlib-only, so there's
nothing to install beyond the shim:

```bash
git clone https://github.com/jonnyeclectic/boost ~/.boost-src
ln -s ~/.boost-src/boost ~/bin/boost        # anywhere on PATH works
```

## Under the hood

boost pulls down registries, indexes them into a local cache, drops
installed skills into one canonical store, and then symlinks them out to
whichever agents you've got — all of it tracked in a lock file so state
stays reproducible.

```
GitHub registries  ──boost update──▶  ~/.boost/repos/    (shallow clones)
                                     ~/.boost/cache/    (JSON catalogs)
                   ──boost install─▶  ~/.agents/skills/ (canonical store)
                                     .skill-lock.json  (v3 lock file)
                   ────symlinks───▶  ~/.claude/skills/  ~/.windsurf/skills/  ~/.cursor/skills/
```

## The usual workflow

```bash
boost search jira          # look across every tapped registry (AI-ranked when available)
boost install my-jira      # copy, link, lock — with a quality score attached
boost doctor               # sanity check: broken links, lock drift, stale taps

# hand the whole setup to a team:
boost bundle dump > Boostfile     # everyone else runs: boost bundle install
```

## 75 commands, organized into 8 groups

`boost --help` prints the full grouped command list; for a visual tour see
[`docs/overview.html`](docs/overview.html).

| Group | Commands |
|---|---|
| **Package Management** | install · uninstall · sync · update · reinstall · bundle · import · migrate · pin · unpin · snapshot · export |
| **Discovery & Search** | search · reindex · discover · recommend · browse · index · trending · stats · count |
| **Skill Information** | list · info · cat · edit · preview · explain · log · home · deps · tag |
| **Registry (Taps)** | tap · untap · taps · outdated |
| **Intelligence** | distill · simulate · infer · absorb · evolve · context · focus · impact |
| **Quality & Health** | doctor · lint · audit · verify · drift · test · fingerprint · quarantine · decay · heal · conflict · changelog · attest · health |
| **Configuration** | config · clean · create · policy · onboard · completions · schedule · serve · mcp · hooks · bmad · self-update |
| **Team & Collaboration** | cohort · profile · protocol · pulse · replay · who |

The AI-assisted commands (`search --smart`, `explain`, `distill`, `infer`,
`absorb`, `evolve`, `simulate`, …) call out to the `claude` CLI when it's
available on your PATH (or `ANTHROPIC_API_KEY` is set), and fall back to
plain heuristics when it isn't — so the tool still works without an API key,
just less cleverly.

## Claude Code hooks & the BMAD Method

`boost hooks` manages Claude Code hooks in `settings.json` at either scope —
`--scope project` (`./.claude/settings.json`) or `--scope global`
(`~/.claude/settings.json`). boost only ever touches hooks it created (tagged
with a `# boost:<name>` marker in the command), never your own, and snapshots
the prior file before each write.

```bash
boost hooks add SessionStart -c 'echo hello' -n greet --scope project
boost hooks list
boost hooks remove -n greet --scope project
```

`boost bmad` installs and manages the [BMAD Method](https://bmadcode.com/)
(agentic Analyst / PM / Architect / Dev / QA personas + workflows) as a
scope-aware, toggleable startup experience. Provisioning is delegated to the
canonical `npx bmad-method install` (needs Node.js 20.12+); boost owns scope,
the startup toggle, and teardown.

```bash
boost bmad install --scope project   # skills + per-project _bmad/ runtime
boost bmad install --scope global    # skills into ~/.claude/skills for every session
boost bmad init                      # add the _bmad/ runtime to the current repo
boost bmad startup on                # inject light BMAD orientation on session start
boost bmad startup off               # stop injecting it (skills stay installed)
boost bmad disable / enable          # quarantine / restore skills (recoverable)
boost bmad uninstall                 # delete skills + _bmad/ for a scope
boost bmad doctor                    # what's installed where
```

When startup is on, a `SessionStart` hook runs `boost bmad orient`, which prints
a short orientation into the session only while the toggle is enabled. That
orientation sets a **default bias**: build/fix/change/refactor requests go
straight to the `bmad-quick-dev` skill (clarify → plan → implement → review),
skipping the full brief → PRD → architecture ceremony unless you ask for full
planning. Global installs stage the installer in a temp dir and copy only the
`bmad-*` skills, so `$HOME` never gets a stray `_bmad/` — the workflow runtime
stays per-project.

## The boost style

The visual identity behind the docs and demos ships as a small, dependency-free
design system in [`style/`](style/) — the *Aurora living-glass* look: a
cyan → violet → pink triad on a near-black ground, an ambient aurora that drifts
behind the page, and glass cards that light up under the cursor. Drop
[`style/boost.css`](style/boost.css) (and the optional
[`style/boost.js`](style/boost.js)) into any static page; see
[`style/demo.html`](style/demo.html) for the whole system on one page and
[`style/README.md`](style/README.md) for the tokens and class reference.

The same palette runs in the **terminal**. boost renders in 24-bit Aurora color
where the terminal advertises it (`COLORTERM=truecolor`), degrading cleanly to
16-color and then to plain text — so the gradient `boost` wordmark, framed
result cards, search relevance meters, and the green `● healthy` doctor verdict
all speak the same design system as the web (the CLI palette is even
[test-locked](tests/unit/test_token_parity.py) to `style/boost.css`, so the two
can't drift). Color follows the [NO_COLOR](https://no-color.org) convention plus
a `BOOST_COLOR` override — set `BOOST_COLOR=never` to force plain output (handy
for logs and pipes) or `BOOST_COLOR=always` to keep color through a pipe.

## Working on boost

```bash
# everything runs under a disposable HOME, so nothing touches your real setup:
export HOME=/tmp/boost-sandbox && mkdir -p $HOME
python3 tests/make_fixture.py /tmp/fixture-tap
./boost tap /tmp/fixture-tap
./boost install brainstorming
./boost doctor
```

Standard-library Python only — no third-party runtime dependencies. Every
path under `~/.boost` and `~/.agents/skills` is resolved from `$HOME` at
call time, which is what makes the sandboxing above possible.

When something misbehaves, boost keeps a rotating diagnostic log at
`~/.boost/logs/boost.log` and writes a full crash report on any unexpected
error. Turn up detail with `boost --verbose <cmd>` or `boost --debug <cmd>`,
read the trail with `boost log --diagnostics`, and see
[`docs/DEBUGGING.md`](docs/DEBUGGING.md) for log levels, env vars, crash
reports, and the free services that monitor the project.

## Test suite

Three layers, all enforced (`make check` runs the full set; CI runs the same thing):

| Layer | What it does | Gate |
|---|---|---|
| `make test` | pytest across `tests/unit/` (every core module) and `tests/functional/` (drives all 72 commands in-process against sandboxed homes) | **≥80% line coverage** of `boost_cli` (`fail_under` in pyproject.toml) |
| `make smoke` | `tests/smoke.sh` — 152 checks run through the actual `./boost` shim (`--online` also hits real registries) | all pass |
| `make mutation` | [mutmut] mutates `boost_cli/core` (~2,600 mutants) and reruns the unit suite against each one | **≥80% killed** (`scripts/mutation_gate.py`) |

Dev setup: `make venv` (pulls in pytest, coverage, mutmut — the shipped
runtime itself stays dependency-free). Every test run uses a throwaway
`$HOME`, so your actual agent configs are never at risk.

[mutmut]: https://mutmut.readthedocs.io/
