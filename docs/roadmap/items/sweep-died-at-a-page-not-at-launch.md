---
id: sweep-died-at-a-page-not-at-launch
board: code
section: pipeline
status: shipped
category: CI · Bug
complexity: S
impact: High
wow: 4
note: the gate kept reporting failure after it had stopped checking a page and a half
order: 309
owner: fix/visual-page-too-large
pr: 839
title: The <code>sweep</code> gate died at a page, not at launch — and took six unrun checks with it
---
<b>The sequel to <code>#524</code>, and the mirror image of it.</b> That bug killed the
sweep at browser launch, before a single page loaded, so the coverage it cost was
obvious: all of it. This one killed the sweep <em>three quarters of the way through</em>,
which cost less and hid better.

<code>tests/visual/visual_check.mjs</code> captured a screenshot <b>before</b> it printed
the verdict, and captured it <b>unguarded</b>. So a diagnostic artifact could decide the
gate's fate — and it did. <code>docs/roadmap.html</code> is generated from
<code>docs/roadmap/items/*.md</code> and grows a card at a time; at 291 cards the
full-page capture at 1280px asked for more than Chrome will composite:

<code>ProtocolError: Protocol error (Page.captureScreenshot): Page is too large.</code>
at <code>async …/visual_check.mjs:182:5</code>

That is an unhandled rejection out of the <code>await</code>, so <code>node</code> died on
the spot.

<b>The red X was the cheap half.</b> The verdict for <code>docs/roadmap.html @1280</code>
had already been computed on the line above and was discarded unprinted, and the six
combinations queued behind it — <code>roadmap.html @1680</code>, and
<code>design-roadmap.html</code> at all five widths — never ran at all. The gate went on
reporting failure while it had quietly stopped checking a page and a half, and what it
reported was a screenshot error, which tells a reader nothing about the coverage that went
missing.

<b>Dated from the run history, not from memory.</b> <code>visual</code> was green on
<code>main</code> at <code>a37f7be5</code> (2026-09-09 01:13Z) and red at
<code>52b5adcd</code> (18:25Z) — the merge of <code>#836</code>, which added 41 cards.
Every run on <code>main</code> and on every branch failed from there, so it reddened every
open PR in the repo, which is how it was found.

<b>The fix restates the division of labour the file's own header already declares</b> —
<em>"Screenshots land in tests/visual/out/ for eyeballing; the exit code is the gate."</em>
Report first and capture last, so nothing after the verdict may decide whether a
page/width combination counts as checked; and capture inside a <code>try</code> that takes
no for an answer, falling back to the viewport shot the other four widths already take,
which cannot be too large.

<b>No pixel ceiling is hardcoded, deliberately — and the first green run proved why.</b>
The limit is Chrome's, it moves with the runner image, and a constant in this repo has to
be sourced. The harness asks for the whole page and records the refusal and the page's
measured height instead, so the number reaches the log rather than being rediscovered:

<code>note: docs/roadmap.html @1280 — full-page capture refused (Page is too large.); page is 151365px tall</code>

<b>151,365px.</b> The tempting fix was to clamp the capture at Chrome's documented
16,384px texture ceiling; that would have saved the top <b>10.8%</b> of the board and
filed it under the same name as a whole-page shot — a truncation nothing in the log would
have mentioned. Asking and taking no for an answer costs one refused CDP call and cannot
lie about what it captured. <code>console_check.mjs</code>,
in the same directory, already reasoned this way about a page it cannot load:
<em>"a third party going down must never redden a deploy check."</em> Same rule, pointed
the other way.

<b>What was verified, and what was not.</b> <code>make lint</code> is clean and the four
new tests are red against the old harness and green against the new one. The sweep itself
is <em>not</em> locally reproducible and this card says so rather than implying otherwise:
full Chrome cannot start under this macOS sandbox at all — ProcessSingleton cannot
<code>bind()</code> its socket, surfacing as the misleading <code>The browser is already
running for &lt;fresh profile dir&gt;</code> — exactly as <code>#524</code>'s card
recorded. CI is the verifier, and green means the closing
<code>10 pages × 5 widths clean</code> line, which is the proof the six unrun combinations
run again.

<b>The ratchet.</b> <code>tests/unit/test_visual_harness_capture.py</code> fails the build
if a capture sits outside a <code>try</code>, if the verdict stops preceding the capture,
if a refused capture is swallowed silently, or if one is counted as a render regression.
<code>#524</code> ended on the line this card has to repeat: the thing recording the risk
was a comment, and a comment cannot fail a build.
