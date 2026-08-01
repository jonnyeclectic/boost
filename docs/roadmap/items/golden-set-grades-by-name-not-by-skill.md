---
id: golden-set-grades-by-name-not-by-skill
board: code
section: internals
status: planned
category: Eval · Correctness
complexity: M
impact: High
wow: 4
note: 35 of 53 golden targets are homonyms — code-reviewer is 79 copies across 59 different skills
order: 81
owner:
pr:
title: The golden set grades by name, and 35 of 53 names are ambiguous
---
<b>The eval scores a hit when the top result carries the right <em>name</em>. Most of those names do
not identify a skill.</b> Measured over a real 71,655-entry catalogue against the 50
natural-language golden queries: of the <b>53</b> distinct target names, <b>18</b> resolve to a
single body &mdash; harmless mirrors of one skill across registries &mdash; and <b>35</b> resolve to
<em>more than one</em>, which are genuinely different skills that happen to share a name.

The worst are not marginal. <code>code-reviewer</code> exists as <b>79 copies across 59 distinct
contents</b>. <code>skill-creator</code> is 77 copies / 30 contents, <code>frontend-design</code>
81 / 18, <code>commit</code> 40 / 25. In total <b>822 entries match a golden name, across 351
distinct bodies</b> &mdash; so roughly one in seven of the entries that can satisfy a golden query
is the one the query was written about.

<b>Why this is a correctness problem and not a rounding error.</b> A query graded against
<code>code-reviewer</code> scores a hit when any one of 59 different skills ranks first, including
ones that review a different language, target a different agent, or do something else entirely. The
metric therefore reports an <b>upper bound</b> on retrieval quality, and it is loosest exactly where
the catalogue is largest &mdash; the regime
[[eval-corpus-is-96x-smaller-than-a-real-install]] shows the gate never measures at all. Every
decision validated against it (blend weights, pool depth, whether a reranker earns its keep)
inherits that looseness.

<b>The fix is not mechanical, which is why this is a card and not a patch.</b> Grading by
<code>(tap, skill_md)</code> would measure what a user actually needs, and that key is already known
to be unique &mdash; <code>#366</code> moved the catalogue onto it for exactly this reason. But
retargeting the golden set means deciding <em>which</em> of 59 <code>code-reviewer</code>s a query
about reviewing a diff for security problems should be graded against. That is a judgment about
intent, not a lookup, and guessing it would quietly bake one opinion into the number the project
reports. Two defensible shapes: pin each golden row to a specific <code>tap</code> +
<code>skill_md</code>, or accept any entry whose body falls in a named <b>equivalence class</b>, so
mirrors still count and homonyms do not.

<b>What this does not claim.</b> It does not follow that retrieval is worse than reported in
proportion. A same-named alternative is often a perfectly reasonable answer, which is why the
eval's <code>relevant</code> field is a list rather than a single value. What is established is
that the number cannot <em>distinguish</em> the two cases, so it must not be read as precision
about the intended skill.

<b>Provenance.</b> Surfaced while measuring the scale falloff, where growing the corpus tap-by-tap
could not get below 51,657 entries without dropping a golden target &mdash; <b>119</b> taps ship a
skill matching one of these names. It also qualifies an earlier claim of mine: &ldquo;all 50 targets
are present&rdquo;, reported while diagnosing the static-embedding spike, was true but matched by
name, so it was weaker evidence than it read as.
