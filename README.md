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

![boost demo](docs/demo.gif)

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

Want the whole ecosystem instead of the starter set? boost ships a **curated
registry catalog** — 90+ classified GitHub registries of skills, Cursor/Windsurf
**rules**, and Claude Code **workflows** (slash commands & subagents),
collectively indexing thousands of items:

```bash
boost tap --catalog --dry-run                 # browse the classified catalog
boost tap --catalog --type skill --limit 20   # tap the 20 biggest skill packs
boost tap --catalog --type rule               # every rules registry
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

## 72 commands, organized into 8 groups

`boost --help` prints the full grouped command list; for a visual tour see
[`docs/overview.html`](docs/overview.html).

| Group | Commands |
|---|---|
| **Package Management** | install · uninstall · sync · update · reinstall · bundle · import · migrate · pin · unpin · snapshot · export |
| **Discovery & Search** | search · discover · recommend · browse · index · trending · stats · count |
| **Skill Information** | list · info · cat · edit · preview · explain · log · home · deps · tag |
| **Registry (Taps)** | tap · untap · taps · outdated |
| **Intelligence** | distill · simulate · infer · absorb · evolve · context · focus · impact |
| **Quality & Health** | doctor · lint · audit · verify · drift · test · fingerprint · quarantine · decay · heal · conflict · changelog · attest · health |
| **Configuration** | config · clean · create · policy · onboard · completions · schedule · serve · mcp · self-update |
| **Team & Collaboration** | cohort · profile · protocol · pulse · replay · who |

The AI-assisted commands (`search --smart`, `explain`, `distill`, `infer`,
`absorb`, `evolve`, `simulate`, …) call out to the `claude` CLI when it's
available on your PATH (or `ANTHROPIC_API_KEY` is set), and fall back to
plain heuristics when it isn't — so the tool still works without an API key,
just less cleverly.

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
