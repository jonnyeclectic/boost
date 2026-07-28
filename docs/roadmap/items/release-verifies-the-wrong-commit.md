---
id: release-verifies-the-wrong-commit
board: code
section: pipeline
status: planned
category: Release safety
complexity: S
impact: High
wow: 4
note: 2 of 18 required contexts are re-checked against the sha actually shipped
order: 64
owner:
pr:
title: The release verifies one commit and ships another
---
<code>publish.yml</code> fires on <code>workflow_run</code> when <code>ci</code> completes, gates
on that run's <code>conclusion == 'success'</code> (plus <code>event == 'push'</code> and
<code>head_repository == this repo</code>), and then checks out <code>ref: main</code>. Those are
not the same commit. <b>Observed 2026-07-28:</b> <code>ci</code> for <code>ecfe38bc</code>
completed at 20:19:05Z; the release run was created at 20:19:07Z; it tagged and shipped
<code>c1727bac</code> as <b>v1.0.271</b> &mdash; while <code>c1727bac</code>'s own
<code>ci</code>, started 20:18:40Z, was still <code>in_progress</code>. One commit's green
verdict authorised a different commit's release.

<b>Most of this is already mitigated, and the card should not be read as "untested code ships".</b>
A strict "require branches to be up to date" policy means the shipped commit was green as a pull
request before it could merge, so its <em>tree</em> was gated. And
<code>release_preflight.py</code> is already pointed at the right commit &mdash;
<code>--sha "$(git rev-parse HEAD)"</code>, with an explicit comment that this is "not the trigger
sha". It polls each required workflow for that exact sha and fails closed on red, cancelled,
skipped, never-ran or still-running-at-deadline. The machinery is correct.

<b>Its coverage is the gap.</b> <code>.github/required-checks.txt</code> lists <b>18</b> required
contexts. <code>publish.yml</code> passes preflight exactly two of them &mdash;
<code>--require pip-audit.yml</code> and <code>--require package-metadata.yml</code>. The other
<b>16 are never re-checked against the commit being shipped</b>, including all 14 that come from
<code>ci.yml</code> and <code>codeql-analyze</code>. The clearest evidence this is an oversight
rather than a decision is in-tree: <code>release_preflight.py</code>'s own docstring says it waits
for <em>every</em> required workflow for the exact commit being released, and the caller hands it
two.

<b>A required context that can never report on <code>main</code> at all.</b> While checking the
other 16: <code>osv-scanner.yml</code> declares only <code>pull_request</code> and
<code>merge_group</code> triggers &mdash; no <code>push</code>. So <code>scan-pr / osv-scan</code>
is green as a PR gate and produces <em>nothing</em> for any commit on <code>main</code>, race or
no race. Adding it to preflight without first giving that workflow a
<code>push: branches: [main]</code> trigger would fail the release closed every time.

The fix is not to change the checkout ref. Pinning to
<code>github.event.workflow_run.head_sha</code> would build the older commit while release-drafter
still tags the default branch's head &mdash; artifact and tag would disagree. The lower-risk
change is to widen preflight's <code>--require</code> set to the contexts that actually run on
<code>main</code>, and optionally fail the job when <code>git rev-parse HEAD</code> differs from
the triggering run's <code>head_sha</code>. This is the third defect found in the same few lines
&mdash; see <code>publish-trigger-was-reachable-from-a-fork</code> (who can fire it) and
<code>publish-gate-ignores-pip-audit-and-metadata</code> (which gates are consulted); this one is
<em>which commit</em> they were consulted about.
