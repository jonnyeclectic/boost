---
id: scheduled-toolchain-lock-regeneration
board: code
section: internals
status: shipped
category: Build · Gap
complexity: M
impact: Med
wow: 2
note: shipped and now proven — first real run opened #405, audit passed, zero pins dropped
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

<b>Shipped as <code>.github/workflows/lock-refresh.yml</code>, and the first thing that had to be
re-checked was this card's own blocker.</b> It states the work is blocked because
Actions&nbsp;&rarr;&nbsp;Workflow permissions forbids creating pull requests, citing
<code>can_approve_pull_request_reviews: false</code>. That is no longer true: the API now returns
<b><code>true</code></b>, <code>demo.yml</code> succeeds on every push to <code>main</code>, and it
opened <code>#353</code> and <code>#394</code> as <code>github-actions[bot]</code>. A blocker
recorded once is a claim with an expiry date; this one had quietly lapsed, and the card would have
kept the item shelved indefinitely.

<b>One PR for all five groups &mdash; a deliberate departure from what this card proposed.</b> The
card suggested per-group jobs so a bump stays reviewable. Two things measured while building it
argue the other way. <code>lock_toolchain.py</code> has <b>no per-group flag</b>
(<code>--upgrade</code> always re-resolves all five), so a five-job matrix would run the same
resolution five times and commit one file from each. And a PR opened this way arrives with
<b>zero check runs</b> &mdash; <code>create-pull-request</code> pushes with
<code>GITHUB_TOKEN</code>, which never triggers workflows &mdash; so every one of them costs a human
a manual <i>Update branch</i> before CI reports at all. Five PRs a month is five full CI runs and
five manual unblocks to review what is usually a list of version bumps. Reviewability is bought
instead with a <b>monthly</b> cadence and a per-group diffstat in the PR body.

<b>The other three constraints this card named were met as written.</b> <code>uv</code> and the
network are provisioned the same way <code>ci.yml</code> does it (<code>pip install uv</code>, then
the script). <code>--audit</code> runs as its own invocation, because the script refuses it
alongside <code>--upgrade</code> &mdash; auditing a file mid-replacement reads the old bytes &mdash;
and a failure there means no PR is opened. Every <code>uses:</code> is pinned to the same peeled
SHAs the repo already uses, permissions are <code>contents: read</code> at the top with the two
writes scoped to the one job, and no <code>merge_group:</code> trigger is needed because this is not
a required context (<code>check_required_checks.py</code> passes).

<b>Verified before pushing:</b> the workflow parses, and <code>zizmor</code> reports <b>no
findings</b>. That clean result was itself checked rather than trusted &mdash; re-running the
scanner against a copy with <code>${{ github.event.head_commit.message }}</code> spliced into a
<code>run:</code> block produces a high-severity <code>template-injection</code>, so the scanner is
genuinely reading this file. That check exists because an earlier workflow in this repo
(<code>shards.yml</code>) shipped exactly that hole.

<b>Unproven until it runs:</b> the first scheduled execution is the first end-to-end exercise.

<b>Proven &mdash; the &ldquo;unproven until it runs&rdquo; caveat above is now closed.</b> The
workflow's first real execution opened <code>#405</code>, and it validated on every point the design
turned on. <code>--audit</code> passed on the runner and <b>zero pins were dropped</b>, which is the
exact failure that made Dependabot unusable here. Six packages moved
(<code>cryptography</code>&nbsp;49&rarr;50, <code>mutmut</code>&nbsp;3.6&rarr;3.7,
<code>libcst</code>&nbsp;1.8.6&rarr;1.9.0, <code>hypothesis</code>, <code>filelock</code>,
<code>pip</code>) across four groups; <code>lint-tools</code> did not move at all.

<b>The prediction written into the PR body held exactly.</b> That body warns the reader that the PR
arrives with no check runs because <code>create-pull-request</code> pushes with
<code>GITHUB_TOKEN</code>; the real PR arrived with <code>total_count: 0</code>. Predicting it in
advance is the difference between a documented platform rule and a confusing discovery &mdash; an
empty check list is indistinguishable from &ldquo;CI has not started yet&rdquo;, and a reader who
did not know that could merge a toolchain bump believing it was green.

<b>Following the workflow's own advice caught the thing worth catching.</b> Rather than merging on a
page with no checks, <i>Update branch</i> was pressed to make CI actually run &mdash; and the
riskiest part of the bump was <code>mutmut</code>&nbsp;3.7 with <code>libcst</code>&nbsp;1.9, since
the mutation gate runs on both. It passed, and the bump merged as <code>#405</code>. The one-PR
choice also held up in practice: the per-group diffstat in the body made a 4-file, +296/-311 change
reviewable at a glance.

