# RAG architecture for boost — natural-language skill retrieval over registry taps

**Status:** design (no code yet) · **Audience:** boost maintainers/reviewers · **Scope:** how boost
should retrieve the *best* skills/rules/workflows for a natural-language task, and expose that to agents
through the MCP server — without breaking boost's zero-dependency posture.

---

## 1. Goals & non-goals

### Goals

1. **Natural-language retrieval.** An agent asks "best skill for testing a React app" and boost returns a
   semantically-ranked shortlist with reasons — not just keyword hits.
2. **Full-content search.** Rank over the *whole* skill/rule/workflow body, not only the frontmatter
   `name` + one-line `description` that `catalog.search` uses today.
3. **Incremental, persisted index.** Indexing full bodies is the expensive step, so it happens once and
   refreshes only when a tap changes — never a scan-per-query.
4. **MCP-hub extensibility.** Position the MCP server to later call out to GitHub, a database, and other
   dependencies as drop-in tools.

### Non-goals

- Forcing FastAPI/django (the MCP transport is stdio JSON-RPC, not HTTP — a web framework has nothing to
  serve here).
- Making a vector database or `langchain` a *required* runtime dependency.
- Breaking the zero-dependency default install or the `make check` gates at any phase.

---

## 2. Why the current search is not enough

`catalog.search` (`boost_cli/core/catalog.py:213`) scores each entry with a substring/token heuristic
over `name`, the one-line `description`, and a JSON dump of the frontmatter `meta`. The MCP `boost_search`
tool (`boost_cli/commands/configuration.py:897`) calls straight into it. Two structural limits:

- **Vocabulary gap.** "test my React app" shares no tokens with a skill named `jest-runner` described as
  "unit testing for JavaScript" — so it scores 0 and never surfaces.
- **Shallow corpus.** The actual instructions — the part that says *what the skill does* — live in the
  body, which is never read.

**Key enabling fact:** after `boost tap`, every item's full body is already on local disk under
`~/.boost/repos/<owner__repo>/` and is reachable from the catalog entry's `skill_md` / `rel_dir` fields
(`_make_entry`, `catalog.py`). So full-content indexing is a **local batch job — no extra network calls.**

---

## 3. Retrieval interface — the seam everything plugs into

Every retrieval engine (stdlib now, dense-vector later) implements one small contract, so `boost_search`
and the CLI depend on the interface, never a concrete engine. Proposed shape for `boost_cli/core/rag.py`:

```python
class Hit(TypedDict):
    entry: dict     # the catalog entry (name, description, tap, kind, skill_md, rel_dir, meta, ...)
    score: float    # engine-native relevance score (higher = better)
    snippet: str    # the best-matching passage, for display + LLM rerank context

class Retriever(Protocol):
    name: str                                   # "bm25" | "dense" | ...
    def build(self, entries: list[dict]) -> None: ...          # (re)index full bodies
    def query(self, text: str, k: int = 60,
              kind: str | None = None) -> list[Hit]: ...        # top-k, optionally filtered to one kind
    def ready(self) -> bool: ...                # False -> caller degrades to the lexical fallback
```

`get_retriever()` returns the best **available** engine, preferring a dense engine when the `[rag]` extra
is installed and its index exists, else the always-on stdlib BM25 engine — the same
prefer-then-degrade shape as `core/ai.py` (`available()` → fall back). No caller ever branches on the
concrete class.

---

## 4. Content extraction & chunking

For each catalog entry (from `catalog.all_entries()`, `catalog.py:177`):

1. **Resolve the body file** from `repos_dir() / safe_tap / rel_dir / <defining file>` using the entry's
   `skill_md` (`paths.repos_dir()`, `paths.py:40`).
2. **Strip frontmatter** and keep the prose with `frontmatter.parse(text) -> (meta, body)`
   (`boost_cli/core/frontmatter.py:136`) — reuse, don't re-parse.
3. **Normalize** — collapse whitespace, drop code-fence noise for scoring (keep it for the snippet).
4. **Chunk** into passages so retrieval is passage-level, not whole-file (a 400-line skill shouldn't be one
   blob). Defaults (tunable, documented in code):
   - target **~1,000 characters** per chunk, split on heading/paragraph boundaries;
   - **~150-character overlap** so a match spanning a boundary isn't lost;
   - **cap ~40 chunks per item** to bound pathological files.
5. Each chunk carries back-pointers `{entry_name, tap, kind, chunk_ix}` so a hit maps to its catalog entry.

