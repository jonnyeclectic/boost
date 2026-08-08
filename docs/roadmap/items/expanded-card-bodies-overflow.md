---
id: expanded-card-bodies-overflow
board: code
section: docsite
status: shipped
category: Docsite · Bug
complexity: S
impact: Med
wow: 3
note: the closed <code>&lt;details&gt;</code> was added for paint cost and is quietly also the only thing keeping long code tokens on the page
order: 99
owner: loop/langchain-retriever-contract
pr: 488
title: Expanded card bodies overflow the roadmap board sideways
---
<b>What happens.</b> <code>_body_html</code> wraps a card body in a closed
<code>&lt;details&gt;</code> only when <code>_SETTLED</code> matches, and
<code>_SETTLED</code> is the one-tuple <code>("shipped",)</code>. Every other status —
<code>inflight</code>, <code>planned</code>, <code>next</code>, <code>declined</code> —
renders its body inline and laid out. Card text is dense with <code>&lt;code&gt;</code>
spans, nothing in the stylesheet sets <code>overflow-wrap</code> on them, and the grid
track is <code>minmax(320px, 1fr)</code> — a floor that does not shrink. A single
identifier wider than the card pushes the track past that floor and the whole document
scrolls sideways.

<b>Measured.</b> At a 375px viewport the wrap column is 327px and the card's own content
box is 283px. Claiming <code>boost-first-rule</code> — flipping one item to
<code>inflight</code> — put its 43-character test-name identifier into a laid-out
paragraph and the sweep reported 34px of horizontal overflow on
<code>docs/roadmap.html</code>. Flipping it back to <code>shipped</code> cleared it,
because the token stopped being laid out at all.

<b>Why the board is green anyway.</b> By luck, not by rule. The six cards that render
expanded today top out at a 36-character token, which still fits. The shipped cards
behind closed <code>&lt;details&gt;</code> reach <b>113</b> characters — and a closed
<code>&lt;details&gt;</code> subtree is never laid out, so none of them can overflow
while they stay shipped. The collapse landed as a paint-cost fix, with real numbers
behind it (705ms of styleLayout over 6,316 elements). That it is also the page's only
defence against an unbreakable identifier is an accident nobody wrote down.

<b>Two ways it bites.</b> A claim is transient — a loop sets <code>inflight</code>, the
board can overflow for the life of the PR, and merging flips it to <code>shipped</code>
and hides the evidence, so the sweep goes red and green again for reasons no one
attributes correctly. A <b>decline</b> is not transient. A declined card is exactly the
kind that carries a long write-up of what was measured and why the answer was no, and it
stays expanded forever. Four sit on the board now.

<b>Why no gate stops it.</b> The sweep in <code>visual_check.mjs</code> does measure
this — document <code>scrollWidth</code> against <code>clientWidth</code>, at 375px,
on this exact page. But <code>visual</code> is not one of the required contexts, so a
red sweep never blocks a merge; and the status flip that fixes the symptom rides along
in the same PR that would have shown it.

<b>The fix is one declaration.</b> <code>overflow-wrap: anywhere</code> on
<code>.rcard code</code> lets a long identifier break rather than push, which is the
right behaviour for a card whether it is expanded or not. That demotes the collapse back
to what it was measured to be — a paint-cost optimisation — instead of load-bearing
layout. Worth pairing with a check that reads item bodies directly, since the only
reason the board passes today is that no unshipped card happens to hold a long enough
token.

<b>It stopped being hypothetical before it was fixed.</b> The card above predicted
this in the abstract; the next PR to claim an item walked into it. Claiming
<code>langchain-retriever-metadata-and-k-floor</code> put a 46-character test name —
<code>test_injected_provenance_is_machine_independent</code> — into a laid-out
paragraph, and the sweep reported <b>68px</b> of horizontal overflow on
<code>docs/roadmap.html</code> at 375px. That is the 36-character ceiling the card
measured, exceeded by ten characters, in the first PR that had reason to exceed it.
The <code>visual</code> workflow went red on both heads of that PR while every
required check stayed green — which is the "no gate stops it" paragraph above,
observed rather than predicted.

<b>Shipped as diagnosed, on both boards.</b> <code>.rcard code</code> and
<code>.ritem code</code> each carry <code>overflow-wrap: anywhere</code>.
<code>anywhere</code> and not <code>break-word</code> is the load-bearing half:
both break the glyph run, but only <code>anywhere</code> also shrinks the element's
min-content size, which is what lets a grid item in a
<code>minmax(320px, 1fr)</code> track reach the width the break makes possible.
<code>TestLongCodeTokensCanBreak</code> pins the declaration on both pages and, in a
second test, that the class it is scoped to is still the class the generator emits —
so a card rename cannot leave the boards unprotected behind a green test.
