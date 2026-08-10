---
id: dependabot-splits-multi-path-action-repos
board: code
section: internals
status: shipped
category: Build · Bug
complexity: S
impact: Med
wow: 3
note: one codeql-action release arrived as 3 PRs, 2 red — and the green one was the misleading part
order: 104
owner: chore/lockstep-action-pins
pr:
title: Dependabot splits one action repo into three unmergeable PRs
---
<b>A Dependabot "dependency" is one <code>uses:</code> path, not one action repo.</b>
<code>github/codeql-action/init</code>, <code>/analyze</code> and <code>/upload-sarif</code> are
three entry points of a <b>single repository at a single commit</b>, but Dependabot tracks them as
three independent dependencies — so one upstream release arrives as one PR each, each moving one pin
and leaving its partners behind. On 2026-08-09 the v4.37.6 release did exactly that:

<code>#495</code> <code>init</code> 4.37.3&rarr;4.37.6 <b>RED</b> ·
<code>#496</code> <code>analyze</code> 4.37.3&rarr;4.37.6 <b>RED</b> ·
<code>#497</code> <code>upload-sarif</code> 4.37.3&rarr;4.37.6 <b>green</b>

Both red ones died on the same line, and it names the cause precisely:
<code>Loaded a configuration file for version '4.37.6', but running version '4.37.3'</code>.
<code>init</code> stamps its own version into the config it writes and <code>analyze</code> refuses
a config written by any other release, so the two must move together or not at all.
<b>No single one of the three was mergeable.</b>

<b>The green one is the trap.</b> <code>#497</code> passed only because
<code>upload-sarif</code> is used alone in <code>scorecard.yml</code>, with no partner in the same
job to disagree with — so "one of the three is green" said nothing whatever about the other two, and
merging it first would have unblocked neither. A reader triaging three PRs by their check marks
reaches for the green one, which is the one change that does not help.

<b>The failing step name points at the wrong file too.</b> The job reports
<code>analyze</code> as the failed step, so the natural first move is to read
<code>codeql.yml</code> — where both pins look internally consistent, because the mismatch only
exists between the PR's branch and what it did not change. The diagnosis lives in the sibling PR.

<b>Fixed in two halves, because either alone is insufficient.</b> The first is a Dependabot
<code>groups:</code> rule on the <code>github-actions</code> entry, so every sub-action of a repo
arrives in one PR and the pins move in lockstep. That stops the broken PR being <i>raised</i>, which
is the real fix — the same shape <code>prometheus/prometheus</code> uses for this identical problem.
The second is <code>tests/unit/test_action_pin_lockstep.py</code>, which fails the build if a split
lands <i>anyway</i> — by hand, by a config edit, or by a change in Dependabot's own behaviour — and
reports the family and the disagreeing pins, which is the diagnosis the CodeQL runtime error makes
you reconstruct.

<b>Written against the class, not the instance, because there was already a second one.</b>
<code>actions/cache</code>, <code>actions/cache/save</code> and <code>actions/cache/restore</code>
are three pins of one repo sitting in lockstep today only because no release has split them yet. It
is grouped here before it bites. The test is <b>parametrised over the families the workflows
actually use</b>, so adopting a sub-action of some new repo fails until it is grouped too, rather
than quietly re-introducing this a year from now.

<b>The guard is checked for being able to fail.</b> Its lockstep assertions pass on a correct tree,
which is exactly when a silently-broken regex would go unnoticed — so four tests assert the parser
still sees the pins and both known families, and four more feed it the literal content of
<code>#495</code> and require it to go red. A stale <i>version comment</i> beside a correct SHA
counts as a split too, since that comment is what a human reads and what <code>zizmor</code>'s
<code>ref-version-mismatch</code> audit compares against.

<b>The same instinct applied to the file list, which is the half that is easy to miss.</b> Every pin
in this repo lives in <code>.github/workflows/*.yml</code> today, so globbing exactly that passes —
and would keep passing, silently and greenly, the first time someone writes a <code>.yaml</code>
workflow or factors a job into a composite action under <code>.github/actions/</code>. Both are
scanned now, and a further test walks <code>.github/</code> itself and fails naming any file that
pins an action the glob did not hand to the assertions above. A guard that has quietly stopped
looking is worse than no guard, because the green tick still appears.
