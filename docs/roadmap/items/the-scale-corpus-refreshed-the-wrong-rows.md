---
id: the-scale-corpus-refreshed-the-wrong-rows
board: code
section: internals
status: shipped
category: CI · Evaluation
complexity: S
impact: High
wow: 5
note: 185 rows, 20 pinned — the monthly job moved exactly the 20 it did not own and pinned none of the 165 it existed to pin
order: 121
owner: loop/scale-refresh-freezes-required
pr: 537
title: the scheduled re-pin that refreshed the twenty rows it must not touch, and none of the hundred and sixty-five it existed to pin
---
<b>The Tier 1b scale corpus is the required corpus plus distractors</b> &mdash; 20 rows copied
verbatim out of <code>taps.txt</code>, pins and counts included, so both tiers start from the same
trees, plus 165 curated registries that make it the size of a real install. The golden floors were
calibrated against those 20 trees. A scale tier measuring a <em>different</em> snapshot of the same
repos reports a difference that is not scale.

<b>The monthly job did precisely the inverse of its job.</b>
<code>eval_corpus.py --refresh</code> walked every row of whatever file it was handed, so it moved
the 20 required pins &mdash; which <code>build_scale_corpus.py</code> owns and copies verbatim
&mdash; and, because <code>relock_text</code> skipped any row with fewer than two fields, pinned
<b>zero</b> of the 165 bare distractors. The tier that exists to measure a pinned 20,000-entry
corpus was floating on upstream HEAD for <b>89% of its rows</b>.

<b>It also could never merge.</b> The same workflow runs
<code>build_scale_corpus.py --check</code> one step <em>before</em> the refresh; the refresh then
broke exactly that check. Every PR it opened was unmergeable by construction, and the diff read as
ordinary pin movement &mdash; 20 SHAs and 20 counts, which is what a healthy re-pin looks like.
PR #536 is the specimen.

<b>Two mechanisms, both about a fallback being consulted too early.</b> The pins moved because
nothing said the required rows belong to another file. The distractors stayed bare because
<code>relock_text</code> gated on <em>&ldquo;does this row already have a pin&rdquo;</em> when the
durable rule is <em>&ldquo;never write a count without a SHA&rdquo;</em> &mdash;
<code>--relock</code> re-measures the same tree and has no SHA to offer, but <code>--refresh</code>
has just resolved upstream HEAD and can close the row. A third, quieter symptom fell out of the
first: the column width is the longest name being rewritten, and the distractor names are longer
than anything in <code>taps.txt</code>, so every required row was re-columned even where its pin had
not changed.

<b>Freezing is by membership, not identity.</b> <code>--refresh</code> on <code>taps.txt</code>
itself is exactly the job that <em>may</em> move those pins, so it freezes nothing. Freezing on
&ldquo;is this a required repo&rdquo; would have made the required corpus permanently unrefreshable
&mdash; the same bug pointed the other way, and far quieter.

<b>Verified against the real file, not argued.</b> Simulating a refresh that resolved a new SHA for
all 185 rows: the 20 required rows come back byte-identical, all 185 end up pinned, and
<code>--check</code> passes &mdash; so the PR is mergeable. The workflow now runs that check
<b>after</b> the refresh as well as before, which is the guard that was missing.
