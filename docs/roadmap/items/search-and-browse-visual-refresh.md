---
id: search-and-browse-visual-refresh
board: code
section: dx
status: inflight
category: UX · Design
complexity: M
impact: High
wow: 4
note: search rows learned kind/tap/installed with a stated drop order; browse got its gradient, an empty state, a badge rail, a list scrollbar and a session chip
order: 122
owner: feat/tui-visual-refresh
pr:
title: One design system across <code>search</code> and <code>browse</code>
---
<b>The brief was "make the CLI look good", and the answer was a design pass,
not a paint job.</b> Three design proposals (information-density, brand,
restraint) were judged into one spec with a doctrine budget: hierarchy from
weight, one accent, and exactly <em>one</em> gradient moment per screen.

<b>Search rows now answer the install decision.</b> A result was a meter, a
name and prose; it is now <code>meter · ●installed · name · [kind] · tap ·
description · ★ curated</code>, planned by a pure <code>out.search_layout</code>
with a stated drop order when narrow — tap first (provenance is the first
luxury), then prose shrinks, then the name cap tightens, then the kind column
goes. The meter's magnitude tint (cyan → violet → pink) was extracted to
<code>out.meter_hue</code> and named as the screen's one gradient moment; the
kind text comes from <code>out.kind_label</code>, the same source browse's
badges render, so the two surfaces can never disagree about what a workflow is
called. Every row is assembled by <code>out.format_search_row</code> — pure,
byte-stable under <code>NO_COLOR</code>, and property-tested to fit every
terminal from 40 columns up.

<b>The browser spent its budget on the top rule.</b> The gradient helpers had
sat unused in the draw path since the grayscale-first refactor; the top border
now runs cyan → violet → pink — on terminals that can render the real Aurora
hues. The 8/16-colour fallback keeps a single-hue rule, because cyan/magenta/
magenta reads as confetti, and monochrome keeps plain dim: the glyphs never
change, only their attributes.

<b>Four absences became affordances.</b> A zero-match filter drew nothing —
indistinguishable from a hung draw; it now says <code>○ no matches for '…' in
name</code> with the keys that widen the net. Badges started wherever the name
ended and wandered per row; they sit in a right-aligned rail that drops
least-important-first (the <code>×N</code> copies count last — nothing
disappears silently). A 70,000-row list had no scrollbar while the detail pane
did; they now share one geometry (<code>browse.scrollbar</code>). And installs
reported only inside the detail pane; the row's mark now cycles
<code>◐ → ● / ✗</code> from the same glyph table the pane uses, with a session
chip in the bottom rule (<code>✓ 2 installed</code>) whose precedence is
failed &gt; busy &gt; ok.

<b>The detail pane states the cost of Enter before it is pressed.</b> An
<code>installs</code> line names what lands where, by kind — for a rule that is
each agent's context file, the file the user reads every session, which is
exactly why it earns the line.

<b>Everything new is core logic under the mutation gate.</b> Twelve pure
helpers (four in <code>core/output</code>, eight in <code>core/browse</code>)
with boundary, drop-order, precedence and partition tests; the draw layer only
places what they return. Dead code left with the change: the six-hue
<code>_aurora_theme</code>, a duplicate subsequence matcher, and an unused
fuzzy filter.
