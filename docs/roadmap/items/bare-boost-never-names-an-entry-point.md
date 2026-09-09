---
id: bare-boost-never-names-an-entry-point
board: code
section: planned
status: planned
category: Onboarding · Bug
complexity: M
impact: Med
wow: 3
note: A newcomer's first screen is 103 lines of 81 commands that is byte-for-byte the same …
order: 241
owner:
pr:
title: Nothing boost prints ever names an entry point: bare <code>./boost</code> is byte-identical on a virgin machine and a working one, and the one command its failure-hints route you to is the only setup …
---
<b>Measured.</b> Bare <code>./boost</code> is md5-identical (dd3c84b8d6510df1871bea5f1518fff4) on a machine with 0 taps and on the same machine with 7 taps and 1 installed skill, because <code>print_help</code> (cli.py:165-223) reads no state at all — and the command every newcomer-facing hint routes to, <code>boost tap --defaults</code>, produces exactly 7 lines whose last is a <code>✓ tapped …</code> row with no summary, while <code>boost install</code> through the same pipe closes with a framed "next: boost info brainstorming" box.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>export HOME=$TMPDIR/lens2-ep ; export BOOST_HOME=$HOME/.boost ; rm -rf "$HOME" ; mkdir -p "$HOME"</code><br>
<code># 1. the first screen: 103 lines, 81 commands, quickstart at line 80, no "start here"</code><br>
<code>./boost &gt; "$TMPDIR/h0.txt" 2&gt;&amp;1</code><br>
<code>wc -l &lt; "$TMPDIR/h0.txt"                                                        # 103</code><br>
<code>grep -n quickstart "$TMPDIR/h0.txt"                                            # 80:  quickstart   Tap the starter registries...</code><br>
<code>grep -ci 'start here\|new to boost\|first, run\|get started' "$TMPDIR/h0.txt"   # 0</code><br>
<code>head -4 "$TMPDIR/h0.txt"</code><br>
<code># 2. the only entry-point pointers are failure hints, and they name tap --defaults, never quickstart</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three sentences in the claim are false as written; the underlying defect survives all three.

1. "you must run a command that exits 1 to learn where setup lives" — WRONG. <code>boost doctor</code> exits <b>0</b> and carries the identical <code>boost tap --defaults</code> hint plus the verdict line "● ready to set up — tap a registry to make boost searchable". I measured DOCTOR_EXIT=0 (the claim's own evidence block also shows EXIT=0, contradicting its prose). The pointer is not gated behind a non-zero exit; it is gated behind running a diagnostic command, which is a weaker statement.

2. "every CLI hint routes to <code>tap --defaults</code> … never mentions that quickstart exists" — OVERBROAD. Two user-facing hints do name <code>boost quickstart</code>: <code>boost_cli/commands/discovery.py:398</code> ("<code>boost quickstart</code> taps the defaults and fetches their vectors in one pass", raised by <code>reindex --fetch-shards</code>) and <code>boost_cli/commands/pkg.py:981</code> ("<code>boost quickstart</code> taps the starters and loads their vectors in one pass", raised by <code>update --shards</code>). Correct figures: ~15 source sites name <code>boost tap --defaults</code> vs 2 that name <code>boost quickstart</code>, and <b>0 of the newcomer-plausible surfaces</b> (search, doctor, taps, browse, list, catalogbundle, mcp, serve) name quickstart. The substantive routing gap is real; the words "every" and "never" are not.

3.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Not carded — I re-checked independently over all 473 items. <code>audit-root-findings.md</code> (the bare-<code>boost</code> card) covers EPIPE exit 120, <code>help --help</code>/<code>help version</code> alias routing, and the launcher's 3.9 Python floor; its one <code>print_help</code> ask ("add one dim Options line under Usage") has shipped — I see the Options line. Nothing about state-awareness or a first-run pointer. <code>BOOST-D13</code> "Framed success summary with next step" is status:done, <code>ref: core/output.py:41 · commands/pkg.py</code>, and its body scopes itself to install/uninstall. <code>audit-tap-findings.md</code> (inflight, PR 772) is about path-shaped SPECs going to the network — zero hits for next/defaults/quickstart/summary. <code>audit-taps-findings.md</code> — zero hits for the same terms. <code>audit-quickstart-findings.md</code> covers unpinned-at-HEAD taps without <code>[rag]</code> and three divergent <code>[rag]</code> hint wordings, not routing.

Scope limits of my repro: - <code>boost quickstart</code>'s final line was verified by <b>source read</b> (<code>quickstart.py:220</code>, unconditional, immediately before <code>return 0</code>), not by running it — a live run fetches the shard manifest and would download vectors. I did not re-run the claim's <code>quickstart | tail -1</code> control. - <code>core/bootstrap.py</code> shows <code>boost mcp register</code> <b>auto-seeds</b> the catalog (taps the defaults unless <code>BOOST_NO_SEED</code>/<code>--no-seed</code>), and its docstring states "<code>boost mcp</code> is the only command a new user is told to run after installing". So an MCP-first newcomer is not stranded; this finding is specifically the <b>CLI-first</b> path.

<b>Why it is worth doing.</b> This is the whole first-value path and it costs a newcomer their first two commands. The productive path is 3 commands / 10.6s once you know it; the tool makes you discover it by failing. Worse, the two setup paths are not equivalent — README leads with <code>quickstart</code>, which pins taps to shard commits and can import prebuilt vectors, while every CLI hint routes to <code>tap --defaults</code>, which does neither and never mentions that quickstart exists. Both fixes are one line each: make <code>print_help</code> add a first-run line when <code>registry.list_taps()</code> is empty (it already resolves config at startup), and give the tap/registry success path the same next-step emitter <code>pkg.py</code> and <code>quickstart.py</code> already use.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
