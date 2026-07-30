---
id: eval-corpus-cannot-see-real-retrieval
board: code
section: internals
status: planned
category: Quality · Eval
complexity: M
impact: High
wow: 4
note: gate reports 1.000 while users get 0.720
order: 70
owner:
pr:
title: The eval gate reports a perfect score on a corpus 4× smaller than a real user's
---
<code>make eval</code> reports BM25 <code>recall@10 = 1.000</code> against the
pinned 23-tap corpus in <code>tests/eval/taps.txt</code>. Run the same script
against a real 83-tap install and it reports <b>0.720</b> — below the gate's own
0.85 floor — with <code>hit@1 0.407</code>, <code>MRR 0.526</code>,
<code>nDCG 0.566</code>, and <code>rule</code> the weakest kind at 0.500 recall /
0.286 hit@1. The gate has been advertising a perfect score while real-world
recall sits at 0.72, and it is blind in three separate ways:
<b>(1) recall-only flooring.</b> <code>--fail-under</code> gates
<code>recall@k</code> and nothing else, so a total <code>hit@1</code> collapse
from 0.780 to 0.000 would still pass.
<b>(2) regression detection is switched off.</b> <code>Makefile</code> passes
<code>--regression-eps 1</code>, which tolerates any absolute drop up to 1.0.
<b>(3) a kind oracle.</b> Grading per-row by the golden set's <code>kind</code>
field tells the retriever whether the answer is a skill, a rule or a workflow —
which <code>boost search</code> never knows unless the user passes
<code>--kind</code>. That single filter is worth +0.073 recall and +0.073 hit@1,
enough to flatter any change measured against it.
<b>The consequence is that no retrieval work in the repo is currently
falsifiable</b>, which makes this a hard prerequisite for every other item in
this group rather than a cleanup. Note the companion gate is in better shape:
<code>make evals</code> (<code>scripts/eval_gate.py</code>) already floors five
metrics and runs a paired bootstrap for significance — its limitation is corpus
size (57 entries, 1 tap), not metric design, so the work is to grow an
instrument that exists rather than to build one. Also needed: queries that
<em>only</em> body text can satisfy. The golden set grades items by name, so it
scores a surface-only index <em>above</em> the full-content one and would
cheerfully greenlight deleting body indexing altogether.
