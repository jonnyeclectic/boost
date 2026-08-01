---
id: eval-deduped-ranked-lists-by-name
board: code
section: internals
status: shipped
category: Eval · Correctness
complexity: M
impact: High
wow: 4
note: 13 different skills named code-reviewer shared one rank slot — where "recall is 1.000" came from
order: 83
owner: loop/eval-dedup-by-body
pr: 411
title: The eval de-duplicated its ranked list by name, so homonyms shared a rank
---
<b>A grade key does two jobs, and they needed different answers.</b> It decides whether an entry is
<em>relevant</em>, and it is the <em>identity</em> the ranked list is de-duplicated on. Both were the
entry's name &mdash; so the thirteen genuinely different skills called <code>code-reviewer</code> in
the pinned corpus collapsed into <b>one rank slot</b>, and every metric was computed over a list
about a third shorter than the one a user would scroll.

<b>This is not a rounding error dressed up.</b> It credited the ranker with a compression that exists
only in the scoring code. Measured over the pinned corpus, de-duplicating on the content hash instead
moves BM25 recall@10 from <b>0.863 to 0.852</b> &mdash; roughly one golden query &mdash; and over the
six-repo minimal set from <b>1.000 to 0.978</b>. That second number is the interesting one: it is
where the project's &ldquo;retrieval recall is 1.000&rdquo; folklore came from. The corpus never had
perfect recall; it had a scoring key that merged wrong answers into right ones.

<b>Exemplar rows had the mirror-image bug.</b> When a row pins an exemplar, its <em>distractors</em>
were keyed on <code>tap::skill_md</code> &mdash; so two byte-identical mirrors of a distractor each
took a slot and pushed the target later. The two bugs pointed opposite ways, which meant an
exemplar-graded row and a name-graded row could not honestly be averaged into a single number. That
blocked finishing [[golden-set-grades-by-name-not-by-skill]], whose whole design is that rows migrate
one at a time.

<b>The fix separates the two jobs.</b> Relevance is decided by name, or by content class when the row
pins an exemplar &mdash; unchanged, so a multi-name <code>relevant</code> list still needs each
distinct name found. Identity is always the entry's content hash: mirrors of one skill collapse
(counting them twice rewards nothing), distinct bodies do not (a user really does see thirteen
entries). One convention for every row.

<b>What this does not fix.</b> The corpus is still 10,152 entries against a real install's far
larger one &mdash; see [[eval-corpus-is-96x-smaller-than-a-real-install]] &mdash; and the golden set
still grades 22 of its 50 natural-language rows against a name that resolves to several different
skills. This makes finishing that migration possible; it does not finish it. The corrected floors are
comfortably clear of the gate (recall 0.852 against 0.78), so no threshold moved.

<b>Provenance.</b> Found while working out how to add the remaining exemplars: the blocker turned out
not to be the 22 judgment calls but the fact that a half-migrated set would average two different
rank conventions. Measuring that is what exposed the name-collapse underneath it.