The **document unit for scoring is the chunk**; results are aggregated back to the **entry** (an entry's
score = max/soft-max over its chunk scores) so the shortlist is a list of *skills*, not fragments.

---

## 5. Index format & storage (incremental)

Persist under `paths.cache_dir()` (`paths.py:44`) → `~/.boost/cache/rag_index.json` (Phase 2 may add a
sibling binary/`.sqlite` for vectors). Refresh is **per-tap and commit-keyed**: each tap cache already
records the git `commit` it was built from (`catalog.rebuild_tap`, `catalog.py:150`, writes
`"commit": gitutil.head_commit(...)`). The RAG index stores the same commit per tap; on `build()` we only
re-chunk and re-score taps whose commit changed.

Schema sketch:

```jsonc
{
  "version": 1,
  "engine": "bm25",
  "generated": "2026-07-18T...Z",
  "commits": { "anthropics__skills": "<sha>", "obra__superpowers": "<sha>" },
  "params": { "chunk_chars": 1000, "overlap": 150, "k1": 1.2, "b": 0.75 },
  "stats": { "docs": 41213, "entries": 9062, "avg_len": 178.4 },
  "docs": [ { "id": 0, "entry": "jest-runner", "tap": "...", "kind": "skill", "chunk_ix": 2,
              "len": 164, "snippet_at": [start,end] } ],
  "postings": { "test": [[0, 3], [17, 1]], "react": [[0, 1]] }   // term -> [[doc_id, tf], ...]
}
```

Postings + doc lengths are all BM25 needs. Phase 2 swaps `postings` for a vector store but keeps `docs`
and `commits`.

---

## 6. Phase 1 — stdlib full-content RAG (zero new deps, mergeable)

**No third-party imports. Stays green through `make check`.**

### 6a. Engine — `boost_cli/core/rag.py`

Pure-Python **BM25** over the chunk corpus (BM25 subsumes TF-IDF and handles document-length
normalization, which matters when bodies vary from 3 lines to 300). Sparse term vectors are a legitimate
"vector" retrieval — we get semantic *recall breadth* from full-text coverage, and the LLM rerank
(below) supplies the semantic *precision*. Tokenization reuses the existing splitter style from
`catalog.search` (`re.split(r"[\s,/_-]+", ...)`), plus lightweight lowercasing and a small stopword list.
Scoring is standard BM25 (`k1≈1.2`, `b≈0.75`). At ~9k items / tens of thousands of chunks this is a
dict-of-postings scan — comfortably sub-second per query in Python.

**Tokenization is exact-match, and `stem_expansions` is the one concession to that.**
A query term and its own inflection are unrelated strings, so `boost search brainstorm`
returned nothing while `brainstorming` returned the skill. Measured over 461 tap caches,
4,663 of 29,607 item names (15.7%) were unreachable by an attested stem — `pattern` missed
474 names ending `-patterns`. Before scoring, any term with **no** posting list is replaced
by the commonest term it prefixes, found with an index-backed range scan over the postings
table. A term that *has* postings is never touched: expansion only ever adds signal where
`_bm25` scored exactly none, so a query whose terms all exist ranks byte-identically and the
retrieval floors cannot move. That is what makes it a fallback rather than a stemmer — a real
stemmer conflates terms that both exist, which changes established rankings and would need an
index-format bump and a regenerated baseline. Terms shorter than `STEM_MIN_LEN` (4) are left
alone, because a three-letter prefix expands to a guess. `boost search` states the
substitution rather than silently answering a different question.

**Query path as shipped** (post `cold-search-reads-the-whole-catalogue`): with
`entries=None` — the CLI, MCP and eval path — `rag.retrieve` ranks straight off
the index's own doc metadata and materialises real catalog entries only for the
final `k` survivors, loading only *their* taps' caches (`_retrieve_from_index`).
The previous shape parsed every tap cache on the machine per query
(`catalog.all_entries()`: 458 files / ~100 MB / 0.32 s measured at 71.6k
entries) and computed a display snippet for every scored doc (39,726 calls to
serve 60). Snippet windowing now runs on returned hits only, on both paths.
The contract is byte-identical-or-fall-back: any survivor whose entry cannot be
materialised (a tap cache vanished under a stat-fresh index) reruns the query
through the explicit-`entries` path rather than approximating. An explicit
`entries=` list (the eval harness, `boost chat`) keeps today's exact path.
`dense.ready()` stats the store before importing the backend for the same
cold-path reason. Measured end to end: 0.94 s → 0.49 s cold at 458 taps.

