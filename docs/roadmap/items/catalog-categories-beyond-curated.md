---
id: catalog-categories-beyond-curated
board: code
section: dx
status: planned
category: Catalog · UX
complexity: M
impact: Med
wow: 2
note: 487 registries carry 21 categories; the items themselves carry only a curated bool
order: 305
owner:
pr:
title: "Per-item categories in <code>search</code>/<code>browse</code>/<code>info</code> — not just a ★ curated bool"
---
From a user request: <em>&ldquo;proper categories for skills (can't have all of them listed as just
curated)&rdquo;</em>. They are right about the item level: the only taxonomy a catalog entry carries is
a boolean. A <code>boost search</code> row shows name, kind, tap, description and at most a
<b>★</b>; <code>boost recommend</code>'s no-match fallback is literally headed
<em>&ldquo;curated picks&rdquo;</em>; <code>boost info</code> prints no category at all. Across a
real install of tens of thousands of items, &ldquo;starred or not&rdquo; is the entire
classification a user can see or filter by.

What the code confirms. <code>catalog._make_entry</code> stamps <code>"curated": curated</code>
onto every entry (<code>boost_cli/core/catalog.py:119</code>, signature at 105&ndash;106) — and that
bool is per-<em>tap</em>, from <code>Tap.curated</code> (<code>core/registry.py:23</code>), set by
<code>tap --defaults</code> or by anyone passing <code>--curated</code>
(<code>commands/taps.py:126</code>) — a trust star, not a classification. Category-like data does
exist, but only per tap: <code>data/registries.json</code> rows carry one (487 registries, 21
values; <code>general</code> alone covers 127), and exactly two surfaces read it —
<code>browse</code>'s row badge via <code>_tap_categories</code>
(<code>commands/discovery.py:936&ndash;941</code>, whose own docstring says <em>&ldquo;catalog
entries themselves carry no category, only their tap does&rdquo;</em>; badge appended last in
<code>_row_badges</code>, discovery.py:961&ndash;963, so narrow panes drop it first, and taps
outside the bundled 487 get none) — and <code>boost serve</code>'s web facets
(<code>core/serve.py:65</code>). <code>cmd_search</code> renders only the star
(discovery.py:179) and takes no filter flag; <code>info</code> shows frontmatter tags when present
(<code>commands/info.py</code>, the <code>meta.get("tags")</code> kv) but no category, and its
<code>--json</code> has no such field. An item's own frontmatter <code>category</code>/<code>tags</code>
ride along invisibly in <code>entry["meta"]</code> and the substring <code>search_blob</code>
(catalog.py:131, 621&ndash;627), so they can match a query yet can never be displayed or filtered.

Proposed fix. Stamp a first-class <code>category</code> on each entry at scan time in
<code>_make_entry</code> (catalog.py:105&ndash;132): the item's frontmatter <code>category</code>
(or first tag) when declared, else inherited from its tap's registry category — and bump
<code>catalog.CACHE_FORMAT</code> so hundreds of existing tap caches backfill without a re-tap, per
the versioned-cache rule. Then surface it where a category would live: a badge in
<code>search</code> rows and a <code>--category</code> filter on
<code>search</code>/<code>browse</code>/<code>recommend</code>, a kv row plus JSON field in
<code>info</code>, and <code>browse</code>'s existing badge switched from tap-level to the entry
field (which also gives un-bundled taps' items a label for the first time). ★ keeps meaning
curation/trust only. Consumers must degrade cleanly when <code>category</code> is absent (old
caches, synthesised entries), same as the <code>content</code> digest rule.
Docs: regenerate <code>docs/commands.html</code> for the new flags; no other doc names categories.
Found by the 2026-08 CLI audit (cluster <code>catalog-categories-beyond-curated</code>, filed from
the user's request); repro in the audit log. Verified against source 2026-08-31.
