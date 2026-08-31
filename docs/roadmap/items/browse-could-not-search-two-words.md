---
id: browse-could-not-search-two-words
board: code
section: dx
status: shipped
category: Bug · UX
complexity: M
impact: High
wow: 4
note: space was bound to select, so two words could never be searched for
order: 115
owner: feat/browse-tui
pr: 525
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

<b>A second pass on the interface, from a screenshot of the real thing.</b>
Rendering it against 60,047 live entries showed what synthetic fixtures could
not: six hues at once — cyan kinds, violet taps, pink matches, yellow
categories, green states — reading as confetti rather than as one surface. The
fix is Refactoring UI's first rule, that hierarchy comes from weight and colour
is added last for meaning only. The tiers are now bold / normal / dim, and the
palette is one accent (cyan) plus two semantics that earn their place: green for
installed, yellow for the curated star. Colour is layered <em>on</em> the tiers,
so a monochrome terminal keeps the whole hierarchy.

<b>Three affordances were missing, and each was invisible rather than absent.</b>
The detail pane could be focused and scrolled but said nothing about it — it now
brightens its border and captions itself <code>details · ↑↓ scroll</code>. The
match toggles could only be reached by <code>^T</code>, so a control you could
see but not walk to read as decoration — the arrow ring now includes them, and
left/right pick one while they hold focus. And installing dropped you back to
the shell after the first pick, which is the wrong shape for a browser: it
installs in place now, with the detail pane reporting
<code>◐ installing…</code> → <code>● installed</code> with the destination, or
<code>✗</code> with the reason.

<b>Installing in place introduced a race, and a flaky test caught it.</b> Two
Tab-selected skills installed in parallel threads, and every
<code>store.install</code> does a read-modify-write of
<code>.skill-lock.json</code> — so both landed on disk and one vanished from the
lock. It passed alone and failed three runs in five in the suite. Installs are
serial now, drained by one worker so the draw loop still answers keys, and the
regression test asserts on <em>overlap</em> rather than on the outcome, because
the outcome was right two times in five.

<b>The browser was also listing the same skill four times.</b> Registries
render one skill into <code>.claude/</code>, <code>.cursor/</code>,
<code>.gemini/</code> and a plugin root, and every copy got a row. Measured on
the real catalogue: <b>22,535 of 60,047 rows (37.5%) are duplicates of another
row</b>, so the list is now 37,512.

<b>Identity is the description, never the name — and that distinction is the
whole risk.</b> <code>code-reviewer</code> appears 75 times with <b>42 distinct
descriptions</b>, and <code>rule</code> 47 times with 47 distinct. Those are
different skills that happen to share a name, and collapsing them would hide
real results — the same mistake the eval scoring made once, crediting the ranker
with a compression that existed only in the scoring code.

<b>Two passes, and their value is wildly different.</b> Exact signature match
costs 34 ms and does 22,379 of the 22,535 collapses; the fuzzy pass at 95% costs
301 ms and merges the remaining 156. Nine times the cost for under half a
percent more. It stays because 95% is the stated contract and this runs once
when the browser opens rather than per keystroke — but the numbers are recorded
so whoever revisits it decides with data rather than a guess.

<b>Nothing disappears silently.</b> A collapsed row is badged
<code>×5</code>, the counter says how many are hidden, and <code>^D</code> shows
them all again. A browser that quietly drops a third of the catalogue and
reports a smaller total is indistinguishable from one with a broken filter.

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
