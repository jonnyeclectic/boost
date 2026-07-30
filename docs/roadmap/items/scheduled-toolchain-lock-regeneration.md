---
id: scheduled-toolchain-lock-regeneration
board: code
section: internals
status: planned
category: Build · Gap
complexity: M
impact: Med
wow: 2
note: the toolchain lock now has no proactive update path — by choice, but nothing replaces it yet
order: 36
owner:
pr:
title: The toolchain lock has no proactive update path any more
---
<code>#342</code> set <code>open-pull-requests-limit: 0</code> on the <code>/requirements</code>
Dependabot entry, because Dependabot cannot regenerate a hash-pinned universal lock without dropping
the pins whose environment markers exclude them on the resolving platform (see
[[dependabot-regeneration-drops-platform-pins]]). That was the right call — every pip bump it raised
was unmergeable — but it reverses the reason the entry was added in the first place: <b>a pin with no
update path is only half the job</b>, and the dev/CI toolchain now has none.

The trade is bounded rather than silent, which is why this is <code>Med</code> and not
<code>High</code>. Dependabot <b>security</b> updates ignore the limit and still fire;
<code>pip-audit.yml</code> runs weekly against the resolved closure and <b>blocks</b> on a live CVE
(Dependabot only ever opened a PR); and <code>osv-scanner.yml</code> covers what a PR introduces. So
the exposure is not "a vulnerable pin sits there unnoticed" — it is
<b>stale-but-not-vulnerable tooling</b>, drifting further from upstream every week until something
forces a bump.

The replacement the card already named: regenerate on a schedule with
<code>scripts/lock_toolchain.py --upgrade</code> and open the PR from that, so the resolution stays
universal and every conditional pin survives. Four points worth getting right rather than guessing.
<b>First</b>, it needs <code>uv</code> and the network — the required gate's <code>--check</code>
already assumes both on CI, but no scheduled job currently sets them up. <b>Second</b>,
<code>--upgrade</code> re-resolves all five groups, so a weekly cadence would land large multi-group
diffs; per-group jobs, or a lower cadence, keep a bump reviewable, and the reason <code>-P</code>
exists at all is that a bare <code>--upgrade</code> buries one package in unrelated churn.
<b>Third</b>, a new workflow is not free in this repo: it must be zizmor-clean with every
<code>uses:</code> pinned to a <i>peeled</i> commit SHA, carry narrow <code>permissions</code>, and
— if it is ever made a required context — grow a <code>merge_group:</code> trigger, which
<code>check_required_checks.py</code> enforces. <b>Fourth</b>, nothing needs to guard the output:
<code>lock_toolchain.py --audit</code> and <code>requirements/platform-pins.lock</code> already fail
closed on a lost marker-gated pin, so a regeneration job that got it wrong would be caught the same
way a Dependabot PR now is.