### 6b. Two-stage pipeline — upgrade `boost_search` / `catalog.search` **in place**

No parallel MCP tool (per decision). The upgraded flow:

1. **Retrieve** top-N (~60) candidate entries via `Retriever.query(task, k=60, kind=?)`.
2. **Rerank / synthesize** with the existing LLM bridge `core/ai.py` (`ai.ask(...)`, `ai.py:39`): feed the
   candidates' `name · kind · description · best snippet` plus the user's task, ask for a ranked shortlist
   with a one-line "why" per pick. This is the RAG "augment + generate" step.
3. **Degrade gracefully.** If `ai.available()` is False (`ai.py:26`) — no `claude` CLI and no
   `ANTHROPIC_API_KEY` — return the BM25 order directly with snippet justifications. If the RAG index
   doesn't exist yet, fall back to today's `catalog.search` so nothing regresses.

`boost_search` keeps its current `{query}` input schema and flat `if/elif` dispatch
(`configuration.py:895`) — only its body changes to call the pipeline. Existing `--smart` reranking in
`cmd_search` (`_ai_rank`, `discovery.py:150`) is folded into / superseded by this path.

### 6c. New command — `boost reindex`

Register `("reindex", "find", "discovery", "Build/refresh the full-content search index")` in the
`COMMANDS` table (`boost_cli/cli.py:48`) and add `cmd_reindex(argv)` in `discovery.py`. It calls
`rag.build(catalog.all_entries())`, honoring commit-keyed incremental refresh, and prints doc/entry
counts. The search path also lazily triggers a refresh when it detects a tap commit newer than the index.

### 6d. Tests & gates (Phase 1)

- `tests/unit/test_rag.py` — chunking, BM25 scoring, incremental refresh, degradation paths. Because
  `rag.py` lives in `core/`, it is **mutation-gated at 80%** (`scripts/mutation_gate.py`) — write tests
  that pin the scoring math and the fallback branches.
- `tests/functional/test_cli_configuration.py` — extend `TestMcp` so `boost_search` still returns the
  MCP content shape, with and without the index present.
- `tests/functional/test_cli_discovery.py` — cover `boost reindex`.
- Keep coverage ≥90%; no new runtime import means ruff/mypy(py312)/smoke are unaffected.

---

## 7. Phase 2 — opt-in dense semantic backend (`[rag]` extra) — ✅ shipped

Implemented in `boost_cli/core/embed.py` (embeddings bridge) + `boost_cli/core/dense.py`
(sqlite-vec vector store), wired through `rag.search` → `rag._retrieve_any` (prefer dense,
floor to BM25) and surfaced via `boost reindex --dense`. The `[rag]` extra pulls only
`sqlite-vec`; embeddings come from Voyage/OpenAI over `urllib`, so no client library is added.

Establish the project's **first** optional extra:

```toml
[project.optional-dependencies]
rag = [ "..." ]   # dense-embedding + vector-store stack
```

A second `Retriever` implementation (`engine="dense"`) that:

- **Embeds** each chunk into a dense vector — via a local model or an embeddings API over `urllib`
  (note: Anthropic exposes **no** embeddings endpoint; the API options are Voyage AI, which Anthropic
  recommends, or OpenAI). API keys follow the `core/ai.py` env-var convention.
