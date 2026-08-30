---
id: dense-reindex-reuses-whole-taps
board: code
section: internals
status: next
category: Search · Performance
complexity: M
impact: High
wow: 3
note: one changed file re-embeds 29 min for 1.9 s of new text
order: 126
owner:
pr:
title: "Dense reuse is per <em>tap</em>, so one changed file re-embeds the whole registry"
---
<code>dense.build</code> decides reuse by comparing each tap's recorded commit against its current
one, and everything below that granularity is re-done from scratch:
<code>_delete_taps</code> is <code>DELETE FROM chunks WHERE tap = ?</code>, and <code>fresh</code>
collects <b>every entry of any tap whose commit moved</b>. So a one-character fix upstream costs that
registry's entire distinct chunk set.

<b>The incremental path is excellent when nothing moves and terrible when something does.</b> Measured
on a real 464-tap / 63,003-entry / 657,587-chunk install (keyless local
<code>BAAI/bge-small-en-v1.5</code>, 384-d, ~21 texts/s single-core):

full cold build <b>5 h 28 m</b>;<br>
<code>reindex --dense</code> with nothing changed <b>26.6 s</b>;<br>
worst single tap re-embed <b>29 m 13 s</b> &mdash; for <b>&le;1.9 s</b> of genuinely new text.

That last figure is the defect in one line. The corpus is brutally skewed:
<code>lingxling/awesome-skills-cn</code> alone is <b>123,471 chunks (18.8%)</b>, the top ten taps carry
<b>47.2%</b>, and the median tap is <b>349 chunks (~17 s)</b>. So the cost of an update is decided
almost entirely by <em>which</em> registries happened to push.

<b>And they push often.</b> Measured 6.56 h after tapping all 464 at HEAD: <b>19 taps had already
moved</b> &mdash; 4.1% of taps but <b>17.0% of chunks</b>, because drift is weighted toward the big,
active registries. Re-running at that point costs <b>61&ndash;68 min, 20.9% of the full
build</b>, to absorb a few hours of upstream commits &mdash; and ~99% of that is embedding: deleting
and re-inserting all 112,081 rows on a copy of the real 1.65 GB store measured <b>2.7 s</b>, a full
464-clone rescan <b>12.7 s</b>.

<b>The amplification, counted exactly.</b> Those 19 taps are 64 commits and 967 changed files ahead.
Exactly <b>39</b> of those files map to an indexed catalog entry, and those entries own <b>659
chunks</b>. Boost re-embeds <b>112,081</b>. That is <b>170&times;</b> more work than the change.

<b>Worse: 40% of it is bots.</b> <b>10 of the 19 moved taps changed nothing boost indexes at all</b>
&mdash; no SKILL.md, no rule file, no Markdown under commands/agents/workflows. They moved on badge
JSON, star-history SVGs, CI YAML and e2e TypeScript, and they cost <b>44,866 chunks = 40.0% of the
incremental bill</b>, about <b>37 of the 68 minutes</b>. <code>davila7/claude-code-templates</code>
alone re-embeds all <b>18,566</b> of its chunks because four dashboard JSON files changed.
Entry-level digests take that 40% to <b>zero</b> without a special case, which is most of the argument
for doing it.

<b>And the advantage decays with cadence</b> (distinct-text counts per scenario at the measured
19.92 texts/s): 6.9 h &rarr; 21%, 1 day &rarr; 33%, <b>7 days &rarr; 52&ndash;58%</b>, 30 days
&rarr; 72% of a full rebuild. A weekly refresh buys under 2&times;. Part of that is a dedup collapse:
the whole corpus is 39.66% duplicate text, but <em>within</em> the 19 moved taps only 27.21%, so
effective throughput falls 33.5 &rarr; 27.4 chunks/s.

<b>The fix does not need new identity machinery.</b> A catalog entry already carries
<code>content</code>, a truncated sha256 of name + description + body stamped by
<code>catalog._content_digest</code> at scan time and pinned byte-identical to what
<code>rag.read_body</code> assembles by <code>tests/unit/test_content_identity.py</code>. On a commit
change, diff the tap's entries by that digest and delete + re-embed only the ones that actually moved.
A registry that reorganised files, bumped a README or touched one skill then costs one entry rather
than 123,471 chunks. Deletion stays tap-scoped underneath, so the constraint that
<code>chunks.tap</code> is what scopes removal is unaffected.

<b>Content-keyed vectors were measured and declined.</b> The obvious neighbouring idea &mdash; hash each
chunk's text, look it up before embedding, skip on a hit &mdash; sounds like it should erase the
corpus's 39.6% duplicate rate. It does not, because <code>_embed_and_store</code> already dedupes
<code>order</code> <em>within the fresh set</em>: on a cold build every duplicate is already collapsed,
so content keying saves <b>0</b>. Only text shared with the <em>unchanged</em> taps is recoverable:
measured on the real moved set, <b>11,501 of 81,580 distinct texts = 14.1%</b>, worth <b>9.6 min of
the 68</b> &mdash; against ~60&ndash;120 lines in <code>dense.py</code>
plus a schema change, an <code>INDEX_VERSION</code> bump and a wrong-vector failure mode that is silent.
Recorded so the measurement is not re-litigated; per-entry granularity is where the win is.

<b>Related gap: a tap pin cannot be set after tapping.</b> <code>registry.pin</code> /
<code>unpin</code> exist (<code>registry.py:398</code>/<code>410</code>) and <code>registry.update</code>
already honours them &mdash; <em>&ldquo;A pinned tap is skipped unless <code>force</code>, which also
clears the pin&rdquo;</em> &mdash; but the only way to set one is <code>boost tap --at &lt;SHA&gt;</code> at
creation, and <code>add()</code> raises <code>"tap %s is already configured"</code>.
<code>boost pin</code>/<code>unpin</code> are in the <code>pkg</code> group and pin <em>skills</em>, not
taps. So freezing the registries responsible for most of the re-embed cost is impossible on an
existing install without untapping. Exposing the pin that already works is the cheapest lever here and
worth landing first &mdash; measured, pinning just <code>jeremylongshore/claude-code-plugins-plus-skills</code>
and <code>davila7/claude-code-templates</code> removes <b>75,227 of 112,081 moved chunks = 67.1%</b> of
today's incremental cost, and <code>davila7</code> changed nothing boost indexes.

<b>Shards do not cover this case.</b> Of the 19 moved taps exactly one appears in the published
manifest, and its shard is pinned at the commit the tap just left, so <code>import_shard</code>
refuses it. Net importable for this reindex: <b>0 of 112,081 chunks</b>.
