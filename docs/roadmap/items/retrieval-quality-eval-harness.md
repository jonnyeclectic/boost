---
id: retrieval-quality-eval-harness
board: code
section: health
status: shipped
category: Quality · Retrieval eval
complexity: M
impact: High
wow: 4
note: golden-set IR gate
order: 3
owner: eval/retrieval-harness
pr:
title: Retrieval-quality eval harness (Tier&nbsp;1 + rerank lift)
---
Boost's unit tests prove the retrieval math is <em>arithmetically</em> correct,
but nothing graded whether search returns the <em>right skill</em> for a real
question. This adds a golden-set harness — <code>tests/eval/golden.jsonl</code>,
43 <code>query&nbsp;&rarr;&nbsp;relevant&nbsp;skill(s)</code> judgments across
skills, rules and workflows — scored with rank-aware IR metrics
(<code>recall@k</code>, <code>hit@1</code>, <code>MRR</code>,
<code>nDCG@k</code>). Deterministic and offline, so it runs as a CI gate
(<code>make&nbsp;eval</code>, <code>--fail-under&nbsp;0.85</code>) beside
<code>make&nbsp;check</code> with a pinned baseline that flags regressions. The
first run earned its keep immediately, exposing a duplicate-name double-count
(recall&nbsp;2.7) fixed by deduping the ranked list. A three-way engine compare
proved BM25 full-content (0.919&nbsp;recall) decisively beats the frontmatter
heuristic (0.756), justifying the RAG stack. An opt-in, key-gated
<code>make&nbsp;eval-ai</code> arm reuses the same labels to measure the LLM
rerank lift — no judge needed — and confirmed rerank promotes the right skill to
#1 in 16% more cases (hit@1 0.605&nbsp;&rarr;&nbsp;0.767) at unchanged recall. A
Tier&nbsp;2b arm (<code>eval_recommend.py</code>, <code>make&nbsp;eval-rec</code>)
grades the <code>boost&nbsp;recommend</code> AI pick stage over golden project
stacks with a hard grounding gate: it found the AI picks statistically tied with
the heuristic on precision but <em>perfectly grounded</em> (0 hallucinated /
off-shortlist picks) — the honest verdict that this stage earns its place through
explanations and safety, not better ranking.
