---
id: recategorised-taps-never-reach-a-tapped-machine
board: code
section: dx
status: shipped
category: Catalog · Data
complexity: M
impact: Med
wow: 2
note: 46 registries out of general, 4 unregistered taps added, caches rescan on a moved category
order: 306
owner: loop/backfill-categories
pr: 1078
title: "A registry moved out of <code>general</code> never reached a machine that had already tapped it"
---
An item's <code>category</code> falls back to its tap's curated category, stamped at scan time. On a
real install with 468 taps, 16,538 of 61,786 entries (27%) read <code>general</code>, inherited from
127 registries filed there, and 297 more read nothing at all, because 6 tapped repos had no row in
<code>registries.json</code>. Fixing the data was not enough, though: <code>load_tap</code> only
rescans a cache whose <code>format</code> is old, so a recategorised registry kept its old label
on every machine until someone re-tapped it.
<br><br>
<b>Shipped:</b> each tap cache now records the <code>tap_category</code> it was scanned under, and a
cache whose value differs from today's registry data is stale the same way an old format is. It is
rescanned when the clone is present and served as-is when it is not, so every future
recategorisation reaches existing machines without bumping the format. The registry catalog read is
memoised on its stat stamp, since 468 parses per search measured 201 ms. Of the 131
<code>general</code> and unregistered repos, 46 were reassigned from the names of the items they
ship (a ≥70% single-domain threshold, with each batch checked adversarially). Four of the
unregistered taps were added with measured <code>est_items</code>; <code>sentry-agent-skills</code>
was left out because <code>getsentry/sentry-for-ai</code> already supersedes it. Because
<code>serve.entry_tags</code> derives its <code>topic:</code> tag from the same field, the tag facet
is backfilled too. Projected over that same install: <code>general</code> 16,538 → 12,677 entries,
uncategorised 312 → 59, <code>backend</code> 220 → 600, <code>agents</code> 1,032 → 2,121, <code>security</code> 722 → 1,014.
<br><br>
<b>Left open:</b> clusters with no category to go to, which stayed in <code>general</code>: science
(≈7 repos, including <code>K-Dense-AI/scientific-agent-skills</code>), mobile (≈4), finance,
product management, game development and media generation (3 each).
