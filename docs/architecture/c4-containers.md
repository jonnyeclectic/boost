# C4 Level 2 — Containers

The deployable and persistent pieces inside boost. Everything here lives on one machine: boost has
no server side, and every path is resolved at call time from `$HOME` (or `$BOOST_HOME`) by
`core/paths.py`, which is what makes `HOME=<tempdir>` sandboxing work in tests.

```mermaid
C4Container
  title Container Diagram — boost

  Person(dev, "Developer", "Runs boost commands")
  System_Ext(agents, "AI coding agents", "Claude Code, Windsurf, Cursor, Gemini CLI, Antigravity CLI, Codex")
  System_Ext(github, "GitHub", "Registry repos and skill sources")

  Container_Boundary(boost, "boost") {
    Container(cli, "boost CLI", "Python 3.12+, stdlib only", "81 commands in 8 groups; lazy-imports one module per invocation")
    Container(mcp, "MCP server", "JSON-RPC over stdio", "Exposes search/install/doctor as agent tools")
    Container(web, "boost serve", "http.server", "Local read-only web UI")
    Container(engine, "core engine", "Python package", "Catalog, retrieval, store, trust — see the component diagram")
  }

  Boundary(state, "boost state — ~/.boost") {
    ContainerDb(repos, "repos/", "shallow git clones", "Tapped registries")
    ContainerDb(cache, "cache/", "JSON", "Catalogs built from frontmatter")
    ContainerDb(statedir, "state/", "JSON", "Pins, policy, profiles, snapshots")
  }

  Boundary(installed, "installed skills") {
    ContainerDb(store, "~/.agents/skills", "files + .skill-lock.json v3", "Canonical store — single source of truth")
    ContainerDb(links, "~/.claude, ~/.windsurf, ~/.cursor, ~/.gemini/antigravity-cli", "symlinks into the store", "Four linking agents")
    ContainerDb(native, "~/.gemini, ~/.codex", "GEMINI.md + TOML commands, AGENTS.md", "Gemini CLI and Codex: rules and Gemini CLI workflows, no skill links")
  }

  Rel(dev, cli, "Invokes")
  Rel(agents, mcp, "Calls tools", "stdio")
  Rel(cli, engine, "Delegates to")
  Rel(mcp, engine, "Delegates to")
  Rel(web, engine, "Reads from")
  Rel(engine, github, "Clones and searches", "git, REST")
  Rel(engine, repos, "Clones taps into")
  Rel(engine, cache, "Indexes catalogs into")
  Rel(engine, statedir, "Persists policy and pins")
  Rel(engine, store, "Copies skills into")
  Rel(engine, links, "Symlinks out to")
  Rel(engine, native, "Materialises rules and commands")
  Rel(agents, store, "Reads directly", "Gemini CLI and Codex")
  Rel(agents, links, "Reads")

  UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="2")
```

## Six agent targets, but only four get symlinks

Claude Code, Windsurf, Cursor and Antigravity CLI each get a symlink into the canonical store.
Gemini CLI and Codex do not: both discover `~/.agents/skills`, the canonical store itself, so both
are configured with `links_skills: false` (`core/config.py` records how each was verified).

- **Gemini CLI** implements the Agent Skills standard. Linking into `~/.gemini/skills` as well
  would put one skill in two of its discovery tiers, where the `.agents` alias out-ranks whatever
  was linked, costing a "Skill conflict detected" line per skill per session and buying nothing.
- **Codex** lists `$HOME/.agents/skills` among its skill roots and de-duplicates by resolved path,
  so a link would cost nothing and add nothing. Not linking also keeps skills visible to a user who
  moves `CODEX_HOME`, because the store root follows `HOME`.
- **Antigravity CLI** shares the `~/.gemini` tree but reads neither the store nor the shared
  `~/.gemini/skills`, so it is a linking agent, and its links go into
  `~/.gemini/antigravity-cli/skills`, where Gemini CLI does not look.

That distinction is load-bearing for anything you write:

- Iterate `agents.linking_agents()` for anything symlink-shaped — linking, unlinking, stale-link
  sweeps, coverage counts.
- Use `agents.enabled_agents()` for rules and workflows, which materialise into each agent's dotdir
  that takes them, `~/.gemini/` and `~/.codex/` included. `agents.native_store_agents()` is the
  complement, for reporting.

## Why the canonical store exists

One copy of each skill lives in `~/.agents/skills`; every linking agent gets a symlink to it. That
is what makes "install once, available everywhere" true without N copies drifting apart, and it is
why `.skill-lock.json` lives beside the store rather than per-agent. Uninstall removes the copy and
sweeps the links; `boost sync` reconciles reality against the lock.

## The state directory is not the store

`~/.boost` is *derived* data — clones, indexes and preferences that boost can rebuild. `~/.agents`
is *user* data: the skills themselves. Deleting `~/.boost` costs a re-tap and a re-index; deleting
`~/.agents/skills` uninstalls everything. Keeping them apart is deliberate.
