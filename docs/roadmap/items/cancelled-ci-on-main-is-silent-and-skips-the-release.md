---
id: cancelled-ci-on-main-is-silent-and-skips-the-release
board: code
section: trust
status: shipped
category: CI · Bug
complexity: S
impact: High
wow: 4
note: the alerting that exists to make a red main impossible to miss asks only about 'failure', and the run that skipped a release was 'cancelled'
order: 365
owner: loop/ci-alert-conclusions
pr: 1025
title: "A <code>cancelled</code> <code>ci</code> on main skips the release and alerts nobody, because the alert asks only about <code>failure</code>"
---
<b>Two independent gates, both keyed on the wrong half of the same enum.</b>
<code>publish.yml</code> fires on <code>workflow_run</code> and ships only when
<code>conclusion == 'success'</code>; <code>ci-failure-alert</code> opens the tracking issue
only when <code>conclusion == 'failure'</code>. A <code>ci</code> run that concludes
<code>cancelled</code> satisfies neither. <b>It does not ship and it does not tell anyone</b>
&mdash; the one conclusion that falls through both.

<b>Observed, on the merge of #1015.</b> <code>mutation-shard (4)</code> hit
<code>timeout-minutes: 75</code> and was cancelled, the aggregate <code>mutation</code> job
failed, and the run concluded <code>cancelled</code> rather than <code>failure</code>. No
release, no issue, no notification. It surfaced the same day, and only because somebody was
reading per-shard job durations out of the Actions API for an unrelated reason &mdash; nothing
in the repo would have raised it, and the next one will be found the same way or not at all.

<b>This is the exact blind spot <code>ci-failure-alert</code>'s own header describes.</b> That
file opens by explaining that <code>demo</code> "failed six runs out of six on main, alerted
nobody, and was found by a manual audit instead", and concludes that "any workflow that runs on
main and nobody watches belongs here". The list was then enforced by
<code>tests/unit/test_failure_alerting_covers_unattended.py</code> so a new workflow cannot
quietly join the blind spot. <b>The enforcement is over <em>which workflows</em> are watched,
and the hole here is <em>which conclusions</em> are</b> &mdash; <code>ci</code> is on the list
and still said nothing.

<b>Why a timeout is not an exotic case.</b> It is the designed behaviour of every
<code>timeout-minutes</code> in the repo, and <code>mutation-shard</code>'s is reached by an
ordinary slow runner rather than by a bug: across 169 measured shard jobs the worst was 72.5
minutes against a 75-minute cap. A job can also be cancelled by the concurrency group or by a
human pressing the button &mdash; and only the last of those is one anybody already knows about.

<b>A runner eviction is the neighbouring case, and it concludes differently.</b> An earlier
draft of this card listed eviction among the routes to <code>cancelled</code>; measured on
2026-10-02, it is not. <code>mutation-shard (0)</code> on main took
<code>The runner has received a shutdown signal</code> and exit 143 at mutant 3095 of 28084,
the job concluded <b>failure</b>, and the alerting fired correctly &mdash; issue #1024 opened
and auto-closed when a rerun of the failed jobs went green. That is the point of widening on
the <em>green</em> set rather than enumerating bad conclusions: the two most common ways a
shard dies land on different sides of an <code>== 'failure'</code> test, and a gate that has
to know which one it was is a gate that will be wrong again.

<b>Shape of the work.</b> Widen the alert's condition from <code>== 'failure'</code> to the set
of conclusions that mean "main is not green", which is every one except <code>success</code>,
<code>skipped</code> and <code>neutral</code> &mdash; naming what is <em>excluded</em> rather
than what is included, so the next conclusion GitHub adds defaults to loud. The issue body
should say which conclusion it was, because <em>cancelled</em> and <em>failure</em> want
different first moves. Then pin it: the sibling test already enforces the workflow list, so the
conclusion set wants the same treatment rather than a comment. Worth checking at the same time
whether <code>publish.yml</code> should distinguish "CI did not pass" from "CI did not finish"
&mdash; today both are a silent no-op, and a release that was skipped because a runner was slow
is recoverable by a rerun that nobody currently knows to start.

<b>Shipped.</b> The opener now gates on the green set <em>negated</em> &mdash;
<code>!contains(fromJSON('["success", "skipped", "neutral"]'), conclusion)</code> &mdash; so a
conclusion GitHub adds later defaults to loud. <code>skipped</code> and <code>neutral</code>
are in it deliberately: <code>release</code> skips on every run it does not publish from, so
without that exclusion each non-green <code>ci</code> would open two issues. The closer keeps
<code>== 'success'</code>, because a <code>cancelled</code> run says nothing about whether the
tracked failure is fixed and must not stand the issue down. The body now names the conclusion
and, for <code>ci</code>, says no release was cut and that a rerun is what publishes it.

<b>publish.yml was left alone, deliberately.</b> Its
<code>conclusion == 'success' &amp;&amp; event == 'push'</code> guard is the fork-PR boundary
that stops an outsider cutting a real PyPI release; widening it to tell "did not pass" from
"did not finish" would trade a silent no-op for a security hole. The recoverable case &mdash; a
release skipped because a runner was slow &mdash; is recovered by the issue telling somebody to
rerun, which is what the new body does.

<b>Found on the way, and fixed in the same change.</b> An empty GitHub expression written
inside a <code>run:</code> or <code>script:</code> body makes zizmor emit
<code>couldn't parse expression</code> from six audits &mdash; template_injection,
overprovisioned_secrets, unredacted_secrets, obfuscation, secrets_outside_env and
unsound_ternary. A comment explaining why the script avoids interpolation was enough to cause
it. Measured three ways: in a YAML <code>#</code> comment it is harmless (zizmor does not read
those), in a <code>script:</code> body it costs six, and in a <code>run:</code> body it costs
six even behind a shell <code>#</code>.

<b>An earlier draft of this section said that blinded the audits for the whole file. It does
not, and the review that asked caught it.</b> Planting a real finding &mdash; a
<code>head_commit.message</code> interpolated into a <code>run:</code> &mdash; in two copies of
the file, one clean and one carrying an empty expression, zizmor reported the
template-injection in <b>both</b>. What is actually lost is the unparseable span itself, which
no audit inspects, plus six warning lines above a run that still ends in "No findings to
report". Worth preventing on those terms rather than the dramatic ones: a span that silently
opts out of SAST is a bad place for a mistake to hide. A parametrised test now walks every
workflow's parsed run/script bodies.

<b>One more hole the widening opened, and the review found it.</b>
<code>head_branch == 'main'</code> is not a provenance check. <code>ci.yml</code> runs on
<code>pull_request</code>, so a fork PR opened from a branch named <code>main</code> produces a
<code>ci</code> run whose <code>head_branch</code> is <code>main</code> &mdash; and
<code>cancel-in-progress</code> concludes it <code>cancelled</code> on every superseded push.
Under the old <code>== 'failure'</code> gate that was rare; under the new one it is routine PR
iteration, and the issue would have claimed a release was skipped for a run that was never
release-eligible. <code>publish.yml</code>, <code>sbom.yml</code> and
<code>mutation-weights-refresh.yml</code> all carry the event+repository pair and this file was
the only <code>workflow_run</code> consumer without it, so the fix is the house guard on
<em>both</em> jobs &mdash; the closer needed it just as much, since a <em>green</em> fork PR
could otherwise close a tracker for a failure still live on main. It is
<code>event != 'pull_request'</code> rather than <code>== 'push'</code> because three watched
workflows are themselves <code>workflow_run</code>-triggered.
