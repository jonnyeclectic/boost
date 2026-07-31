---
id: a11y-sweep-flakes-on-color-contrast
board: code
section: internals
status: planned
category: CI · Flake
complexity: S
impact: Med
wow: 2
note: reds an unrelated PR, passes on rerun, cause unproven
order: 75
owner:
pr:
title: The axe-core sweep intermittently fails <code>color-contrast</code> on a page the PR never touched
---
The <code>sweep</code> job failed on <code>#373</code> with <b>20 violating node(s)</b> in
<code>docs/mcp-hub.html</code> — <code>[serious] color-contrast</code> on every
<code>.topic-tag</code>, reported as 3.57:1 (<code>#656a81</code> on <code>#0e0f16</code>, 8.3pt,
weight normal) against the 4.5:1 threshold. That PR touched <code>docs/eval.html</code> and the
roadmap items. It did not touch <code>mcp-hub.html</code>, its CSS, or anything either imports.

<b>It is a flake, and that much is established rather than assumed.</b> Four checks: the PR branched
from <code>170d52c</code>, and on that exact commit the same page <b>passes with 25 rules</b>;
<code>sweep</code> is green on all of <code>86163e0</code>, <code>4e22379</code>,
<code>088f1e2</code>, <code>678bbc2</code>, <code>93d82a6</code>, <code>584997d</code>,
<code>e6177a6</code>, <code>693601f</code> and <code>170d52c</code>; <code>axe-core</code> is pinned
at <code>4.12.1</code> through <code>npm ci</code> and a committed lockfile, so it is not dependency
drift; and <b>re-running the identical job passed</b> with no code change.

<b>The cause is NOT established, which is why this is a card and not a patch.</b> Two plausible
mechanisms were checked and both ruled out. Webfont loading: <code>--mono</code> is a pure system
stack (<code>ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace</code>), so there is
no font to wait for. Reveal animations: <code>mcp-hub.html</code> carries no <code>.reveal</code>
rule and no <code>IntersectionObserver</code>. A remaining hypothesis worth testing is that axe walks
ancestors to resolve an effective background, and a semi-transparent panel composited over the page
gradient resolves differently depending on paint timing — but that is a guess, and it should be
reproduced before anything is changed.

<b>Do not "fix" this by adding a settle delay and declaring it solved.</b> A
<code>document.fonts.ready</code> plus <code>requestAnimationFrame</code> wait is the obvious patch
and it may well work, but applied without reproducing the failure it papers over the symptom and
makes the next occurrence harder to read — the same trap as a tolerant lookup key that turns a loud
error into silent wrong behaviour. Reproduce first: loop <code>a11y_check.mjs</code> over
<code>mcp-hub.html</code> some tens of times on a runner and see whether the violation appears, then
fix what that shows.

<b>Why it is worth doing at all.</b> A required check that reddens on a file the author never opened
is worse than a slow one: the natural response is to dismiss it as noise, and the next real
<code>color-contrast</code> regression gets dismissed with it. Note also that 3.57:1 is genuinely
below AA — if the flake turns out to be axe correctly catching a contrast defect that it usually
<em>misses</em>, the fix is the token, not the harness.
