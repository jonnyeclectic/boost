---
id: langchain-langgraph-langsmith-integration
board: code
section: planned
status: planned
category: Feature
complexity: L
impact: High
wow: 4
note: a second consumer class for the catalogue — blocked on one dependency conflict boost already owns
order: 88
title: production-ready LangChain / LangGraph / LangSmith integration
---
Every agent boost supports today is a <b>coding</b> agent that reads files off disk — Claude Code,
Cursor, Windsurf, Gemini CLI. The catalogue itself is not coding-specific: it is 10,000+ retrievable
procedures with frontmatter, provenance and a lock file. A LangChain application cannot reach any of
it, so the same procedure has to be re-written as a prompt string by hand. This item is about making
the catalogue addressable from a Python agent runtime as well as from a dotfile.

<b>Three surfaces, and they are not equally justified.</b>

<code>langchain</code> — a <code>BoostRetriever</code> implementing <code>BaseRetriever</code> over
the engine <code>boost search</code> already uses: BM25 (<code>core/rag.py</code>) fused with
optional dense retrieval (<code>core/dense.py</code>) through <code>rag.rrf_fuse</code>. The
retrieval quality is already measured — the required gate floors recall@k, hit@1, MRR and nDCG@k
against <code>tests/eval/golden.jsonl</code> — so this surface ships with numbers rather than
claims. Plus a document loader that turns a <code>SKILL.md</code> into prompt content with its
frontmatter preserved as metadata.

<code>langgraph</code> — skills as procedures a graph pulls <i>mid-run</i>: a node that retrieves
the right skill for the current state and injects it, rather than stuffing every procedure into the
system prompt. boost's <code>workflow</code> item kind is already the closest thing it has to a
graph node, and <code>core/workflows.py</code> already renders per-runtime formats
(<code>TOML_COMMAND_AGENTS</code> for Gemini), so a LangGraph renderer is a new target for existing
machinery, not a new concept.

<code>langsmith</code> — hosted tracing plus datasets/evaluators. boost already has a four-tier
eval story (Tier 1 BM25 floors, 1b <code>ranx</code> significance, 2a/2b LLM rerank and recommend,
2c <code>ragas</code> faithfulness) and a baseline keyed by query-set digest. LangSmith would host
the golden set and run online evals against real traffic. It must <b>not</b> replace the required
gate, which is deliberately pure-stdlib BM25 needing no API key — a required check that depends on
a SaaS account is a required check that fails when someone else's billing lapses.

<b>What "production ready" forces, specifically.</b>

<b>It cannot be an extra — the Python floor decides it.</b> boost is
<code>requires-python = "&gt;=3.9"</code> and CI tests 3.9 / 3.12 / 3.14 across Linux, macOS and
Windows. Measured 2026-08-02: <code>langchain</code> 1.3.14 declares
<code>&gt;=3.10.0,&lt;4.0.0</code> and <code>langsmith</code> 0.10.15 declares <code>&gt;=3.10</code>. So
an extra would either fail to resolve on the 3.9 leg or force boost to drop 3.9 for every user,
including those who never touch LangChain. A separately versioned distribution that depends on
<code>boost-skill-cli</code> keeps the floor a property of the integration.

<b>There is a dependency conflict boost already owns, and it blocks this.</b> The
<code>[eval]</code> extra pins <code>langchain-core&lt;0.4</code>,
<code>langchain-community&lt;0.4</code> and <code>langchain-openai&lt;1</code>, because ragas 0.2.x
hard-imports a <code>ChatVertexAI</code> path that langchain ≥1.0 removed. One environment cannot
hold both that pin and langchain 1.x. The good news is measured: <b>ragas 0.4.3 declares
<code>langchain</code>, <code>langchain-core</code>, <code>langchain-community</code> and
<code>langchain_openai</code> with no upper bound at all</b>, and still supports Python ≥3.9. So the
first step is small, independently valuable, and testable on its own — move <code>[eval]</code>
from <code>ragas&gt;=0.2,&lt;0.3</code> to 0.4 and delete the three pins. Nothing else should be built
until that lands, or the project holds two incompatible langchain majors.

<b>The existing rules still apply.</b> Nothing in the integration may be imported by the CLI or by
the required gate — the discipline <code>[eval]</code> already follows. It must degrade cleanly
without an API key, the way <code>embed.py</code> falls back Voyage → OpenAI → local
<code>bge-small-en-v1.5</code>; a key is a quality upgrade, never the entry fee. And it carries its
own tests without lowering the 80% coverage or 80% mutation floors.

<b>Delivery order.</b> Each phase is independently shippable, and phase 0 is worth doing on its own
merits whatever happens to the rest.

<b>0 &middot; unpin.</b> Move <code>[eval]</code> to <code>ragas&gt;=0.4</code> and delete the three
langchain pins, freeing the langchain major. Contained, testable, no new surface.
<b>1 &middot; retrieve.</b> A <code>boost-langchain</code> distribution carrying
<code>BoostRetriever</code> and the <code>SKILL.md</code> loader — the smallest thing that makes the
catalogue reachable from a LangChain app, and the one with measured retrieval quality behind it.
<b>2 &middot; orchestrate.</b> The LangGraph node, plus a graph-shaped render target in
<code>core/workflows.py</code> beside the existing per-agent formats.
<b>3 &middot; observe.</b> LangSmith tracing, and the golden set published as a LangSmith dataset so
online evals run against the same queries the offline gate uses.

<b>One scoping decision shapes phase 1's API</b> and should be settled before it starts: a LangChain
<i>application</i> pulling skills at runtime is the consumer all three phases serve, whereas a
LangChain <i>developer</i> who just wants these procedures in their editor is already served by
<code>boost install</code> with no langchain dependency at all. Phase 1 should be designed for the
former — a retriever, not an installer — and the docs should point the latter at the CLI so the new
package does not accumulate a second, redundant install path.
