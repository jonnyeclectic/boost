---
id: a11y-sweep-flakes-on-color-contrast
board: code
section: internals
status: shipped
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

<b>Reproduction attempt: blocked on macOS, do it on a runner.</b> The pinned harness installs and
runs fine locally (<code>npm ci</code> with <code>npm_config_cache</code> redirected &mdash;
<code>~/.npm/_cacache</code> is not writable in the agent sandbox), and
<code>BOOST_CHROME_BIN</code> accepts
<code>/Applications/Google Chrome.app/Contents/MacOS/Google Chrome</code>. But every launch dies with
<code>The browser is already running for &lt;fresh profile dir&gt;</code>, on a
<em>newly created</em> <code>userDataDir</code> each time, because Chrome on macOS is a
single-instance app: launching the bundle binary attaches to the running instance instead of starting
an isolated one. Nothing to fix in the harness &mdash; it is why the reproduction loop belongs on a
Linux runner (or against Chrome for Testing), not on a developer laptop with Chrome open.

<b>Cause found &mdash; and my earlier &ldquo;maybe axe is right about the contrast&rdquo; caveat was
wrong.</b> It is a harness defect, and the harness predicted it in a comment.

<code>a11y_check.mjs</code> loads each page over <code>file://</code> and passes
<code>--allow-file-access-from-files</code>, with this note: &ldquo;without this Chrome treats each
file as its own opaque origin and the stylesheet never applies, <em>which would make every contrast
result meaningless</em>.&rdquo; That is exactly what happens intermittently. Every failing element
resolves its colour from <code>var(--text-3)</code>, defined once in
<code>style/boost.css</code> and linked <em>relatively</em> (<code>../style/boost.css</code>).

The arithmetic settles it. The shipped token is <code>#767c96</code>, which is
<b>4.85:1 on <code>#07080f</code> &mdash; passing AA</b>, and it was already raised once from
<code>#676d86</code> (3.9:1) by <code>#243</code>. The colours axe reported &mdash;
<code>#505467</code> on <code>roadmap.html</code>, <code>#656a81</code> on <code>mcp-hub.html</code>
&mdash; <b>appear nowhere in this repository</b>. They are Chrome's unstyled fallbacks. So both
&ldquo;contrast failures&rdquo; were the same defect: the stylesheet silently not applying.

<b>The fix is therefore not a colour and not a settle delay.</b> Both would be treating a symptom.
The real options are to stop depending on a flag that intermittently fails &mdash; serve the docs
over a throwaway <code>http://</code> origin for the sweep, or inline the stylesheet into a temporary
copy &mdash; and, more importantly, to <b>fail loudly when it happens</b>: assert that a known token
resolves before running axe at all, so an unstyled page reports &ldquo;stylesheet did not load&rdquo;
rather than twenty plausible-looking contrast violations against colours that do not exist.

That guard matters more than the flake. Without it the sweep produces confident, specific,
<em>entirely wrong</em> findings &mdash; which is what sent me to check a token that had been correct
for months.

<b>Reopened, then actually solved. Both of my earlier diagnoses were wrong, and the card records
them rather than quietly overwriting.</b>

The stylesheet-load theory in <code>#384</code> predicted that if the flake recurred the sweep would
report <code>page is unstyled</code>. It recurred on <code>#386</code> and reported <b>10 contrast
violations on a fully styled page</b> &mdash; so that prediction failed, exactly as the card invited.

What broke it open was a <em>third</em> phantom colour. Across three runs axe reported
<code>#505467</code>, <code>#656a81</code> and <code>#363948</code>, none of which exist anywhere in
this repository. A fixed browser fallback cannot drift. Measured against the real token
<code>#767c96</code>, those three sit at <b>44%, 72% and 20% of its luminance</b> &mdash; the
signature of one colour composited at varying opacity, not of three different colours.

<b>The cause is <code>.js .reveal</code>: <code>opacity: 0</code> transitioning to <code>1</code> over
600&nbsp;ms.</b> axe computes contrast from the composited pixel, so running mid-transition grades a
half-faded element. The failing nodes are <code>.count</code> spans inside
<code>&lt;section class="block reveal"&gt;</code>. My earlier &ldquo;no <code>.reveal</code> rule on
this page&rdquo; check was simply wrong: I grepped the <em>page</em>, and the rule lives in the shared
<code>style/boost.css</code>.

<b>The fix is one line, and the stylesheet was already prepared for it.</b>
<code>boost.css</code> carries a <code>prefers-reduced-motion: reduce</code> block forcing
<code>opacity: 1 !important</code> on <code>.reveal</code>; the sweep never asked for that media
feature. It now calls <code>emulateMediaFeatures</code> before navigating. That is better than
waiting out the animation, because it audits the page as a motion-sensitive user actually receives
it &mdash; a settle delay would have papered over a timing race while testing a state no user is
guaranteed to see.

The <code>#385</code> guard stays: it is orthogonal, it caught a real mis-assumption about
<code>commands.html</code> on its first run, and an unstyled page still deserves to fail loudly.

<b>Closed.</b> The cause is understood (reveal-animation compositing), the fix shipped in
<code>#388</code>, and the <code>#385</code> stylesheet guard stays as an orthogonal safety net.
Verified on <code>#388</code>: all seven pages ran the real axe check &mdash;
<code>a11y-check: OK &mdash; 7 pages clean</code> &mdash; including <code>docs/roadmap.html</code>,
the page that had failed on the two runs immediately before.

Worth keeping the trail: this card went through <b>three</b> wrong diagnoses before the right one
&mdash; a genuine contrast defect, then a stylesheet-load failure, then the animation. Each was
killed by measurement rather than argument, and the one that cracked it was noticing a
<em>third</em> phantom colour, because a fixed browser fallback cannot drift.
