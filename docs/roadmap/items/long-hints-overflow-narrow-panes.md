---
id: long-hints-overflow-narrow-panes
board: code
section: dx
status: next
category: CLI · Output
complexity: M
impact: Low
wow: 2
note: 11 commands still emit prose hints past 80 columns; the worst is one string pinned by six test files
order: 126
owner:
pr:
title: The hints still run past the pane, and the worst one is pinned by six test files
---
<b>Measured, at <code>COLUMNS=80</code>, over 46 commands.</b> After the box and the help screen
were fitted, <b>11</b> still emit a line past 80 columns. Ranked:
<code>doctor</code>'s semantic-search hint at <b>127</b>; the AI-fallback notice at <b>101</b>,
which is one shared string surfacing in <code>explain</code>, <code>impact</code> and
<code>simulate</code>; <code>protocol</code>'s URL forms at 100; <code>changelog</code>'s
unshallow hint at 93; <code>who</code>'s footer at 87; <code>search</code>'s extra hint at 82;
<code>replay</code>'s footer at 81.

<b>Two of the eleven must be left alone.</b> <code>pulse</code>'s <code>source=</code> paths and
<code>fingerprint</code>'s hash are data, not chrome — clipping them destroys the information the
line exists to carry. So a blanket "no line exceeds <code>term_width()</code>" assertion is the
wrong gate: it would false-positive on exactly the lines that should be long. Pin the composed
sites individually.

<b>Why this is not a quick wrap.</b> The 101-column offender contains
<code>using the heuristic fallback</code>, which is asserted by <b>six</b> test files plus
<code>tests/bdd/features/explain.feature</code>. Wrapping inserts a newline mid-sentence and
breaks every one of them; and under pytest <code>term_width()</code> falls back to 80, so the
wrap fires in the suite rather than only on a narrow terminal. The change is a
<code>wrap()</code> helper in <code>core/output.py</code> — mutation-gated, so boundary-width
tests, not coverage — plus re-pinning those assertions. Shortening the strings instead is a
smaller diff but a voice decision, and the substring pinned by the tests would have to survive
either way.
