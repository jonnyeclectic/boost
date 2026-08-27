---
id: long-hints-overflow-narrow-panes
board: code
section: dx
status: inflight
category: CLI · Output
complexity: M
impact: Low
wow: 2
note: a code span is one atomic token, so a hint folds to the pane without splitting the command it tells you to run
order: 126
owner: loop/wrap-long-hints
pr:
title: The hints still run past the pane, and the worst one is pinned by six test files
---
<b>Measured, at <code>COLUMNS=80</code>, over 46 commands.</b> After the box and the help screen
were fitted, <b>11</b> still emitted a line past 80 columns. Ranked:
<code>doctor</code>'s semantic-search hint at <b>127</b>; the AI-fallback notice at <b>101</b>,
which is one shared string surfacing in six places; <code>protocol</code>'s URL forms at 100;
<code>changelog</code>'s unshallow hint at 93; <code>who</code>'s footer at 87;
<code>search</code>'s extra hint at 82. A re-measure while claiming this found a twelfth the
first pass missed — <code>simulate</code>'s quoted trigger line at <b>97</b>, which clips the
description to 100 <em>characters</em>, a length rather than a width.

<b>Two of them must be left alone.</b> <code>pulse</code>'s <code>source=</code> paths and
<code>fingerprint</code>'s hash are data, not chrome — clipping them destroys the information the
line exists to carry, and a hash broken across two lines cannot be compared by eye. So a blanket
&ldquo;no line exceeds <code>term_width()</code>&rdquo; assertion is the wrong gate: it would
false-positive on exactly the lines that should be long.

<b>What shipped: a code span is one atomic token.</b> <code>out.wrap()</code> is a greedy word
wrap in which a backticked span is a single unbreakable unit even though it contains spaces,
because the spans in these hints are shell commands the user is meant to select and paste. That
is the whole reason this is not two lines of <code>textwrap</code>: <code>doctor</code> and
<code>search</code> both interpolate <code>dense.fix_hint()</code>, whose answers end in
<code>pip install 'boost-skill-cli[rag]'</code>, and a wrap that splits it hands the user a
command that does not run. A token wider than the pane is emitted whole and overflows — one long
line the terminal soft-wraps still yields the right text on a copy, which a bisected one does not.
<code>search</code> already wrapped, with a comment conceding it relied on a test that no
<code>_FIX</code> entry holds an over-long token; the span rule makes that structural. It also
wrapped to the <em>full</em> width and then let <code>out.info</code> indent by two, which is
precisely the 82.

<b>Wrapping is opt-in per call site, and that is the design.</b> <code>warn</code>,
<code>info</code>, <code>dim</code> and <code>kv</code> take <code>wrap=True</code> and each pays
for its own prefix — the marker, the indent, the key column — so continuations align under the
message rather than folding back to column zero. Always-on wrapping would have folded the two
data lines this item exists to protect.

<b>Two claims in the first draft of this card did not survive measurement.</b> It said the
101-column offender was pinned by <b>six</b> test files; only <b>one</b> pins it verbatim
(<code>test_ai_fallback_note_verbatim</code>, the mutant-killer, which wraps at the <em>emission
site</em> and so was never touched). The other five pin the substring
<code>using the heuristic fallback</code>, and are re-pinned against whitespace-collapsed output —
an idiom <code>test_cli_discovery.py</code> had already established, for this exact reason. The
BDD feature got a separate <code>should contain wrapped</code> step rather than collapsing inside
<code>the output should contain</code>, which eleven feature files use ~87 times.

<b>Result: eight overflowing lines became two, and the two are the data lines.</b> The gate splits
the commands by whose words are on the line — <code>search</code>, <code>who</code> and
<code>protocol</code> compose their whole output and are swept down to 40 columns; commands that
quote a skill's own rules are swept at 80 and wider, because reflowing someone else's prose is a
different decision from fitting boost's own hints.

<b>Still open, found by the new gate rather than by this card.</b> At 40 and 60 columns
<code>doctor</code>'s <code>·</code>-joined status summaries run to 71, and
<code>protocol</code>'s <code>try it:</code> example is a single 59-column command that cannot
fold. Neither is in this item's scope — both are recorded here so the next pass does not
rediscover them as new.
