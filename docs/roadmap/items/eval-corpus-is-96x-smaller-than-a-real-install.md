---
id: eval-corpus-is-96x-smaller-than-a-real-install
board: code
section: internals
status: planned
category: Eval · Correctness
complexity: M
impact: High
wow: 4
note: measured the falloff — hit@1 0.420 at 53 entries, 0.020 at 60k, no plateau
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

<b>The falloff is measured now, which was this card's own proposed first step.</b> It asked where
between 743 and 71,655 the metrics fall off, on the grounds that knowing the shape is cheaper than
building a second tier blind. Holding the 50 natural-language golden queries fixed and growing the
corpus from one entry per golden name upward with random distractors:

<code>53 &rarr; <b>0.420</b></code> &middot; <code>253 &rarr; 0.380</code> &middot;
<code>753 &rarr; 0.240</code> &middot; <code>2,053 &rarr; 0.220</code> &middot;
<code>6,053 &rarr; 0.080</code> &middot; <code>20,053 &rarr; 0.040</code> &middot;
<code>60,053 &rarr; <b>0.020</b></code>

<b>There is no plateau, and that is the answer.</b> <code>hit@1</code> decays continuously &mdash;
roughly halving for every 4&times; the corpus grows &mdash; rather than degrading to some floor a
larger fixed corpus would capture. So &ldquo;pick a bigger number for the second tier&rdquo; has no
principled stopping point; what the gate can honestly claim is bounded by the size it measures, and
that size is ~750 while users run 10&ndash;100&times; more. A scheduled tier is still worth having,
but it should be described as <em>a</em> scale rather than <em>the</em> scale.

<b>A second finding fell out of the method, and it complicates the metric itself.</b> The first
attempt grew the corpus tap-by-tap and could not get below <b>51,657</b> entries while keeping every
golden target present &mdash; because <b>119 separate taps</b> ship a skill matching a golden name.
Names like <code>review</code>, <code>commit</code> and <code>why</code> are not identifying. So
<code>hit@1</code> graded <em>by name</em> counts a hit when any of 119 same-named skills lands
first, which flatters the metric at scale exactly where it looks worst. Grading by
<code>(tap, skill_md)</code> would measure what a user actually needs; that is a bigger change than
this card, and worth its own.

<b>Stated limits.</b> BM25 IDF still comes from the full index rather than being recomputed per
subset, so these are the ranking effects of added <em>candidates</em>, not a byte-exact simulation
of a small install. Distractors are sampled uniformly from real entries rather than composed as a
plausible tap set. And n=50, so one query is &plusmn;0.02 &mdash; the endpoints are far apart enough
to carry the conclusion, the middle steps are not individually significant.

