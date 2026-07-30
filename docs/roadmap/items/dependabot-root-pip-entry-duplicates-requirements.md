---
id: dependabot-root-pip-entry-duplicates-requirements
board: code
section: internals
status: shipped
category: Build · Gap
complexity: S
impact: Low
wow: 1
note: fallout from #289 — every toolchain bump now arrives twice
order: 35
owner: loop/dependabot-root-narrow
pr: 349
title: Dependabot raises every toolchain bump <em>twice</em>
---
PR #289 added a third Dependabot entry, <code>package-ecosystem: pip</code> with
<code>directory: /</code>, to give <code>pyproject.toml</code>'s optional extras the proactive bump
PRs they had never had. The first scheduled run after it merged produced <b>eight</b> PRs, and two
pairs of them are duplicates: <code>#301</code>/<code>#302</code> (twine) and
<code>#300</code>/<code>#303</code> (hypothesis) change <b>byte-identical file sets</b> — one PR from
the <code>/</code> entry and one from the pre-existing <code>/requirements</code> entry, for the same
bump. Merging either makes the other redundant, and Dependabot closes the twin automatically, so the
cost is noise rather than breakage. It will recur every week.

Worse, the entry cannot deliver what it was added for. Every constraint under
<code>[project.optional-dependencies]</code> is either an open lower bound
(<code>sqlite-vec&gt;=0.1.6</code>) or explicitly listed in that entry's own <code>ignore</code>
block (the pinned langchain 0.3 stack held back for ragas). Dependabot does not raise a
<i>version</i> PR when the declared range already admits the newest release, so the set of
<code>pyproject.toml</code> version updates this entry can ever produce is <b>empty</b> — which is
why none of the eight touched <code>pyproject.toml</code>.

Do not simply revert it. Dependabot <i>security</i> updates ignore the versioning strategy and fire
on a vulnerable version inside a permitted range, so the entry does give the extras security
coverage they previously lacked — the item it closed was right that
<code>[rag]</code>/<code>[bdd]</code>/<code>[perf]</code> had only reactive pip-audit flags. The
entry should be <b>narrowed</b>, not removed.

Two candidate fixes, both needing verification against a real scheduled run rather than reasoning —
Dependabot's file discovery is what got this wrong in the first place. <b>First</b>, scope the
<code>/</code> entry so it stops matching <code>requirements/**</code>, leaving
<code>/requirements</code> as the single owner of the hash-pinned lock. <b>Second</b>, if proactive
extras bumps are genuinely wanted, that needs <code>versioning-strategy: increase</code> so open
lower bounds are raised at all; otherwise accept that this entry is security-only and say so in the
comment, which is the honest smaller change.

<b>Shipped &mdash; the second one, and <code>#342</code> changed why.</b> That change gave
<code>/requirements</code> <code>open-pull-requests-limit: 0</code>, which silences the duplicate on
one side but leaves the <code>/</code> entry as the <em>only</em> remaining path to a
lock-regenerating pull request &mdash; precisely the thing that cannot be done correctly on a single
platform. The duplicate stopped being the problem and the survivor became one.

So the version-update side of the <code>/</code> entry is off too, and the reasoning is now written
where the next person will look. It produces nothing wanted: every constraint under
<code>[project.optional-dependencies]</code> is an open lower bound or sits in the entry's own
ignore list, so its set of possible <code>pyproject.toml</code> version updates is <b>empty</b>
&mdash; none of the eight PRs in that first run touched it. And it produces one thing actively
harmful: four of those eight were byte-identical lock regenerations. <b>Security</b> updates ignore
the limit and keep firing, which is the coverage the extras genuinely gained, and
<code>lock_toolchain.py --audit</code> now catches a security PR that arrives having dropped a
marker-gated pin.

Both pip entries are pinned at <code>limit: 0</code> by
<code>tests/unit/test_dependabot_config.py</code>, alongside an assertion that neither entry is
<em>deleted</em> &mdash; removing them would give up the security coverage that is the whole
remaining point. Related: [[dependabot-regeneration-drops-platform-pins]].
