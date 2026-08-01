---
id: eval-corpus-is-96x-smaller-than-a-real-install
board: code
section: internals
status: planned
category: Eval · Correctness
complexity: M
impact: High
wow: 4
note: BM25 hit@1 is 0.340 on the pinned corpus and 0.040 on a real one
order: 80
owner:
pr:
title: The eval corpus is 96&times; smaller than a real install, and the floors describe the small one
---
<b>The required <code>eval</code> gate measures a catalogue almost nobody has.</b>
<code>tests/eval/taps.txt</code> pins 20 registries resolving to <b>743</b> entries. A real install
that has run <code>boost tap</code> a few times is far bigger &mdash; the machine this was measured
on carries <b>71,655</b> entries across 77 taps, <b>96&times;</b> larger.

<b>The gap changes the answer, not just the margin.</b> Over the same 50 natural-language golden
queries, BM25 scores <code>hit@1</code> <b>0.340</b> on the pinned corpus (published in
<code>#373</code>) and <b>0.040</b> on the 71,655-entry one. Both numbers are correct; they are
measurements of different things. The targets have not gone missing &mdash; all 50 are present, and
spot-checking puts them at rank <b>7</b>, <b>8</b>, <b>38</b> and <b>163</b> rather than rank 1.
What changed is the number of plausible distractors competing for the top slot.

<b>Why this matters more than a number moving.</b> The <code>eval</code> gate floors BM25 recall@k
at 0.85 and passes with wide margin, which reads as &ldquo;retrieval is healthy&rdquo;. It is
healthy <em>at 743 entries</em>. Every retrieval decision validated against that corpus &mdash;
blend weights, pool depths, whether a reranker earns its keep &mdash; is being validated at a scale
users leave behind after their third tap. The near-duplicate card predicted exactly this shape when
it warned the lift may <em>shrink</em> toward 50k rather than hold; this is that warning arriving
with a number attached.

<b>What is not being proposed.</b> Not lowering the floor, and not making the corpus enormous:
<code>ensure_eval_corpus.sh</code> already taps 20 repos over the network inside the
<code>lint</code> job, and a 77-tap corpus would make the required gate slow and flaky. The useful
shape is probably a <b>second, larger tier</b> &mdash; scheduled rather than required, floored on
its own baseline &mdash; so the small corpus keeps gating every PR cheaply while the large one
catches the scale effects the small one structurally cannot. Measuring <em>where</em> between 743
and 71,655 the metrics fall off would tell you how large that tier needs to be, and is a smaller
first step than building it.

<b>Provenance:</b> found while running the spike in
[[keyless-dense-tier-local-static-embeddings]], where the first sign was BM25 scoring 0.040 in a
harness that had to be checked for a bug before the number could be believed.
