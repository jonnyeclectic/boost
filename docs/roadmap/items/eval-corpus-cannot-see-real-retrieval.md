---
id: eval-corpus-cannot-see-real-retrieval
board: code
section: internals
status: inflight
category: Quality · Eval
complexity: M
impact: High
wow: 4
note: gate reports 1.000 while users get 0.720
order: 70
owner: loop/eval-corpus-falsifiable
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
<b>Half of the "also needed" already exists.</b> This card asks for queries that <em>only</em> body
text can satisfy, on the grounds that a name-graded set would greenlight deleting body indexing.
<code>tests/eval/golden-natural.jsonl</code> (shipped in <code>#360</code>) is 50 such queries: each
is written from its target's own <code>description</code> and has the target's distinctive
<b>name tokens deliberately stripped</b> &mdash; a mechanical check rejected five drafts that had
leaked one &mdash; so a surface-only index cannot answer them. It was written before any engine ran
against it and scored once, which is the same fitting-and-reporting discipline this group needs.

It corroborates this card's thesis from a second, independent direction. This card shows the gate
blind to <b>corpus size</b>: 1.000 on 23 taps against 0.720 on 83. The natural set shows it blind to
<b>query shape</b> on the <em>same</em> corpus &mdash; BM25 scores recall 1.000 / hit@1 0.780 on the
keyword golden set and <b>0.690 / 0.240</b> on natural-language queries over identical data. Two
different axes, same conclusion: the number the gate reports is not a number about retrieval.

What it does <b>not</b> fix is the corpus-size half, which is this card's own finding and remains
open &mdash; 50 queries over 6 taps cannot speak to an 83-tap install. The two are complementary
rather than overlapping, and combining them (natural-language queries over a realistically sized
corpus) is the instrument this group actually wants.

<b>Two of the three blindnesses are now closed, and the third was never true of the committed
harness.</b> <b>(1) recall-only flooring</b> is fixed: <code>--floor NAME=VALUE</code> is repeatable
and gates any metric, and <code>make eval</code> now floors all four &mdash; measured BM25 on the
pinned corpus is 1.000 / 0.780 / 0.860 / 0.895, with each floor about 0.12 under its measured value
so upstream drift cannot flake the build. A misspelled metric name is a hard error rather than a
silently skipped floor, since a floor that never fires is worse than no floor.

<b>(3) the kind oracle does not exist in <code>scripts/eval_retrieval.py</code>.</b> Checked
directly: every ranker &mdash; <code>catalog_ranker</code>, <code>bm25_ranker</code>,
<code>dense_ranker</code>, <code>hybrid_ranker</code> &mdash; is called with the query alone, and
there is no <code>kind=</code> argument anywhere in <code>scripts/</code> or <code>evals/</code>,
before or after <code>#360</code>. The golden set's <code>kind</code> field feeds the per-kind
<em>reporting</em> slices in <code>_aggregate</code> and nothing else, so the +0.073 figure quoted
above cannot have come from this harness. Recording it here rather than silently deleting the claim,
because the number was real in whatever script measured it.

<b>A defect the card did not predict:</b> the baseline was not keyed to the query set that produced
it. Running the natural-language set printed eight confident <code>REGRESSION vs baseline</code>
lines &mdash; BM25 recall 1.000&rarr;0.690, hit@1 0.780&rarr;0.240 &mdash; which were not
regressions but the gap between two different question sets, and <code>--save-baseline</code> on the
natural set would have silently overwritten the keyword set's numbers with them. Baselines are now
keyed by <code>name@content-digest</code>, so editing a query in place invalidates its baseline
rather than quietly re-grading against numbers that no longer describe it.

<b>Still open:</b> the corpus-size half (23 taps versus a real 83) and
<code>--regression-eps 1</code>, which is a symptom of the corpus tracking upstream HEAD rather than
pinned commits. Pinning <code>taps.txt</code> by commit SHA is the change that would make
regression-vs-baseline meaningful again; the absolute floors added here are drift-tolerant by
construction and do not depend on it.

