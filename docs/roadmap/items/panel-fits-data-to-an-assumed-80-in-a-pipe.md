---
id: panel-fits-data-to-an-assumed-80-in-a-pipe
board: code
section: planned
status: planned
category: UX · Bug
complexity: S
impact: Low
wow: 2
note: output.panel computes room = term_width() - 4 (output.py:527) and clips its content t…
order: 219
owner:
pr:
title: <code>out.panel</code> still fits its content to <code>term_width()</code>, so <code>boost count | …</code> clips the line to an assumed 80 columns
---
<b>Measured.</b> On this machine <code>./boost count | cat</code> renders the 110-character inventory summary into an 80-column box, clipping the content to 76 columns and dropping the 34-character tail "0 taps) · discovery index not built", while <code>COLUMNS=300 ./boost count</code> prints all 110.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>F=$TMPDIR/panel-fixture; rm -rf $F; mkdir -p $F/skills/alpha-skill $F/commands $F/.cursor/rules</code><br>
<code>printf -- '---\nname: alpha-skill\ndescription: A demo skill.\n---\n# Alpha\n' &gt; $F/skills/alpha-skill/SKILL.md</code><br>
<code>printf -- '---\nname: beta-workflow\ndescription: A demo workflow.\n---\nRun it.\n' &gt; $F/commands/beta-workflow.md</code><br>
<code>printf -- '---\ndescription: A demo rule.\n---\nAlways do it.\n' &gt; $F/.cursor/rules/gamma-rule.mdc</code><br>
<code>(cd $F &amp;&amp; git init -q . &amp;&amp; git add -A &amp;&amp; git -c user.email=a@b -c user.name=a commit -qm init)</code><br>
<code>export HOME=$TMPDIR/panel-home; rm -rf $HOME; mkdir -p $HOME; export BOOST_HOME=$HOME/.boost BOOST_NO_AI=1 BOOST_ASSUME_YES=1</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Three stated widths are wrong; the defect itself reproduces exactly.

1. "The piped box is 78 columns wide" → it is 80. room = term_width()-4 = 76, <code>_clip_visible</code> fills to exactly 76 display columns (ellipsis included), box = inner + 4 = 80. 80 is the only value reachable once clipping fires; 78 is not.

2. "piped 81 (clipped at 76 + ellipsis)" → the piped box row is 80 columns and the content is clipped to 76 columns TOTAL, i.e. 75 chars plus the ellipsis. "76 + ellipsis" would be 77 and is not what <code>_clip_visible</code> does.

3. "full line 114 chars" → 114 is the rendered box ROW in display columns; the summary TEXT is 110 chars. State which one. The lost tail is 34 chars, ~31% of the line.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

Scope of my repro, and things a card author must not get wrong:

1. Only <code>count</code> loses UNIQUE data. I verified the install panel clips too (<code>→ claude-code · win…</code>), but the <code>✓ linked → claude-code · windsurf · cursor · antigravity</code> status line printed immediately above it is unclipped, so nothing is actually lost there. <code>panel</code> is a third EMIT site of the root cause but <code>boost count</code> is the only DATA-LOSS site. Do not inflate install/uninstall into a second loss site.

2. <code>boost count --json</code> is an unclipped machine-readable path, so a script has an escape hatch. That plus (1) is why Low is right.

3. The <code>installed 47 (40 skills · 1 rule · 6 workflows)</code> figure comes from the REAL HOME's lockfile, not the eval corpus — BOOST_HOME does not move the skills store. Only <code>10152</code> / <code>20 taps</code> are the corpus's. Do not attribute 47 to the corpus in a card.

4. I did not run <code>boost count</code> against the shared $TMPDIR/eval-home. I copied <code>config.json</code> + <code>cache/</code> to a private BOOST_HOME with no <code>repos/</code>, so <code>load_tap</code> served the stale caches as-is and wrote nothing to the shared corpus.

5. A fix that routes <code>panel</code> through <code>pane_width()</code> will turn 7 tests red: <code>tests/unit/test_output.py::TestPanelFitsTerminal</code> (lines 539-586) monkeypatches <code>output.term_width</code>, and under pytest stdout is not a TTY, so <code>pane_width()</code> returns None in all of them. They need to patch <code>pane_width</code>/<code>isatty</code> instead, the way PR 739 reworked the table tests. Whoever fixes this will otherwise think the fix is wrong.

6.

<b>Why it is worth doing.</b> <code>boost count</code> is the one-line inventory a script or a shell prompt would capture, and piping it silently drops the discovery-index state and (on a real machine) the tap count. It is small in isolation, but it is the last unconverted emit site of a root cause the repo already diagnosed, wrote a helper for, and pinned tests around — leaving it means the invariant "a pipe has no pane" is true of tables and <code>--help</code> and false of boxes, which is the kind of split that grows back.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
