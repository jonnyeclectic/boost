---
id: err-multiline-hint-colours-across-the-newline
board: code
section: planned
status: planned
category: UX · Bug
complexity: S
impact: Low
wow: 2
note: err() joins a multi-line hint's lines and then wraps the whole joined string in one c…
order: 207
owner:
pr:
title: <code>out.err</code>'s multi-line hint is coloured as one span, so line 1 ends with no RESET and lines 2+ carry no start code
---
<b>Measured.</b> With colour forced, a three-line hint from <code>err()</code> emits an opening <code>ESC[2m</code> on hint line 1 that is never terminated, two bare continuation lines carrying no SGR at all, and one closing <code>ESC[0m</code> at visible column 98 of the last line — so <code>boost index 2&gt;&amp;1 | head -2</code> under <code>CLICOLOR_FORCE</code> hands the consumer a stream ending inside an unterminated dim span; output.py:252 wraps the newline-joined body in a single <code>c(..., DIM)</code>, colouring first and splitting after.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>BOOST_COLOR=always .venv/bin/python -c "</code><br>
<code>from boost_cli.core import output as out</code><br>
<code>out.err('gh api failed', 'HTTP 401: Bad credentials\nTry authenticating with:  gh auth login\ngh: To use GitHub CLI in a GitHub Actions workflow, set the GH_TOKEN environment variable.')</code><br>
<code>" 2&gt;&amp;1 | /bin/cat -v</code><br>
<code># and the live call path (single-line tail in this sandbox, but proves err() is reached):</code><br>
<code>export HOME=$TMPDIR/audit-output-formatting; export BOOST_HOME=$HOME/.boost; mkdir -p "$HOME"</code><br>
<code>GH_TOKEN=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef BOOST_COLOR=always ./boost index 2&gt;&amp;1 | head -3 | /bin/cat -v</code>

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

The core defect and its byte shape reproduce exactly. Five stated details are wrong:

1. "<code>empty_state._block</code> (output.py:559-561)" — WRONG LINES. 559-561 is docstring prose. <code>_block</code> is defined at output.py:569 and its per-line colouring is at 571-572.

2. "the lone <code>^[[0m</code> is 90 columns into line 4" — WRONG. It sits at visible column 98. 90 is the length of the message text alone; the line also carries the 8-column <code> hint: </code> alignment indent.

3. "<code>err</code> is the one emitter that does not [colour per line]" — REFUTED. Handed a string containing a literal newline with <code>wrap</code> off, <code>dim()</code>, <code>warn()</code> and <code>empty_state()</code> all emit the identical straddling span (measured above). <code>empty_state._block</code> only colours per line of its *wrap* output; with <code>wrap=False</code> <code>body = [text]</code>, so the newline sits inside one <code>c(..., DIM)</code>. What is actually unique about <code>err</code> is that it is the only emitter whose docstring documents accepting embedded newlines and the only one with a live multi-line caller (<code>gh_failure_hint</code>); I grepped every <code>out.warn(</code> / <code>out.dim(</code> / <code>out.empty_state(</code> call site and none passes a <code>\n</code>-bearing string (all joins use ", " or "; ").

4. "<code>boost index 2&gt;&amp;1 | head -2</code> hands the shell an opening SGR with no close" — WRONG without a stated precondition.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Not carded — I re-checked independently. Grepped all <code>^title:</code> lines for colour/ANSI/reset/escape/SGR/dim/hint terms and read the four plausible cards in full: <code>long-hints-overflow-narrow-panes.md</code> (line width, not escape spans), <code>BOOST-D04.md</code> (semantic colour roles), <code>BOOST-D18.md</code> (empty-state/hint styling consistency), <code>BOOST-D27.md</code> (its three named remaining wrap-law gaps are <code>dim()</code>'s embedded indent, <code>empty_state()</code> adoption, and <code>truncate()</code>/<code>search_layout()</code> wide-char width — <code>err()</code> is not among them). <code>grep -ril 'unterminated|RESET|SGR|escape code' docs/roadmap/items/</code> returned 11 files, none about <code>err()</code>.

Scope of my repro, and what a card must not overclaim: - No corpus was needed; this is a pure library-call repro plus one live CLI path. The 20-tap eval corpus at $TMPDIR/eval-home is irrelevant here and I did not touch it. The <code>./boost index</code> run used its own disposable HOME. - I could not produce the 3-line <code>gh</code> tail live either: the sandbox proxy's TLS failure is a single line, so the live run only proves <code>err()</code> is reached with a <code>gh</code>-sourced hint, not that a 3-line tail occurred. The multi-line shape is proven by the direct call, which is what the finder also did. - A card must state the forced-colour precondition. In an ordinary interactive run the bytes ARE emitted (stdout is a TTY), but every terminal I know carries DIM across a newline, so it renders correctly — the finding concedes this. The only consumer that sees breakage is a line-oriented reader under <code>BOOST_COLOR=always</code> / <code>CLICOLOR_FORCE</code> (CI).

<b>Why it is worth doing.</b> Most terminals carry DIM across a newline, so it usually *looks* right — the harm is to anything reading a line at a time. <code>boost index 2&gt;&amp;1 | head -2</code> hands the shell an opening SGR with no close, dimming everything printed afterwards; and because the hint goes to stderr, any stdout written between hint lines lands inside the unterminated dim run. The module already knows the correct shape and uses it twice — <code>empty_state._block</code> (output.py:559-561) and <code>table</code>'s header cells (output.py:906-908, with the comment "a whole-line wrap would be cancelled at the first separator's RESET") both colour per line. <code>err</code> is the one emitter that does not.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
