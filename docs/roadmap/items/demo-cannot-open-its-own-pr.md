---
id: demo-cannot-open-its-own-pr
board: code
section: pipeline
status: planned
category: CI reporting
complexity: S
impact: Med
wow: 4
note: a repo setting blocks it — no edit to demo.yml can fix this one
order: 65
owner:
pr:
title: <code>demo.yml</code> still fails on every push &mdash; and the fix is not in the workflow
---
<code>demo-gif-workflow-has-never-succeeded</code> (shipped, PR&nbsp;294) fixed the recorder:
<code>charmbracelet/vhs-action</code>'s broken ffmpeg installer was replaced with apt plus
ttyd/vhs pinned by release-asset id. That worked. The recording step now succeeds on both event
paths. <b>The workflow still fails on every push to <code>main</code></b> &mdash; observed
2026-07-28 at 20:56, 20:04 and 09:27, and it is the only failing workflow in the last 60 runs.

The failure moved one step later, to <code>open a PR if the recording changed</code>. The run
annotation gives it verbatim:

<code>GitHub Actions is not permitted to create or approve pull requests.</code>

<b>Nothing in <code>demo.yml</code> is wrong, so nothing in <code>demo.yml</code> will fix it.</b>
The job already declares <code>contents: write</code> and <code>pull-requests: write</code>,
which is exactly what <code>peter-evans/create-pull-request</code> documents as required. The
workflow uses no secrets. <code>persist-credentials: false</code> on the checkout is correct and
is the repo-wide convention across all 31 checkout steps &mdash; the action supplies its own git
auth and explicitly unsets any persisted credential. Every one of those is a plausible-looking
false lead. The actual blocker is a <b>repository setting</b>: Actions&nbsp;&rarr;&nbsp;General
&nbsp;&rarr;&nbsp;Workflow permissions &nbsp;&rarr;&nbsp; "Allow GitHub Actions to create and
approve pull requests", which the API reports as
<code>can_approve_pull_request_reviews: false</code>. This is the same shape as
<code>sbom.yml</code>: a workflow that is correct in the file and inert in reality.

Deciding it is a real decision, not a formality. Turning that toggle on grants <em>every</em>
workflow in the repo the ability to open pull requests, which is a genuine widening of what a
compromised action can do. The alternative is to accept that this step cannot work and change
what the push path does &mdash; upload the GIF as an artifact on both paths, as the pull-request
path already does, and drop the PR-opening step.

<b>A second, independent defect in the same file.</b> Its concurrency group is
<code>group: demo</code>, not ref-scoped. Every other per-ref workflow scopes it &mdash;
<code>sonarcloud-${{ github.ref }}</code>, <code>fuzz-${{ github.ref }}</code>,
<code>eval-stats-${{ github.ref }}</code>, <code>eval-explain-${{ github.ref }}</code>; only the
deliberately-singleton <code>release</code> and <code>post-deploy</code> are global. With
<code>cancel-in-progress: true</code>, a pull-request run and a <code>main</code> run therefore
cancel each other, which is where demo's <code>cancelled</code> runs come from. Fix is
<code>group: demo-${{ github.ref }}</code> regardless of what is decided about the toggle.

Worth reconciling while here: the tree disagrees with itself on the history.
<code>demo-gif-workflow-has-never-succeeded</code> says "3 runs, 3 failures", while
<code>demo.yml</code> and <code>ci-failure-issue.yml</code> both say six of six.
<b>It is not only the demo any more.</b> [[scheduled-toolchain-lock-regeneration]] needs the same
permission: since <code>#349</code> switched off Dependabot's version updates for the pinned
toolchain, the replacement is a scheduled job that regenerates the lock and proposes it &mdash; and
that job cannot open a pull request either. So this toggle now gates two items rather than one, and
the second is a supply-chain freshness gap rather than a docs asset. That does not make the
decision automatic, but it does change what is on each side of it.

