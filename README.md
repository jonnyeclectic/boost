# boost — a package manager for AI coding skills

[![CI](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml/badge.svg)](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jonnyeclectic/boost)](https://github.com/jonnyeclectic/boost/releases/latest)
[![Python 3.12–3.14](https://img.shields.io/badge/python-3.12%E2%80%933.14-blue)](https://github.com/jonnyeclectic/boost/blob/main/.github/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fjonnyeclectic%2Fboost%2Fbadges%2Fcoverage.json)](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml)
[![Mutation score](https://img.shields.io/badge/mutation_score-%E2%89%A580%25_killed-blueviolet)](https://github.com/jonnyeclectic/boost/blob/main/scripts/mutation_gate.py)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)](https://github.com/jonnyeclectic/boost/actions/workflows/ci.yml)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14275/badge)](https://www.bestpractices.dev/projects/14275)
[![OpenSSF Baseline](https://www.bestpractices.dev/projects/14275/baseline)](https://www.bestpractices.dev/projects/14275/baseline-2)
[![License](https://img.shields.io/github/license/jonnyeclectic/boost)](LICENSE)

**Homebrew for AI coding skills.** boost finds, installs, and version-tracks
skills from GitHub-hosted registries — and wires each one into **Claude Code,
Windsurf, Cursor, and Gemini CLI** in a single pass.

```bash
pipx install boost-skill-cli
boost tap --defaults          # 7 curated registries: skills, rules, workflows
boost search tdd              # full-content BM25 over every skill
boost install tdd-workflow    # → every agent, version-pinned, one lock file
```

No more copying `SKILL.md` into four agent folders and forgetting which one is
stale. The default install is **zero-dependency** — pure stdlib, no build step.

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

Needs Python 3.12+ and `git`.

```bash
pipx install boost-skill-cli        # or: pip install boost-skill-cli
boost --version
boost tap --defaults          # pull in the 7 starter registries

# upgrading later is `upgrade`, not `install --upgrade` — with a bare package
# name the latter matches the spec you already satisfy and silently does nothing
pipx upgrade boost-skill-cli        # or: pip install --upgrade boost-skill-cli
```

The default install is **zero-dependency** (pure stdlib). `boost search` and the
`boost_search` MCP tool rank results with a built-in full-content BM25 engine —
the index builds automatically on your first search, so BM25 is the default with
no setup (`boost reindex` just forces a rebuild).

### Configuring semantic search

BM25 matches words. It is very good when your query shares vocabulary with the
docs and poor when it doesn't — ask it *"my app is slow"* and it has nothing to
match on. Semantic search ranks by meaning instead, and boost fuses the two so
each covers the other's blind spot.

**No API key is required.** Two steps:

```bash
pip install "boost-skill-cli[rag]"   # vector store + local embedding model
boost reindex --dense                # embed your tapped registries
```

The first search after that downloads a small embedding model once (~133 MB,
sha256-pinned, cached under `~/.boost/cache/models`) and runs it on CPU. Nothing
is sent anywhere.

| | required | what you get |
|---|---|---|
| BM25 | nothing — it is the default | keyword matching, always on |
| `[rag]` extra + `reindex --dense` | no account, no key | meaning-based search, fused with BM25 |
| `VOYAGE_API_KEY` or `OPENAI_API_KEY` | an account | a larger embedding model; same behaviour otherwise |

A key is a **quality upgrade, not an entry fee** — set one and boost prefers it
automatically, re-embedding on the next `reindex --dense`. Every layer degrades
rather than failing: no extra, no key, or no built store each fall back to BM25,
and `boost doctor` reports which engine is actually serving and why.

Want the whole ecosystem instead of the starter set? boost ships a **curated
registry catalog** — 480+ classified GitHub registries of skills, Cursor/Windsurf
**rules**, and Claude Code **workflows** (slash commands & subagents),
collectively indexing ~30,000 scannable items. Every `est_items` is *measured*
from the repo's file tree, not estimated, so `--limit` ranks by real size — and
counted once per item however many agents a repo renders it for, so a pack that
ships a copy in `.claude/`, `.cursor/` and twelve other dotdirs is not credited
with fourteen skills (`scripts/measure_registry.py`).

Seven domains are curated end to end, each tappable on its own:
**`ai`** (RAG, evals, tracing, model serving — official OpenAI, Anthropic,
LangChain, Qdrant, Elastic, MLflow, Langfuse, Arize, W&B, vLLM libraries),
**`architecture`** (DDD, clean architecture, system design, C4/ADR),
**`ui`** (design systems, design taste, accessibility, data visualization,
TUI/dotfiles — including Impeccable, taste-skill and Huashu Design),
**`java`** (Spring Boot, Kotlin/JVM, Quarkus, JetBrains, Camunda, Vaadin),
**`ecommerce`** (Shopify, Magento, WooCommerce, Spree, Bagisto, PrestaShop,
Stripe, Algolia), **`infra`** (Docker, Kubernetes, OpenShift, Helm, GitOps,
networking — plus official Azure, Grafana, Pulumi, Flux, DigitalOcean packs),
and **`marketing`** (marketing, CRM, email campaigns and customer outreach —
20 registries, ~2,400 measured items: cold-email and ABM sequences from
ColdIQ, CRM setup and hygiene for Salesforce/HubSpot/Attio from LeadMagic,
B2B RevOps lead routing, Zapier's GTM cheat codes, plus paid media, SEO/GEO
and lifecycle email):

Smaller categories fill in around them. **`efficiency`** collects the packs whose
items exist to make an agent emit *less* — less code (`ponytail`) or fewer output
tokens (`caveman`). Their `focus` lines describe what the items do and omit the
headline savings on purpose: independent paired benchmarks reproduce roughly a
fifth of what each advertises, with no measured quality loss, so the effects are
real but far smaller than the marketing figure.

```bash
boost tap --catalog --dry-run                 # browse the classified catalog
boost tap --catalog --type skill --limit 20   # tap the 20 biggest skill packs
boost tap --catalog --type rule               # every rules registry
boost tap --catalog --category infra          # Docker/Kubernetes/OpenShift packs
boost tap --catalog --category java           # Spring Boot / Kotlin / JVM packs
boost tap --catalog --category rag            # RAG / vector-search skill packs
boost tap --catalog --category security       # filter by category
```

### Share the catalogue instead of re-tapping it

Tapping is the slowest thing a new install does, and the expensive artifact is
not the valuable one. On a machine with **458 registries** tapped, the shallow
clones are **12 GB** — while the catalogue they produce, the JSON boost actually
searches, is **10.9 MB** gzipped. So hand someone the catalogue:

```bash
boost catalog --export catalogue.tgz    # 458 taps · 59,972 entries · 10.9 MB
boost catalog --show catalogue.tgz      # what is in it, without importing
boost catalog --import catalogue.tgz    # on the other machine
```

Measured on a fresh `HOME`: import takes **0.3 s**, `boost reindex` a further
**3.8 s**, and `boost search` then returns real hits over all 59,972 items with
**zero repositories cloned**. `install` still clones — but only the one registry
the skill you chose actually lives in, instead of all 458 up front.

Bundles carry catalogue JSON and nothing else. The derived indexes are excluded
(they are 3.8 GB of a 3.9 GB cache directory and rebuild in seconds), and
vectors are excluded because they are only valid inside the embedding space that
made them — `boost reindex --export-shard` is the path for those, with the
provenance checks a bundle deliberately does not try to carry. Import **merges**,
so it never silently drops taps the receiving machine already had.

boost indexes three item kinds out of the same registries: `SKILL.md` **skills**,
`.mdc`/`.cursorrules`/`.windsurfrules` **rules**, and command/agent **workflows**
(Markdown under `commands/`·`agents/`·`workflows/`, or carrying subagent
frontmatter). All three install, and they land in different places — a skill is
copied into the canonical store and symlinked out, a rule is materialised into
each agent's context file (`~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`), and a
workflow is rendered per agent. So a rule has no directory to look in:

```bash
boost list --kind rule                # just the rules, and where they landed
boost list --kind workflow            # …and which slot each one fills
```

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

```text
GitHub registries  ──boost update──▶  ~/.boost/repos/    (blobless sparse clones)
                                     ~/.boost/cache/    (JSON catalogs)
                   ──boost install─▶  ~/.agents/skills/ (canonical store)
                                     .skill-lock.json  (v3 lock file)
                   ────symlinks───▶  ~/.claude/skills/  ~/.windsurf/skills/  ~/.cursor/skills/
```

A tap clone holds **only the files boost indexes** — `SKILL.md`, workflow
Markdown, and rule files. Everything else a registry ships (`node_modules`,
binary assets, bundled JS) is neither downloaded nor checked out, because the
catalog is built from Markdown and nothing else. `Shopify/agent-skills` is
611 MB as a normal clone and 11 MB as a tap, and produces an identical catalog.
When a skill you install owns its own `scripts/` or `assets/`, those are fetched
on demand at install time, so nothing is missing from what lands in the store.

If you tapped heavily before this landed, `boost compact` narrows the clones you
already have — offline, no re-clone, no loss of search coverage:

```bash
boost compact --dry-run     # what it would reclaim
boost compact               # narrow every clone in place
boost compact --reclone     # also drop already-downloaded git objects (needs network)
```

Gemini CLI is the one agent that needs no symlink: it implements the
[Agent Skills](https://agentskills.io) standard and discovers `~/.agents/skills`
— boost's canonical store — directly. Linking into `~/.gemini/skills` as well
would put the same skill in two of its discovery tiers, so boost deliberately
doesn't (`agents.gemini.links_skills` is `false`; flip it to `true` if you ever
need the copy). Rules and workflows still materialize under `~/.gemini/`.

### User scope vs project scope

That's the default — **user scope**, the skills you want everywhere. The other
half is the npm `--save` half: skills a *team* agrees on, which belong in the
repo where they can be reviewed in a PR and arrive with a `git clone`.

```bash
boost install code-review --local     # into THIS repo (= --scope project)
boost install code-review             # into your user config (default)
boost list --local                    # just what this repo carries
boost uninstall code-review --local
```

A `--local` install writes **real directories** into the repo's own agent config
and records them in a committable per-repo lock:

```text
<repo>/.claude/skills/<name>/     real copies, not symlinks
<repo>/.cursor/skills/<name>/
<repo>/.boost/skill-lock.json     commit this — it's what teammates clone
```

Real copies, deliberately: a symlink into *your* `~/.agents/skills` is a
dangling pointer on anyone else's machine, so committing one would ship
something that only works on the author's laptop. The two scopes use separate
lock files, so vendoring a skill into a repo never fights with the copy you use
everywhere — and `boost install --local` run from `src/deep/nested` walks up to
the repo root rather than scattering a `.claude/` three directories down.

After a fresh clone, `boost sync` re-materializes anything the project lock
records but the checkout is missing — the lock stores repo-relative paths, so it
works from whatever directory your teammate cloned into. It never deletes a
skill directory boost didn't write, and it won't overwrite a hand-written
`.claude/skills/<name>/` unless you pass `--force`.

`boost update` covers user scope only for now; to refresh a vendored skill use
`boost install <skill> --local --force`.

## The usual workflow

```bash
boost search jira          # look across every tapped registry (AI-ranked when available)
boost install my-jira      # copy, link, lock — with a quality score attached
boost doctor               # sanity check: broken links, lock drift, stale taps

# hand the whole setup to a team:
boost bundle dump > Boostfile     # everyone else runs: boost bundle install
```

### Browsing the catalogue

`boost browse` is a full-screen picker over every tapped item — a filterable
list on the left, the selected item's full detail on the right.

```text
╭─ ●●●  boost browse  ──────────────────────────────────┬──────────────────────╮
│ ❯ co re                                          2/4  │ code-review  v1.0.0  │
│ match (●) all ( ) name ( ) descr ( ) tap              │ ──────────────────── │
│ ↑↓ move  ⇥ select  → detail  ^T scope  ↵ install      │ Review a pull …      │
├───────────────────────────────────────────────────────┤ ● installed          │
│  ★● code-review         [skill] v1.0.0 [acme/quality] │ SOURCE · FRONTMATTER │
╰─ ✓ 1 installed ───────────────────────────────────────┴──────────────────────╯
```

| key | does |
|---|---|
| any character, **including space** | types into the query |
| `↑` `↓` | walk the whole surface: query → match toggles → results |
| `→` `←` | into and out of the detail pane, where `↑`/`↓` scroll it |
| `←` `→` *on the toggle row* | pick what the query matches |
| `⇥` | select (multi-select for a batch install) |
| `^T` | cycle the match toggles without leaving the results |
| `↵` | install — **in place**, without leaving the browser |
| `esc` | quit |

The query splits on spaces and **every** token must match, so `code review`
narrows where `code` alone would not. Selection lives on `⇥` rather than space
for exactly that reason, and `q` stays a character so `quality` is searchable.

`↵` installs without dropping you back to the shell, and the whole surface
reports it: the row's mark cycles `◐` → `●` (or `✗`), the detail pane narrates
with the destination or the reason, and a chip in the bottom rule keeps the
session tally (`✓ 2 installed`) visible even with the pane closed. Installs
queue and run one at a time, because each one rewrites the lock file.

The list is honest at the edges too: badges sit in a right-aligned rail
(dropping least-important-first when narrow, the `×N` copies count last), an
overflowing list gets a scrollbar, a zero-match filter says
`○ no matches for '…'` with the keys that widen it, and the detail pane's
`installs` line states what `↵` will touch **before** it is pressed — for a
rule that is each agent's context file, which is why it earns the line.

**Duplicates are collapsed.** Registries render one skill into `.claude/`,
`.cursor/`, `.gemini/` and a plugin root, so the same thing was listed four
times — on a real 60,047-entry catalogue **22,535 rows (37%) are duplicates**.
Rows whose name *and* description match (or are ≥95% alike) fold into one,
badged `×5`, with the hidden total in the counter and `^D` to show them again.
Identity is the description, never the name: `code-reviewer` appears 75 times
with 42 *different* descriptions, and those are 42 real skills.

## 80 commands, organized into 8 groups

`boost --help` prints the full grouped command list; for a visual tour see
[`docs/index.html`](docs/index.html), and for every flag of every command see
[`docs/commands.html`](docs/commands.html). For a GIF of one flagship command
per group — recorded live with [VHS](https://github.com/charmbracelet/vhs) — see
[`docs/carousel.html`](docs/carousel.html). For how boost is put together
internally — C4 diagrams of the context, containers, engine components and the
install path — see [`docs/architecture/`](docs/architecture/README.md).

| Group | Commands |
|---|---|
| **Package Management** | install · uninstall · sync · update · reinstall · bundle · import · pin · unpin · snapshot · export · adapt · run |
| **Discovery & Search** | search · reindex · discover · recommend · browse · index · trending · stats · count |
| **Skill Information** | list · info · cat · edit · preview · explain · log · home · deps · tag |
| **Registry (Taps)** | tap · untap · taps · outdated · catalog |
| **Intelligence** | chat · distill · simulate · infer · absorb · evolve · context · focus · impact |
| **Quality & Health** | doctor · lint · audit · verify · drift · test · fingerprint · quarantine · decay · heal · conflict · changelog · attest · health · trust |
| **Configuration** | config · clean · compact · create · policy · onboard · completions · schedule · serve · mcp · hooks · bmad · self-update |
| **Team & Collaboration** | cohort · profile · protocol · pulse · replay · who |

The AI-assisted commands (`search --smart`, `explain`, `distill`, `infer`,
`absorb`, `evolve`, `simulate`, …) call out to the `claude` CLI when it's
available on your PATH (or `ANTHROPIC_API_KEY` is set), and fall back to
plain heuristics when it isn't — so the tool still works without an API key,
just less cleverly.

## boost as an MCP server

boost is itself an MCP server, so an agent can search and install skills mid-task
instead of waiting for you to shell out. `boost mcp register` wires it into every
agent CLI it finds on your PATH — and on a machine with no taps yet it also pulls
in the starter registries first, so **installing boost and running `boost mcp` is
the whole setup**:

```bash
boost mcp register                 # every installed host (default: --host auto)
boost mcp register --host gemini   # just one
boost mcp register --no-seed       # register only; tap nothing
boost mcp register --seed          # re-tap the defaults even if taps exist
boost mcp unregister               # same host selection, in reverse
```

The seed only fires when the catalog is empty — re-running `boost mcp` on a
configured machine leaves your taps alone — and a failed clone is reported
without taking the registration down with it. Export `BOOST_NO_SEED=1` to keep
`boost mcp` a purely local operation (CI images, air-gapped machines).

| Host | CLI | Registered in |
|------|-----|---------------|
| Claude Code | `claude` | `claude mcp add` → its user-scope MCP config |
| Gemini CLI | `gemini` | `gemini mcp add -s user` → `~/.gemini/settings.json` (`mcpServers`) |

A host whose CLI isn't installed is skipped, not an error — name it explicitly
(`--host gemini`) to have boost print the command for you to run later.

Six tools are exposed: `boost_search`, `boost_list`, `boost_info`,
`boost_install`, `boost_doctor`, and `boost_discover_github`. The server also
returns MCP `instructions`, which tell the agent *when* boost is relevant, so a
matching skill gets found at the start of a task rather than after the work is
already reconstructed by hand.

The two hosts place those instructions differently, and it matters. Claude Code
loads them as server instructions in the system prompt. Gemini CLI appends them
to its **memory tier** alongside `GEMINI.md`, and only in a trusted folder — so
outside one they are dropped silently. Each tool's own description therefore
repeats its trigger rather than relying on the server text, because a tool
description is the only part that is always in context at the moment the agent
chooses a tool.

Verify the wiring with `claude mcp list` or `gemini mcp list` — boost should show
as **Connected**. (Gemini only connects stdio servers in a trusted folder; run
`gemini` once in the directory and accept the trust prompt if it shows
`Disabled`.)

## Agent hooks & the BMAD Method

`boost hooks` manages hooks in `settings.json` at either scope — `--scope
project` (`./.claude/settings.json`) or `--scope global`
(`~/.claude/settings.json`). boost only ever touches hooks it created (tagged
with a `# boost:<name>` marker in the command), never your own, and snapshots
the prior file before each write.

```bash
boost hooks add SessionStart -c 'echo hello' -n greet --scope project
boost hooks list
boost hooks remove -n greet --scope project
```

Gemini CLI has hooks too, behind `--host gemini` (`~/.gemini/settings.json`).
The file shape is the same but two details are not, so boost handles both for
you: its `timeout` is in milliseconds rather than seconds — `--timeout 10` is
ten seconds on either host — and most event names differ. Pass whichever
vocabulary you know and boost translates, saying which name it used:

```bash
boost hooks add PreToolUse --host gemini -c 'boost check' -n guard
#   Claude's 'PreToolUse' is Gemini's 'BeforeTool' — using that
boost hooks list          # both hosts, with a host column
```

`SubagentStop` and `SubagentStart` have no Gemini counterpart at all — it has
no sub-agents — so boost refuses those rather than writing a hook that could
never fire.

### BMAD autopilot

`boost bmad on` is a one-time, global switch that puts the
[BMAD Method](https://bmadcode.com/)'s personas in charge of every task that
arrives, without you having to invoke anything. No Node, no network, one
command:

```bash
boost bmad on      # ← that's it
```

It writes seven BMAD persona subagents into `~/.claude/agents/` and installs two
hooks. A `SessionStart` hook briefs the session on the roster; a
`UserPromptSubmit` hook classifies each incoming prompt and prefixes it with a
short routing banner:

```text
[BMAD autopilot] track: build
Lead: `bmad-dev` subagent — Amelia, Senior Software Engineer. Ship it complete and verified.
Support: `bmad-tea` (Murat), `bmad-scribe` (Paige) — spawn them with the Agent tool…
BMAD skill: `bmad-build` — invoke it if it is installed; otherwise the persona's own playbook stands.
Done means: tests: add or update coverage under `tests/`, and run them · docs: update
`README.md` / `docs/` wherever the change shows · roadmap: create or claim the item under
`docs/roadmap/items/` · gate: `make check` green, with real output · `CLAUDE.md` is binding
Work autonomously through to a finished, verified change; stop to ask only when a choice
would change what gets delivered.
```

Nine tracks (`build`, `quality`, `docs`, `planning`, `product`, `architecture`,
`ux`, `discovery`, `review`) each name a lead persona, the support personas to
spawn alongside it, and the canonical BMAD v6 skill for that kind of work.
**That last line is the point**: the definition of done is read off the repo in
front of you — your test directory, your docs, your roadmap items, your gate
command — so documentation, testing and roadmap bookkeeping travel with the task
instead of being remembered afterwards.

The router costs a question nothing. Acknowledgements, slash commands, short
informational questions ("what does `scan_dir` do?") and anything containing
`no bmad` produce **no banner at all** — and because a `UserPromptSubmit` hook
that exits non-zero would erase your prompt, it degrades every failure to
silence and always exits 0.

```bash
boost bmad personas                            # the roster, and whether it's installed
boost bmad route "add tests for the scanner" --plain   # what would this route to?
boost bmad doctor                              # autopilot + workflow state, both scopes
boost bmad off                                 # remove the hooks and the personas
boost bmad on --scope project                  # or keep it to one repo
```

Every persona file carries an ownership stamp containing a digest of its own
contents, so **the moment you edit one it stops being boost's**: `boost bmad on`
reports it as kept rather than overwriting it, and `boost bmad off` leaves it
alone. Delete the file if you want the stock version back.

**The full method** is still a separate, heavier install. `boost bmad install`
delegates to the canonical `npx bmad-method install` (needs Node.js 20.12+) for
the `bmad-*` workflow skills and the per-project `_bmad/` runtime they read on
activation:

```bash
boost bmad install --scope project   # skills + per-project _bmad/ runtime
boost bmad install --scope global    # skills into ~/.claude/skills for every session
boost bmad init                      # add the _bmad/ runtime to the current repo
boost bmad startup on|off            # just the SessionStart briefing
boost bmad disable / enable          # quarantine / restore skills (recoverable)
boost bmad uninstall                 # delete skills + _bmad/ for a scope
```

The two compose. The autopilot routes at `bmad-build`, `bmad-prd` and friends
whether or not they are installed and says which case you're in — with the
skills present you get BMAD's full workflow, without them the persona's own
playbook. Global installs stage the installer in a temp dir and copy only the
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

Four layers, all enforced (`make check` runs the full set; CI runs the same thing):

| Layer | What it does | Gate |
|---|---|---|
| `make test` | pytest across `tests/unit/` (every core module) and `tests/functional/` (drives all 80 commands in-process against sandboxed homes) | **≥90% coverage** of `boost_cli`, statements and branches (`fail_under` in pyproject.toml) |
| `make smoke` | `tests/smoke.sh` — 175 checks run through the actual `./boost` shim (`--online` also hits real registries) | all pass |
| `make mutation` | [mutmut] mutates `boost_cli/core` (~9,900 mutants) and reruns the unit suite against each one | **≥80% killed** (`scripts/mutation_gate.py`) |
| `make evals` | scores the search ranker on a graded golden set — recall@5/@10, MRR, nDCG@5/@10 | **metric floors + no statistically significant regression** (`scripts/eval_gate.py`) |

Dev setup: `make venv` (pulls in pytest, coverage, mutmut — the shipped
runtime itself stays dependency-free). Every test run uses a throwaway
`$HOME`, so your actual agent configs are never at risk.

[mutmut]: https://mutmut.readthedocs.io/

## Evaluation harness

Search quality is the one thing the suite above can't assert: every test can
pass while the ranker quietly gets worse. `make evals` measures it. The harness
is pure stdlib and fully offline — it generates its own corpus of skills, rules,
and workflows and taps it into a disposable `BOOST_HOME`, so a metric that moves
can only mean the *ranker* moved. See [`evals/README.md`](evals/README.md).

**Golden set** — [`evals/golden_set.json`](evals/golden_set.json): 36 realistic
queries with **graded** relevance (3 perfect · 2 useful · 1 marginal) over the
generated corpus. Generated and validated by `evals/make_golden.py`, which
refuses a judgment naming a skill the corpus doesn't contain; `--check` fails CI
on drift, so the file can never disagree with its source.

**Five metrics**, all computed by `evals/metrics.py`:

- **recall@5** / **recall@10** — of everything relevant, what fraction reached the top *k*.
- **MRR** — 1/rank of the first relevant hit, averaged; sensitive only to the top of the list, which is where people look.
- **nDCG@5** / **nDCG@10** — graded gain (`2^rel − 1`) with the standard `log2(rank + 1)` discount; the only metric that distinguishes the right results in the wrong order from the right order.

**Significance gating.** A metric dropping isn't automatically a regression —
with 36 queries, one unlucky result moves the mean. So `scripts/eval_gate.py`
fails a metric only when it falls more than 0.02 below the committed baseline
**and** a seeded 10,000-resample paired bootstrap over the per-query deltas puts
that drop at `p < 0.05`. Alongside that, each metric has an absolute floor set
~0.05 below its first measured value, which catches the erosion that a
compare-to-last-commit check never sees. Accepting a real ranking change is a
deliberate `make evals-baseline` commit.

**Faithfulness.** `boost explain` and `boost distill` generate prose from a
`SKILL.md`, and their failure mode is overclaiming. The harness scores that with
the Ragas method — split the answer into atomic statements, verify each against
the source, score supported/total — and reports it alongside what the runtime
grounding guardrail in `boost explain` would do with the same reply. With no
`claude` CLI and no `ANTHROPIC_API_KEY` it **skips rather than fails**, and
reports a status instead of a number so "couldn't measure" is never mistaken for
"scored zero". It's therefore outside `make check`; run it with
`make evals-online`.
