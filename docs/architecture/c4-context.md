# C4 Level 1 — System context

Who uses boost, and what it talks to. This is the only diagram that shows boost as a single box;
every other diagram in this directory opens that box.

```mermaid
C4Context
  title System Context — boost

  Person(dev, "Developer", "Installs and governs agent skills")

  System(boost, "boost", "CLI + MCP server that finds, installs and governs the skill, rule and workflow files AI coding agents run on")

  System_Ext(agents, "AI coding agents", "Claude Code, Cursor, Windsurf, Gemini CLI")
  System_Ext(github, "GitHub", "Hosts registry repos (taps) and skill sources")
  System_Ext(llm, "Anthropic API / claude CLI", "Optional LLM-assisted ranking and authoring")
  System_Ext(embed, "Voyage / OpenAI embeddings", "Optional vectors for dense retrieval")
  System_Ext(pypi, "PyPI", "Distributes the boost-skill-cli package")

  Rel(dev, boost, "Runs commands", "terminal")
  Rel(dev, pypi, "Installs boost from", "pipx / pip")
  Rel(agents, boost, "Calls boost_search / boost_install", "MCP, JSON-RPC over stdio")
  Rel(boost, github, "Clones taps and searches code", "git, REST")
  Rel(boost, agents, "Writes skills, rules and slash-commands", "files + symlinks")
  Rel(boost, llm, "Ranks, explains, distills", "optional, degrades to heuristics")
  Rel(boost, embed, "Embeds the catalog", "optional, falls back to BM25")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## What the boundaries mean

**boost never requires the network to be useful.** Both external AI services are optional and
degrade rather than fail: `core/ai.py` falls back to heuristics when neither the `claude` CLI nor
`ANTHROPIC_API_KEY` is present, and `core/dense.py` falls back to BM25 when the `[rag]` extra or an
embeddings key is missing. Only tapping and installing genuinely need GitHub.

**The agents are consumers, not integrations.** boost does not drive an agent or run inside one.
It writes files into the locations agents already read, so a skill installed once is visible to
every configured agent with no per-agent wiring — see
[c4-containers.md](c4-containers.md) for where those files land.

**The shipped runtime is stdlib-only.** `[project].dependencies` is empty by design, so the arrow
to PyPI carries a package with no runtime dependency closure of its own. Everything optional lives
behind an extra.