- **Stores** vectors in an on-disk store. Candidates, lightest-first: **`sqlite-vec`** (a single-file,
  stdlib-adjacent SQLite extension — closest to boost's ethos) or **`chromadb`** (a full vector DB) for
  users who explicitly want one. Either sits behind the same `Retriever` interface.
- **Degrades:** if the extra isn't installed or the vector index is absent, `get_retriever()` returns the
  Phase-1 BM25 engine. **TF-IDF/BM25 is the always-on floor.**

This is where the vector-database preference is honored — as an opt-in upgrade, not a tax on the default
install. `pip install boost-skill-cli` stays zero-dependency; `pip install boost-skill-cli[rag]` turns on
dense retrieval.

---

## 8. Phase 3 — MCP as a hub (GitHub, database, other deps) — ✅ shipped

The flat `if/elif` dispatcher is now an **extensible registry** (`boost_cli/core/mcp.py`):

1. **Registry refactor (done).** `core/mcp.py` defines a `Registry` — an ordered `name -> (spec, handler)`
   map. Each handler is `fn(args: dict) -> (text, is_error)` and is paired with its
   `{name, description, inputSchema}` via `REGISTRY.register(...)` (or the `@REGISTRY.tool(...)`
   decorator). The JSON-RPC server iterates it: `tools/list` returns `REGISTRY.specs()` and `tools/call`
   dispatches through `REGISTRY.call(name, args)` — an unknown tool returns `(None, False)` in exactly one
   place, so the server answers a single `-32602 unknown tool` error. `_MCP_TOOLS` and `_mcp_tool` remain
   as thin back-compat shims over the registry.
2. **First reach-out tool (done), behind graceful degradation** (the `core/ai.py` pattern — probe, else a
   helpful message, never raise):
   - **`boost_discover_github`** — GitHub code-search for `SKILL.md` repos to grow the corpus, via the
     one-shot `discovery.github_skill_search(query, limit)` helper. No `gh` CLI → returns an install hint
     with `is_error=True`; a failed search → a retry hint; otherwise a ranked repo list. It never writes a
     cache and never crashes the server.
   - Future tools (Phase-2 vector store / a database query, a generic external API) plug in the same way.

**Extension contract** — to add an MCP tool, no dispatcher or server edit is needed:

```python
def _tool_x(args: dict) -> tuple[str | None, bool]:
    # probe for any external dependency; degrade to a helpful message if absent
    return "…result text…", False          # (text, is_error)

REGISTRY.register("boost_x", "one-line description",
                  {"type": "object", "properties": {…}}, _tool_x)
```

A handler that reaches out to a dependency **must** degrade (return a short message, not raise) so the
long-lived stdio server survives a missing `gh`, offline network, or absent `[rag]` extra. Registration
order is preserved and is the `tools/list` order.

Phase 3 landed *after* the retrieval core was proven, so the hub grew on a stable seam.

---

## 9. Growing the corpus from GitHub (reuse, don't rebuild)

These already exist and should be surfaced (and, in Phase 3, exposed through MCP) rather than reinvented:

| Command | What it does |
|---|---|
| `boost tap <owner/repo>` | Add one GitHub repo as a registry (shallow clone → indexed). |
| `boost tap --catalog [--type/--category/--limit]` | Bulk-add from the curated 470-registry catalog (`boost_cli/data/registries.json`). |
| `boost index` → `boost discover` | GitHub-wide code search via `gh` (`cmd_index`, `discovery.py:217`) to find new `SKILL.md` repos to tap. |

Every newly tapped repo lands on local disk and is picked up by the next `boost reindex` — corpus growth
and RAG indexing compose automatically.

---

## 10. Roadmap & gate/compatibility summary

| Phase | Capability | New deps | Default-on? | `make check` impact |
|---|---|---|---|---|
| **1** | Full-content BM25 retrieval + LLM rerank; `boost_search` upgraded in place; `boost reindex` | **none** (stdlib) | ✅ yes | New `core/rag.py` (mutation-gated) + tests; coverage ≥80%; ruff/mypy/smoke unaffected |
| **2** | Dense embeddings + vector store | `[rag]` extra only | ❌ opt-in | Extra-only; default path unchanged; TF-IDF fallback keeps green |
| **3** ✅ | MCP hub: extensible `core/mcp.py` registry + `boost_discover_github` reach-out | none required (deps per tool, opt-in) | ❌ opt-in | New `core/mcp.py` (mutation-gated) + `test_mcp.py`; `TestMcp`/`TestGithubSkillSearch` cover the tool; coverage 93% |

**Invariant preserved at every phase:** `pip install boost-skill-cli` remains zero-runtime-dependency and
`make check` stays green; all heavier machinery is opt-in behind the `[rag]` extra and the
prefer-then-degrade pattern already established by `core/ai.py`.

---

## 11. Open questions for implementation

- **Snippet vs. full-chunk in the LLM rerank prompt** — token budget vs. precision; start with best
  snippet + description.
- **Index staleness UX** — auto-refresh silently on search, or require an explicit `boost reindex`? Plan:
  auto-refresh when cheap (commit changed for ≤1 tap), otherwise hint the user to run `boost reindex`.
- **BM25 parameters** — validate `k1`/`b` against the real corpus; expose via `params` in the index so they
  are tunable without a rebuild-format change.
- **Phase-2 vector store choice** — `sqlite-vec` (ethos fit) vs. `chromadb` (familiarity); decide when
  Phase 2 starts, not now.
