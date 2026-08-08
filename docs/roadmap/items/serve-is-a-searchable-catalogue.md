---
id: serve-is-a-searchable-catalogue
board: code
section: dx
status: inflight
category: DX · Feature
complexity: L
impact: High
wow: 5
order: 108
owner: loop/serve-searchable-catalogue
pr: 492
note: the old page listed only what was installed — 147 rows out of 71,695 — with no search, no tags and no way to see what a tap actually is
title: <code>boost serve</code> becomes a searchable, faceted catalogue with a graph of the taps
---
<b>What it was.</b> A single dark table of the <em>installed</em> items and two JSON links.
On the machine this was measured on that is <b>147 rows out of 71,695</b> — the served page
could not show you 99.8% of the catalogue, could not search, and had no notion of a tag. The
one question a catalogue exists to answer, "what is out there and is any of it what I want",
was the one it could not take.

<b>Search reuses the ranker boost already has.</b> <code>catalog.search</code> is the scorer the
required <code>eval</code> gate floors at four metrics; the rows carry the same keys it reads, so
they pass straight through it. Writing a second scorer for this page would have made the
catalogue a third answer to a question <code>boost search</code> and the MCP surface already
answer — and the only one of the three nothing measures.

<b>Tags are facets, and they are namespaced.</b> <code>kind:</code>, <code>topic:</code>,
<code>state:</code>, <code>tag:</code>, <code>tap:</code>. The namespace is not decoration: filters
apply per namespace, and an unprefixed value makes a tap literally named <code>skill</code>
indistinguishable from the kind — which is the sort of collision a third-party registry gets to
choose for you. <code>topic:</code> comes from the curated taxonomy in
<code>registries.json</code>, which is decided from the names of the items a repo ships rather
than its README and is already pinned by
<code>tests/unit/test_registry_categories.py</code>; deriving a second one here would let the
page and <code>boost registries</code> disagree. Frontmatter <code>tags:</code> come through too,
and that field is third-party YAML — a list, a comma string and total junk are all common, so
<code>tags: {a: 1}</code> in one of hundreds of taps reads as "no tags" rather than blanking the
catalogue.

<b>The graph tab draws taps, not items.</b> A node per item is 71,695 nodes — unrenderable, and
it draws the one structure that is already a list two clicks away. A tap-level graph shows what a
table cannot: <b>which registries carry the same things</b>. <code>code-reviewer</code> ships from
thirteen different taps, and that overlap is the edge. Communities come from deterministic label
propagation (sorted iteration, ties on the lowest label) so the same catalogue always draws the
same picture — which is the property that makes the graph testable at all. A repeat <em>inside</em>
one tap is explicitly not an overlap: registries increasingly ship a copy per agent, so that is
the commonest shape in the catalogue and would otherwise bond every node to itself.

<b>And the payload is graphify's actual format, not a lookalike.</b> The first draft emitted
<code>{nodes, edges, stats}</code>, which resembles graphify's <code>graph.json</code> and is not
loadable by it: graphify writes <b>NetworkX node-link JSON</b> — <code>directed</code>,
<code>multigraph</code>, a graph-level attribute dict, <code>nodes</code>, and
<code>links</code> rather than <code>edges</code>, which is the one difference that breaks a
loader. Corrected after checking the real file rather than assuming, and verified by loading the
live 300-node payload with <code>networkx.node_link_graph</code>: <code>Graph named 'boost
catalogue' with 300 nodes and 900 edges</code>, graph attributes intact, 127 connected components.
So the tab that ships is one consumer and graphify, Gephi or a notebook are others.

That check also surfaced the thing the graph exists to show:
<code>awesome-codex-skills</code> and <code>awesome-skills-cn</code> share <b>867</b> item names,
and <code>buildwithclaude</code> and <code>claude-code-subagents-collection</code> share 720 —
invisible in any table, obvious as an edge.

<b>Both caps are stated rather than silent.</b> Measured: 300 nodes carry <b>5,181</b> overlaps and
55% of those are a single shared name, often a coincidence on a generic one. Everything drawn is a
hairball; the strongest 900 leave an average degree near six, which is a graph you can read. The
payload still reports the true totals (<code>overlaps</code>, <code>taps</code>,
<code>dropped</code>) and the tab prints them, because a cap you cannot see reads as "this is all
of it".

<b>Two things measurement changed.</b> Building the rows costs <b>0.54s</b> and facetting them
<b>0.12s</b> at real scale — and the search box issues a request per keystroke, so the first draft
was unusable at exactly the catalogue size that makes the feature worth having. Both are now cached
behind a fingerprint of the tap caches <em>and the lock file</em>: <code>boost install</code> in
another terminal changes the <code>installed</code> column without touching a single catalog cache,
so watching only the caches would have served a stale answer that looked live.

<b>No catalogue data is interpolated into the markup.</b> Rows arrive over <code>fetch</code>.
Descriptions and names are third-party text from whatever repos the reader has tapped, and one
containing <code>&lt;/script&gt;</code> closes an embedding block and turns the rest of the page
into markup it chose — the same class of defect as the 404 that echoed its request (#489). Not
embedding it removes the class rather than escaping around it, and it keeps the shell a constant
<b>17.8 KB</b> however large the catalogue gets.

<b>And nothing is fetched from anywhere else.</b> No CDN, no font, no remote script — pinned by a
test, because a catalogue that goes blank on a plane is not a local tool, and a page view that
tells a third party which port a developer's machine is serving on is not one either.

<b>The old page's guarantees moved rather than went away.</b> "A rule gets no raw-content link" is
now pinned on the two facts that enforce it — the row says which kind it is, and
<code>/skill/&lt;name&gt;</code> 404s for a rule whatever a client chooses to render.
