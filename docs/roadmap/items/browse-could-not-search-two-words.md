---
id: browse-could-not-search-two-words
board: code
section: dx
status: inflight
category: Bug · UX
complexity: M
impact: High
wow: 4
note: space was bound to select, so two words could never be searched for
order: 115
owner: feat/browse-tui
pr:
title: <code>browse</code> could not search for two words, and the fix reshaped the whole browser
---
<b>The bug was two lines.</b> <code>space</code> toggled multi-select, and the
printable range that fed the query started at 33 — one past space, deliberately.
So a space could never reach the filter, and <code>code review</code> was
unsearchable: you got whatever <code>codereview</code> matched, which is
nothing.

<b>Fixing it forced a decision rather than a patch.</b> Once space types, every
printable key must type — which took <code>i</code> (install) and
<code>q</code> (quit) with it. The keymap moved to what every other picker
uses: <code>↵</code> installs, <code>⇥</code> selects, <code>esc</code> quits.

<b>Space earns its place by meaning something.</b> The query tokenizes on
whitespace and <em>every</em> token must match, so typing more always narrows.
An <code>any</code> rule would make a second word widen the result set, which
reads as the filter breaking. <code>tdd driven</code> now finds
<code>tdd-workflow</code> with one token from the name and one from the
description.

<b>The logic moved to <code>core/browse.py</code>, which is the part that
matters for the next change.</b> A TUI whose rules live inside the draw loop
has no tests and no mutation coverage, because curses cannot be asserted on. A
layout integer can. Matching, pane geometry, the focus model and the detail
panel are now pure functions with 69 tests over them — and because the draw
helpers take <code>put</code> as a parameter, the frame itself renders into a
text grid, so "the box has four sides" is an assertion rather than a hope.

<b>That immediately caught a real defect.</b> The right-hand border never drew:
the clip bound was <code>x &lt; w - 1</code>, which makes the last column
unwritable, so the frame shipped with three sides. Also caught: the column
divider's <code>┴</code> landing on top of the help text and rendering
<code>esc quit</code> as <code>┴sc quit</code>.

<b>What the browser looks like now.</b> One framed surface — title rule, query,
scope radios, key hints — over a list pane and a detail pane divided by a rule.
The selected row highlights across its full width rather than by a marker
column. The detail pane carries what <code>boost info</code> would tell you
(kind, tap, path, file, installed state) plus the <em>entire</em> frontmatter,
scrollable with the arrows once <code>→</code> moves focus into it. Sorted keys,
no allowlist: an allowlist silently hides exactly the custom key a registry
author cared about.

<b>Arrows cross pane boundaries</b> instead of dead-ending, which is what makes
the query and the list feel like one surface: <code>↑</code> from the top row
lands on the query, <code>↓</code> comes back, <code>→</code> and
<code>←</code> cross into and out of the detail.

<b>Narrow terminals drop the detail pane rather than crushing it.</b> The first
thresholds (24/28) were guesses and looked it — at 58 columns they kept a
27-column list that ellipsised every description. Measured against the real row,
the minimums are 34 and 32, so 58 columns now gets one full-width readable list.

<b>It also got faster than what it replaces.</b> Searching the description as
well as the name is more text per entry, and the first cut cost <b>125 ms per
keystroke</b> over a 71,700-entry catalogue — slower than the 80 ms draw poll,
so the browser fell behind a typist. Two fixes, both measured: hoist the
haystack into a per-scope index built once (125→112 ms), then replace the
<code>all(ch in iter(hay))</code> subsequence test with one driven by
<code>str.find</code>, which scans in C instead of stepping a Python iterator
(112→<b>32 ms</b>, a 4.5x win on the inner loop, verified identical on every
input by a brute-force cross-check against the old implementation). The shipped
browser searched a shorter haystack and still cost 32–39 ms, so this is more
search for less time.
