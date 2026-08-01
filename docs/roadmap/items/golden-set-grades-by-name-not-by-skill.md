---
id: golden-set-grades-by-name-not-by-skill
board: code
section: internals
status: inflight
category: Eval · Correctness
complexity: M
impact: High
wow: 4
note: 28 of 50 rows pinned mechanically with zero change to any number; 22 are genuine judgment calls
order: 81
owner: loop/golden-name-grading
pr: 412
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

<b>The mechanism ships; the judgment does not, and that split is deliberate.</b> A golden row may now
carry an <code>exemplar</code> &mdash; <code>"tap::skill_md"</code>, the entry the query was actually
written about. Grading then runs on that entry's <b>content class</b>: a byte-identical mirror from
another registry still counts, because refusing it would punish a correct answer for arriving from a
mirror, while a <em>different</em> skill sharing the name does not. Rows with no exemplar keep name
grading unchanged, so the two styles coexist during a migration.

<b>Backward compatibility is the property that had to hold, and it was verified rather than
asserted:</b> running the suite end to end after the refactor gives BM25 <code>hit@1</code>
<b>0.341</b>, against <b>0.340</b> published in <code>#373</code>. Nothing about the reported
numbers moves until an exemplar is added.

<b>Rankers now yield entries rather than names.</b> They could not decide the grading key themselves
once it became row-dependent, and the old <code>_dedupe</code> helper &mdash; whose own docstring
conceded &ldquo;grading is by name, so a repeat would otherwise be counted twice&rdquo; &mdash; is
replaced by <code>dedupe_keys</code>, which collapses mirrors under class grading and keeps
homonyms distinct so recall cannot count one hit twice.

<b>Exemplars fail loudly.</b> One naming an entry that is not indexed, or missing the separator,
exits with the offending string. Falling back to name grading on a typo would produce a quietly
weaker gate that still reports a number, which is the failure this card exists to end.

<b>What is left is 50 judgment calls, and they are not mine to make.</b> Choosing which of 59
<code>code-reviewer</code>s a query about reviewing a diff for security problems refers to is a
statement about intent. Guessing it would bake one opinion into the number the project publishes,
invisibly. The harness is ready for those decisions one row at a time; each added exemplar tightens
the metric and none of them destabilise it.

<b>Progress: 28 of the 50 rows are now pinned, and pinning them changed nothing.</b> Measured over
the SHA-pinned corpus, 28 rows have the property that every name in their <code>relevant</code> list
resolves to exactly <b>one body</b> &mdash; so the exemplar is a lookup, not a judgment, and grading
by content class must return the same verdict as grading by name. It does: the natural-language set
scores <b>0.350 / 0.160 / 0.245 / 0.259</b> before and after, identical to three decimal places.
That equality is the point of shipping them &mdash; the rows are now explicit about which skill they
mean, at zero cost to comparability.

<b>The remaining 22 are the real content of this card.</b> <code>code-reviewer</code> is 13 distinct
skills in this corpus, <code>update-docs</code> 10, <code>commit</code> 4. There is no shortcut
available: their descriptions share a median similarity of about <b>0.15</b>, so these are genuine
forks rather than one skill re-published, and no rule separates them without someone saying what the
question meant. The menu is generated rather than written down, because the candidate set is a fact
about the corpus that is tapped:

<pre>python3 scripts/eval_retrieval.py --golden tests/eval/golden-natural.jsonl --worksheet</pre>

<b>What unblocked this.</b> Not the judgment calls &mdash; [[eval-deduped-ranked-lists-by-name]].
A half-migrated set was averaging two different rank conventions, because name-graded rows collapsed
homonyms into one rank slot while exemplar-graded rows gave every distractor mirror its own. Until
both used one convention, migrating rows one at a time produced a number that meant nothing.
