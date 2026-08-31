---
id: audit-singular-plural-misses-1-skills-1-issue-need-1-skill-pass-ac
board: code
section: dx
status: planned
category: CLI · Polish
complexity: S
impact: Low
wow: 1
note: a shared _s helper exists at _common.py:15 and six commands hand-roll around it
order: 242
owner:
pr:
title: "Singular/plural misses (&ldquo;1 skills&rdquo;, &ldquo;1 issue need&rdquo;, &ldquo;1 skill pass&rdquo;) across six commands"
---
Six commands hand-roll plurals and get the singular wrong. Reproduced verbatim on a fresh HOME with one
installed skill: <b>doctor</b> &mdash; <code>&#9679; 1 issue need attention &mdash; see the suggestions
above</code>; <b>lint</b> &mdash; <code>&#10003; 1 skill pass lint (min 40)</code>; <b>policy check</b> &mdash;
<code>&#10003; policy check passed (1 skills)</code>; <b>cohort create</b> &mdash; <code>&#10003; created cohort
everyone (100% rollout, 1 skills) &mdash; you are IN</code>. The remaining two are confirmed in source:
<code>count</code>'s breakdown prints <code>1 skills &middot; 1 rules &middot; 1 workflows</code> (surfacing once
a rule and workflow are also installed &mdash; the same line pluralises <code>tap%s</code> correctly), and
<code>focus</code> prints <code>other 1 skills sidelined</code> (<code>team.py:105</code>,
<code>configuration.py:475</code>).

It is an internal-consistency miss, not a style choice: a shared plural helper already exists
(<code>_s</code>, <code>boost_cli/commands/_common.py:15</code>) and is applied inconsistently &mdash;
<code>quality.py:637</code> and <code>:777</code> pluralise the noun but leave the verbs
<em>need</em>/<em>pass</em> unagreed, while <code>boost list</code> and <code>uninstall</code> on the same HOME
say <code>1 skill installed</code> correctly, and <code>profile use</code> hedges with
<code>sidelined 1 skill(s)</code>.

Fix as one sweep PR: reuse <code>_s</code> at <code>configuration.py:475</code> and <code>team.py:105</code>
(cohort create, profile save, the <code>skill(s)</code> strings) and in count's breakdown; the verbs at
<code>quality.py:637/777</code> need a word pair chosen on <code>n == 1</code>
(<em>needs/need</em>, <em>passes/pass</em>) &mdash; <code>_s</code> alone cannot fix verb agreement. Add a small
unit test asserting the <code>n == 1</code> strings. No docs change &mdash; these are runtime messages only.
Found by the 2026-08 CLI audit (cluster pluralisation-sweep); repro in the audit log.
