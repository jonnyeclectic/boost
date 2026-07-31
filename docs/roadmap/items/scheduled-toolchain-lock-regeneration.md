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

<b>Blocked on a repository setting, and it is the same one that blocks
[[demo-cannot-open-its-own-pr]].</b> The obvious shape for this &mdash; a scheduled job that runs
<code>lock_toolchain.py --upgrade</code> and opens a pull request &mdash; cannot work here.
Actions&nbsp;&rarr;&nbsp;General&nbsp;&rarr;&nbsp;Workflow permissions&nbsp;&rarr;&nbsp;"Allow
GitHub Actions to create and approve pull requests" is off; the API reports
<code>can_approve_pull_request_reviews: false</code>, and <code>demo.yml</code> already fails on
every push to <code>main</code> with <code>GitHub Actions is not permitted to create or approve
pull requests</code>. Declaring <code>pull-requests: write</code> does not help, as that card
established at length. Building this the obvious way would produce a second workflow that is
correct in the file and inert in reality.

So the two items are coupled: flipping that one toggle unblocks both, which is worth knowing when
weighing it &mdash; the decision is no longer about a demo GIF alone. That card is right that it is
a real decision, since the toggle grants <em>every</em> workflow the ability to open pull requests.

<b>Two designs that respect the constraint</b>, if the toggle stays off. Actions can still
<em>push a branch</em>, so the job can regenerate the lock, commit to
<code>chore/toolchain-lock-YYYY-MM-DD</code> and stop &mdash; leaving a one-click "Compare &amp;
pull request", with the expensive part (resolving five groups universally with <code>uv</code>)
already done. Or it can open an <em>issue</em> containing the diff, which
<code>issues: write</code> does permit. The branch is better: it carries the actual bytes rather
than a description of them, and <code>lock_toolchain.py --audit</code> then runs against it as a
normal PR gate once a human opens it.

Either way the freshness gap this item exists to close narrows from "nobody is watching" to "a
human clicks a button", which is the honest available improvement while the setting stands.


<b>The blocker is gone.</b> This card is gated on the same repository setting as
<code>demo-cannot-open-its-own-pr</code>, and the API now reports
<code>can_approve_pull_request_reviews: <b>true</b></code>. Confirmed working rather than merely
configured: <code>#353</code> was opened by <code>github-actions[bot]</code>.

So the &ldquo;honest available improvement while the setting stands&rdquo; compromise described above
&mdash; a workflow that only reports drift and waits for a human to click a button &mdash; is no
longer the ceiling. A scheduled job can now regenerate the lock and open its own PR, which is what
this card originally asked for.

Deliberately left unimplemented here. It needs a real decision about cadence and about what happens
when the regenerated lock fails <code>lock_toolchain.py --check</code> on a runner, and shipping an
untested scheduled workflow that opens PRs against <code>main</code> is worse than shipping nothing.
The value of this note is that the next person picking it up starts from &ldquo;build it&rdquo;
rather than from &ldquo;it cannot be built&rdquo;.
