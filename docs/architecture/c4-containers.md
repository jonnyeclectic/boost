# C4 Level 2 — Containers

The deployable and persistent pieces inside boost. Everything here lives on one machine: boost has
no server side, and every path is resolved at call time from `$HOME` (or `$BOOST_HOME`) by
`core/paths.py`, which is what makes `HOME=<tempdir>` sandboxing work in tests.

```mermaid
C4Container
  title Container Diagram — boost

  Person(dev, "Developer", "Runs boost commands")
  System_Ext(agents, "AI coding agents", "Claude Code, Cursor, Windsurf, Gemini CLI")
  System_Ext(github, "GitHub", "Registry repos and skill sources")

  Container_Boundary(boost, "boost") {
    Container(cli, "boost CLI", "Python 3.12+, stdlib only", "78 commands in 8 groups; lazy-imports one module per invocation")
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
    ContainerDb(links, "~/.claude, ~/.cursor, ~/.windsurf", "symlinks into the store", "Three linking agents")
    ContainerDb(gemini, "~/.gemini", "GEMINI.md + TOML commands", "Rules and workflows only")
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
  Rel(engine, gemini, "Materialises rules and commands")
  Rel(agents, store, "Reads directly", "Gemini CLI only")
  Rel(agents, links, "Reads")

  UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="2")
```

## Four agent targets, but only three get symlinks

Gemini CLI implements the Agent Skills standard and discovers `~/.agents/skills` — the canonical
store — *directly*, so it is configured with `links_skills: false`. Linking into `~/.gemini/skills`
as well would put one skill in two of its discovery tiers, where the `.agents` alias out-ranks
whatever was linked, costing a "Skill conflict detected" line per skill per session and buying
nothing.

That distinction is load-bearing for anything you write:

- Iterate `agents.linking_agents()` for anything symlink-shaped — linking, unlinking, stale-link
  sweeps, coverage counts.
- Use `agents.enabled_agents()` for rules and workflows, which materialise into `~/.gemini/` like
  any other agent's dotdir. `agents.native_store_agents()` is the complement, for reporting.

## Why the canonical store exists

One copy of each skill lives in `~/.agents/skills`; every linking agent gets a symlink to it. That
is what makes "install once, available everywhere" true without N copies drifting apart, and it is
why `.skill-lock.json` lives beside the store rather than per-agent. Uninstall removes the copy and
sweeps the links; `boost sync` reconciles reality against the lock.

## The state directory is not the store

`~/.boost` is *derived* data — clones, indexes and preferences that boost can rebuild. `~/.agents`
is *user* data: the skills themselves. Deleting `~/.boost` costs a re-tap and a re-index; deleting
`~/.agents/skills` uninstalls everything. Keeping them apart is deliberate.
