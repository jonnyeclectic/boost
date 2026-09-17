---
id: bmad-done-contract-ignores-the-track
board: code
section: dx
status: next
category: "Agents · BMAD"
complexity: M
impact: High
wow: 2
note: a review or research ask is told to add tests and finish a change
order: 321
owner:
pr:
title: "<code>boost bmad</code> gives every track the build contract, so a review is told to finish a change"
---
<code>route_lines</code> (<code>core/bmad.py:523</code>) takes the first four banner lines from the track
and the last two ignore it: <code>done_checklist(signals)</code> (<code>:483</code>) has no
track parameter, and the autonomy sentence (<code>:551</code>) is a literal. One prompt per track against
one fixture repo gave <b>one distinct pair of closing lines across all 9 tracks</b>:<br>
<code>Done means: tests: add or update coverage under `tests/`, and run them · docs: update `README.md` / `docs/` wherever the change shows · gate: `make check` green, with real output · `CLAUDE.md` is binding</code><br>
<code>Work autonomously through to a finished, verified change; stop to ask only when a choice would change what gets delivered.</code>

<b>Repro</b> (throwaway repo with <code>tests/</code>, <code>docs/</code>, <code>README.md</code>,
<code>CLAUDE.md</code>, and a <code>Makefile</code> with <code>check:</code>).
<code>boost bmad route "review the changes on this branch and tell me what could break" --plain</code>
names Murat (<code>bmad-tea</code>) as lead with <code>bmad-code-review</code>, then defines done as new
coverage, updated docs and a finished, verified change. <code>"compare the two caching options and recommend one"</code>,
<code>"write the PRD for the policy engine"</code> and <code>"prioritize the backlog for next sprint"</code>
get the same two lines. In an empty repo the comparison is told <code>tests: cover the change … docs: write down what changed</code>, but nothing changed.
The shared lines are 48% of the fixture's review banner (326 of 673 chars) and 41% in the empty repo.

<b>Against real prompts the clause seldom fits.</b> Replaying the origin/main classifier over one
profile's history (417 ordinary prompts over 6 active days, roughly half from tooling repos): 147 (35%)
would get a banner, or 109 if pasted text is not in the hook's <code>prompt</code> field (not yet
checked). A <em>single judge</em> (an agent) labelled 41 routed banners, sampled by track: <code>Done means</code>
fit <b>5 of 41</b> (11 counting partial fits).

<b>The same contract appears in three places, and one was a deliberate choice.</b> The autopilot item
made tests and docs unconditional (&ldquo;no doc change needed&rdquo; is a conclusion to reach), and
<code>tests/unit/test_bmad_core.py:331</code> enforces that. It is right for a change and wrong for an
answer. Every persona file repeats the contract (<code>_persona_text</code>,
<code>core/bmad.py:663&ndash;667</code>: &ldquo;tests updated and actually run, documentation left true …&rdquo;),
so the <code>bmad-analyst</code> a discovery banner hands off to brings it back. The SessionStart
briefing says to follow the banner (<code>:576</code>) and ends on a tests-docs-item house rule
(<code>:586</code>).

<b>The autonomy line competes with approval gates users add on purpose</b>, such as the
<code>HARD-GATE</code> in superpowers' <code>brainstorming</code> skill (no implementation until the user
approves) or a team rule requiring confirmation before a change that affects production. The banner is
<code>UserPromptSubmit</code> <code>additionalContext</code> (<code>commands/bmad.py:354</code>), added
again on every routed prompt. <b>Untested:</b> which instruction a model follows when they
conflict. Softening the line to defer to the repo guide would not cover this: the <code>is binding</code>
clause only appears when a guide file exists (<code>core/bmad.py:514&ndash;516</code>), and a plugin skill is not a guide file.

<b>Fix: store the kind of done on <code>Track</code></b> (<code>core/bmad.py:75</code>) and pass it to
<code>done_checklist(signals, done)</code>. <i>change</i> (build, quality, docs, ux): today's clauses,
unchanged. <i>findings</i> (review, discovery): &ldquo;findings with evidence, no edits unless
asked&rdquo;. The &ldquo;unless asked&rdquo; matters because the tie-break sends <code>"fix the lint
errors in the scanner"</code> to review and <code>"investigate why the export crashes and fix it"</code>
to discovery. <i>artifact</i> (product, planning, architecture): &ldquo;a written artifact, no
code&rdquo;, keeping the roadmap and guide clauses. Drop the autonomy line from
findings and artifact tracks. On change tracks, replace it with wording that does not depend on a
guide file: finish and verify, and still honour any approval step that the guide or a loaded skill
requires. <code>_persona_text</code> should state the contract for each kind, since
<code>bmad-tea</code> leads both quality and review. The house rule should name all three kinds.

<b>Tests go in <code>tests/unit/test_bmad_core.py</code>.</b> Assert every <code>TRACKS</code> entry
declares a kind, and that no findings or artifact banner has a <code>tests:</code> clause.
Add verbatim review and discovery banners next to <code>test_the_whole_banner_is_exactly_this</code>
(<code>:396</code>), whose build pin keeps its <code>Done means</code> line and takes the new closing line.
Limit <code>:331</code> to change tracks. <code>:376</code> pins <code>autonom</code> on one build banner:
move it to the new wording and assert the line is absent from findings and artifact banners.
<code>:688</code> only checks that each persona file mentions tests and docs, so pin the per-kind persona
contract directly. Out of scope: router accuracy (same single judge: track or lead clearly wrong on
21 of 41) is a separate defect.
