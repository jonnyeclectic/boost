---
id: roadmap-page-weight-grows-without-bound
board: code
section: docsite
status: shipped
category: Docs · Performance
complexity: M
impact: High
wow: 2
note: it was never the bytes — 705 ms of styleLayout was, and 55.5% of elements now skip it
order: 76
owner:
pr:
title: <code>roadmap.html</code> grew 36% in one session and nothing bounds it
---
The generated board is <b>407.6&nbsp;KB, of which 404.7&nbsp;KB is markup</b> — 189
<code>&lt;article&gt;</code> cards rendered eagerly into one DOM. Measured across this session's
merges it went <b>301.6&nbsp;KB &rarr; 409.9&nbsp;KB, a 36% rise</b>, monotonically increasing with
every card documented.

<b>The mechanism is that shipped work never stops costing.</b> Sizing the sections: <code>shipped</code>
17.6&nbsp;KB / 16 cards, <code>next</code> 1.1&nbsp;KB / 1, <code>planned</code>
<b>383.0&nbsp;KB / 172</b> — but 164 of those 172 carry a <code>shipped</code> pill. They are finished
items grouped under their original section, each still rendering its full body, and those bodies grow
because closing an item well means recording what was measured and what turned out to be wrong. The
board is now mostly an archive that every visitor downloads in full.

<b>This is NOT what failed <code>lighthouse</code> on <code>#386</code>, and that is worth stating
because the correlation is seductive.</b> <code>#388</code> passed the same gate at
<b>409.9&nbsp;KB</b> — very slightly <em>larger</em> than <code>#386</code>'s 409.8&nbsp;KB, which
failed. A bigger page scoring better rules out page weight as that failure's cause; it was runner
variance, exactly as <code>lighthouse.yml</code>'s own comment predicts ("a single sample dips into
the 80s under runner load, which the median absorbs"). The performance floor is
<code>minScore 0.85</code> against a normal score of ~99–100, so there is real headroom today.

<b>The case for doing it anyway is the trend, not the current number.</b> At roughly +6&nbsp;KB per
merged card the page crosses 500&nbsp;KB within a few working sessions, and DOM size is precisely
what Lighthouse's performance category penalises — so this becomes the cause eventually even though
it is not the cause now.

<b>Likely levers, cheapest first.</b> Collapse shipped card bodies behind
<code>&lt;details&gt;</code> so the text ships but does not render — that alone addresses the
383&nbsp;KB block and keeps every word searchable in the source. Failing that, render shipped items
as one-line entries linking to their item file, or paginate by section. All three live in
<code>scripts/build_roadmap.py</code>; none require touching an item file, which matters because the
item files are the merge-conflict-free part of this design.

<b>Do not raise the Lighthouse floor to fix this.</b> The floor is calibrated and honest; a page that
outgrows it should be made smaller, not re-graded.

<b>Update &mdash; the prediction above came true, and the card's own headline claim is now false.</b>
This card argued page weight &ldquo;is <em>not</em> the cause now&rdquo; of any
<code>lighthouse</code> failure, and that it would become the cause eventually. Eventually arrived on
<code>#395</code>: <code>docs/roadmap.html</code> scored <b>0.74, 0.77, 0.81</b> against the
<code>minScore 0.85</code> floor &mdash; <b>all three runs below the floor</b>, not a single sample
dipping under load. The board was <b>433.7&nbsp;KB / 192 cards</b> at that point, against the
407.6&nbsp;KB / 189 recorded when this card was filed.

<b>The distinction that matters for whoever picks this up:</b> the earlier <code>#386</code> failure
really was runner variance &mdash; <code>#388</code> passed at a very slightly <em>larger</em> size,
which is what ruled weight out then. This one is not the same shape. <code>main</code> passed at
<b>430.0&nbsp;KB</b> one minute earlier on the same runner class, and <code>#395</code>'s
<em>best</em> of three runs was below <code>main</code>'s worst. So the honest reading is not
&ldquo;+3.7&nbsp;KB broke it&rdquo; &mdash; a 0.9% size change cannot move a score that far. It is
that the page now sits <b>on the cliff</b>, with roughly 0.07 of run-to-run spread straddling the
floor, so it fails intermittently and will fail more often as cards accrue. Headroom, not the mean,
is what was spent.

<b>This also raises the cost of documenting work well</b>, which is the uncomfortable part: closing a
card properly means recording what was measured and what turned out wrong, and every such paragraph
now pushes a shared gate closer to red. That is an argument for the <code>&lt;details&gt;</code>
lever rather than for writing less.

<b>Shipped &mdash; and the measurement corrected the card's own framing.</b> This item is titled for
page <em>weight</em>, and every earlier paragraph reasons about kilobytes. Reading the Lighthouse
artefact from the failing run shows bytes were never the mechanism. Of 1.6&nbsp;s of main-thread
work: <code>styleLayout</code> <b>705&nbsp;ms</b>, <code>paintCompositeRender</code>
<b>393&nbsp;ms</b>, <code>parseHTML</code> 83&nbsp;ms, <code>scriptEvaluation</code>
<b>20&nbsp;ms</b>. The page was slow because the browser <em>lays out and paints</em> 6,316 elements,
not because it downloads 440&nbsp;KB and not because of JavaScript.

<b>The weighted losses name the same thing.</b> Reconstructing the 0.74: TBT 0.58 &times; 30%, LCP
0.69 &times; 25%, FCP 0.47 &times; 10%, SI 0.93 &times; 10%, CLS 1.00 &times; 25% &rarr; 0.7365.
Worth noting <code>dom-size</code> scored <b>0</b> at 6,316 elements but is <em>unweighted</em> in
the performance category &mdash; so the obvious-looking number was not the one costing the score,
which is exactly the trap of optimising against a diagnostic instead of the metric.

<b>The fix is the cheapest lever this card already proposed, for a better reason than it gave.</b>
<code>build_roadmap.py</code> now wraps a <code>shipped</code> card's body in a closed
<code>&lt;details&gt;</code> &mdash; <b>188 of 192 cards</b>. A closed <code>&lt;details&gt;</code>
subtree still parses and still ships, so every word stays greppable and findable by the browser's own
find-in-page, but it is never laid out or painted: <b>3,764 of 6,781 elements (55.5%)</b> now skip
both. Anything a reader might act on &mdash; <code>planned</code>, <code>next</code>,
<code>inflight</code> &mdash; stays expanded.

<b>The page got bigger, and that is the point.</b> 440.3&nbsp;KB &rarr; <b>453.5&nbsp;KB</b>, because
188 <code>&lt;summary&gt;</code> elements cost ~13&nbsp;KB. Under the original framing that reads as
a regression; under the measurement it is irrelevant, because transfer was never what breached the
floor. Had this been fixed by chasing kilobytes, the work would have been aimed at the one number
the score does not weigh.

<b>Not claimed:</b> a resulting Lighthouse score. It could not be reproduced locally (no Chrome in
this sandbox), so the element count is the measured claim and CI's own <code>lighthouse</code> job is
the verdict.

