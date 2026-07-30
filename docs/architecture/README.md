# boost architecture

C4-model diagrams of how boost is put together, in Mermaid so they render on GitHub and stay
reviewable in a diff. Read them in order — each one opens a box the previous one drew.

| Level | Diagram | Answers |
|-------|---------|---------|
| 1 | [System context](c4-context.md) | Who uses boost and what it talks to |
| 2 | [Containers](c4-containers.md) | The processes and the directories on disk |
| 3 | [Core components](c4-components-core.md) | How the 45 engine modules group, and the layering rule |
| — | [Dynamic: install](c4-dynamic-install.md) | What `boost install` actually does, step by step |

Subsystem designs live beside these rather than inside them:
[rag-architecture.md](../rag-architecture.md) covers retrieval in depth, and
[DEBUGGING.md](../DEBUGGING.md) covers the diagnostic surfaces.

## The three invariants worth knowing before you read code

**1. Layering is enforced.** `cli → commands → core`, checked by `import-linter` in `make lint` and
CI. `core/` is the engine and the only layer the mutation gate targets; `commands/` is thin glue.
Putting behaviour in the command layer means it is covered by neither.

**2. Paths resolve at call time.** `core/paths.py` reads `$HOME` (or `$BOOST_HOME`) on every call
rather than caching at import. That is not incidental — it is what lets the whole test suite point
a temporary directory at `HOME` and exercise real install paths without touching your machine.

**3. Optional is always optional.** Dense retrieval falls back to BM25; the AI bridge falls back to
heuristics. The shipped runtime is stdlib-only and `[project].dependencies` is empty. Any new
dependency belongs behind an extra, and any new path through it needs a degraded branch.

## Keeping these honest

These diagrams are hand-written, not generated, so they can drift. They describe *structure* —
layers, boundaries, which component owns which decision — rather than anything that changes with a
routine edit, so drift should be rare and visible. The claims most worth re-checking when the
engine changes:

- the component groupings in [c4-components-core.md](c4-components-core.md), against
  `ls boost_cli/core/`
- the layering contract, against `[tool.importlinter]` in `pyproject.toml`
- the install sequence, against `core/store.py::install`
- the agent-target split, against `agents.linking_agents()` and `agents.native_store_agents()`

Command-level reference is generated and lives elsewhere: `docs/commands.html` is built from the
`COMMANDS` registry by `scripts/build_command_reference.py`. Do not hand-edit it.
