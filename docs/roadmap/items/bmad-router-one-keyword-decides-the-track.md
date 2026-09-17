---
id: bmad-router-one-keyword-decides-the-track
board: code
section: dx
status: inflight
category: Agents · BMAD
complexity: S
impact: High
wow: 3
note: 89 of 143 routed prompts rode on a single keyword
order: 319
owner: loop/bmad-incidental-keywords
pr:
title: One incidental keyword decides the <code>boost bmad</code> track
---
<code>classify</code> counts distinct keyword patterns per track over the raw prompt and routes on
the best score (<code>core/bmad.py:412</code>&ndash;<code>417</code>). Two hits are required only
past <code>LONG_PROMPT_WORDS</code> (60, #630; <code>:415</code>), so any prompt of up to 60 words
that clears the question and slash gates <b>routes on one match anywhere</b> &mdash; including
words nobody meant as intent: a URL, a path, a flag, a ticket reference, the repo's own name.
Replaying the origin/main classifier over one real prompt history (417 prompts, 348 unique, 6
active days): <b>89 of 143 routed unique prompts were decided by exactly one keyword</b>. A single
judge labelling 41 routed banners found the track or lead clearly wrong in <b>21 of 41</b>.

<b>A wrong route costs more than silence.</b> The banner names a lead, asks for support subagents,
sets a done-contract (tests, docs, and the gate when there is one) and says to work autonomously
(<code>:536</code>&ndash;<code>553</code>). In a repo directory named <code>migrations</code>,
&ldquo;list the last three commits in migrations&rdquo; gets a 643-char build banner &mdash; Amelia
leads, Murat and Paige to be spawned, <code>make check</code> green &mdash; for a
<code>git log</code>. The module already chose: it &ldquo;would rather under-route than talk over
someone&rdquo; (<code>:387</code>&ndash;<code>388</code>).

<b>Five collision classes, all single hits, reproduced on origin/main with synthetic prompts</b>
(three spot-checked on the installed v1.2.112): <i>repo name</i> &mdash; &ldquo;list the last three
commits in migrations&rdquo; in <code>migrations/</code> &rarr; build, &ldquo;list the new notebooks
in benchmarks&rdquo; in <code>benchmarks/</code> &rarr; discovery; <i>flags</i> &mdash; &ldquo;rerun
the installer with <code>--scope</code> global&hellip;&rdquo; &rarr; product; <i>URLs, paths,
code</i> &mdash; <code>https://example.com/docs/&hellip;</code> &rarr; docs, <code>tail
logs/build/server.log</code> &rarr; build, <code>`npm run build`</code> &rarr; build; <i>tracker
words</i> &mdash; &ldquo;move story ABC-123 to in progress&rdquo; &rarr; product; <i>generic
verbs</i> &mdash; &ldquo;update me when the CI run finishes&rdquo; &rarr; build. The hook already
has the repo &mdash; <code>cwd</code> becomes <code>root</code>
(<code>commands/bmad.py:342</code>&ndash;<code>344</code>) &mdash; but <code>route_lines</code>
calls <code>classify(prompt)</code> bare (<code>core/bmad.py:529</code>).

<b>Fix: stop scoring text that is not intent; do not raise the threshold.</b> Before scoring,
<i>(1)</i> drop URLs, backtick spans, <code>--flag</code>/<code>-f</code> tokens and tracker-noun +
ID pairs (<code>story ABC-123</code>); <i>(2)</i> a token containing <code>/</code> stops scoring
for <code>build</code> but still counts for every other table, so <code>docs/README.md</code>
stays docs; <i>(3)</i> <code>classify(prompt, root=None)</code>, fed by <code>route_lines</code>,
drops whole-word matches of <code>Path(root).name</code>; <i>(4)</i> a build verb followed by
<em>me</em>/<em>us</em> does not score. On a stdlib prototype: all <b>46</b> distinct prompts
<code>test_bmad_core.py</code> sends through <code>classify</code> keep their verdict; <b>16 of
18</b> synthetic misroutes go silent; build asks still route &mdash; 12/12 verb-first, 8/8 not
(&ldquo;we need to fix the crash&hellip;&rdquo;), 4/4 late-verb &mdash; and 5/5 path-object asks
keep their track. Small hand-written sets: they show which rule does the work, not a rate.

<b>Threshold rules measured and declined.</b> Layered on <i>(1)</i>&ndash;<i>(4)</i>: two build hits
or a head verb silences neither of the 2 left but routes <b>2 of 8</b> non-head and <b>0 of 4</b>
late-verb asks; a verb in a clause's first six words routes <b>0 of 4</b> late-verb asks; making
<code>add</code>/<code>update</code>/<code>create</code>-class verbs need a second hit silences one
more but keeps only <b>6 of 12</b> short build asks and breaks <code>"update the flag"</code>
(<code>test_bmad_core.py:142</code>). Stripping paths outright flips 3 of 5 path-object asks.
<b>Residue:</b> &ldquo;add the meeting notes to my summary&rdquo; stays build; &ldquo;pull the
comments on story ABC-123&hellip;&rdquo; goes docs on <code>\bcomments?\b</code>; a sibling repo's
name still routes; and a cwd named after a keyword loses that word &mdash; in <code>tests/</code>,
&ldquo;add tests for catalog.scan_dir&rdquo; flips quality &rarr; build.

<b>Tests:</b> add <code>TestIncidentalKeywords</code> beside <code>TestClassifyTracks</code>
(<code>tests/unit/test_bmad_core.py:173</code>): one <code>(prompt, repo_dirname, expected)</code>
table with every repro as <code>trivial</code> except the two residues (pinned at today's track,
so a later fix shows as a diff), the non-head, late-verb and path-object asks at their tracks,
plus a <code>route_lines</code> case rooted at <code>tmp_path / "migrations"</code> so the name
must reach <code>classify</code>.
