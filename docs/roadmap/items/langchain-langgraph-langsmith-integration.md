---
id: langchain-langgraph-langsmith-integration
board: code
section: compat
status: shipped
owner: loop/langchain-integration
pr: 466
category: Feature
complexity: L
impact: High
wow: 4
note: a second consumer class for the catalogue — blocked on one dependency conflict boost already owns
order: 88
title: production-ready LangChain / LangGraph / LangSmith integration
---
<b>Update (PR #472):</b> the separate-distribution decision below was revisited with better
evidence and reversed — <code>boost_langchain</code> now ships <i>inside</i> the
<code>boost-skill-cli</code> wheel behind a <code>[langchain]</code> extra, and the conflict
isolation this card attributes to distribution boundaries is carried by extra boundaries instead
(<code>[eval]</code> and <code>[langchain]</code> never co-install; pip refuses the pair loudly).
The history below is preserved as written; see <code>langchain-in-the-wheel</code> for the
reversal's evidence.

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

<b>Packaging is an open decision — the Python floor does not settle it.</b> This card first argued
the opposite ("it cannot be an extra — the Python floor decides it"), and since that reasoning is
in the repo's history and someone could act on it, it is corrected here rather than quietly
rewritten.

<i>What was right.</i> <code>langchain</code> 1.3.14 does declare
<code>&gt;=3.10.0,&lt;4.0.0</code>, and <code>langgraph</code> 1.2.10 and <code>langsmith</code>
0.10.15 both declare <code>&gt;=3.10</code> — re-measured 2026-08-03, unchanged. Installing a
<code>[langchain]</code> extra on the old 3.9 CI leg really would have failed.

<i>What did not follow from it.</i> That failure is confined to whoever asks for the extra, and it
is loud rather than silent: pip answers <i>"Ignored the following versions that require a different
python version"</i> and names the constraint it could not satisfy. A dependency's floor does not
propagate to its host, so an extra could not have forced <code>boost-skill-cli</code> to drop 3.9
for users who never installed it — and which extras a CI leg installs is that leg's choice. "It
cannot be an extra" was a conclusion the evidence did not reach.

<i>What is now moot.</i> <code>requires-python</code> is <code>&gt;=3.12</code> and CI tests
3.12 / 3.13 / 3.14, so every interpreter boost supports clears all three packages with room to
spare.

So the decision rests on grounds the original argument never got to. A separately versioned
<code>boost-langchain</code> distribution still looks right, for a reason that has nothing to do
with Python versions: langchain majors move faster than boost does, and an extra drags that cadence
into boost's own lock files, <code>licenses</code> job and <code>pip-audit</code> job — a real cost
for a package whose value is being boring to install.

<b>There is a dependency conflict boost already owns — and the unpin this card prescribed does
not work yet.</b> The <code>[eval]</code> extra pins <code>langchain-core&lt;0.4</code>,
<code>langchain-community&lt;0.4</code> and <code>langchain-openai&lt;1</code>, because ragas 0.2.x
hard-imports a <code>ChatVertexAI</code> path that langchain ≥1.0 removed. This card originally
made the unpin phase 0 and blocked everything on it, on the measurement that <b>ragas 0.4.3
declares its langchain dependencies with no upper bound at all</b> (re-measured 2026-08-03,
still true). That measured the <i>declared</i> bounds and not the imports: installed beside
langchain 1.x (measured 2026-08-04), ragas 0.4.3's <code>llms/base.py</code> still does
<code>from langchain_community.chat_models.vertexai import ChatVertexAI</code> — the path
langchain-community 0.4.x deleted — so <code>import ragas</code> crashes. Upstream main already
carries the removal (zero <code>ChatVertexAI</code> hits in the repo), so the unpin becomes a
small follow-up the day ragas ships a release after 0.4.3.

What actually dissolves the conflict is the packaging decision made above for other reasons:
<code>boost-langchain</code> is a separately versioned distribution, so the langchain 1.x stack
lives in its own environment and its own CI leg while <code>[eval]</code> keeps its 0.3-stack
pins in its own. The two majors never co-install — pip refuses the combination loudly — and each
surface tests against the stack it really runs on. "Nothing else should be built until the unpin
lands" was wrong twice over: the unpin cannot land yet, and it was never the real gate.

<b>The existing rules still apply.</b> Nothing in the integration may be imported by the CLI or by
the required gate — the discipline <code>[eval]</code> already follows. It must degrade cleanly
without an API key, the way <code>embed.py</code> falls back Voyage → OpenAI → local
<code>bge-small-en-v1.5</code>; a key is a quality upgrade, never the entry fee. And it carries its
own tests without lowering the 80% coverage or 80% mutation floors.

<b>Delivery order.</b> Each phase is independently shippable.

<b>0 &middot; unpin.</b> Blocked upstream (see above): lands as its own small PR when ragas ships
a release after 0.4.3. The distribution isolation makes it a cleanup, not a prerequisite.
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
