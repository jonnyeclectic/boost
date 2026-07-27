---
id: merge-queue-would-deadlock-most-required-checks
board: code
section: pipeline
status: planned
category: Release safety
complexity: S
impact: Med
wow: 3
note: a latent trap, only if someone enables the queue
order: 58
owner:
pr:
title: Enabling a merge queue would deadlock every required check except ci.yml's
---
Only <code>ci.yml</code> declares <code>merge_group</code> among its triggers. The other
workflows producing required contexts — <code>codeql.yml</code>,
<code>pip-audit.yml</code>, <code>package-metadata.yml</code>, <code>osv-scanner.yml</code> —
run on <code>pull_request</code> only.

GitHub's merge queue evaluates the <b>required</b> checks against the temporary
<code>merge_group</code> ref, not against the pull request. So the moment a merge queue is
turned on, <code>codeql-analyze</code>, <code>pip-audit</code>, <code>metadata</code> and
<code>scan-pr / osv-scan</code> would never report on the queued ref and every enqueued PR
would sit forever — the same never-reports deadlock as
<code>required-checks-can-declare-a-check-that-deadlocks-prs</code>, arriving through a
different door.

Nothing is broken today; no merge queue is configured. Filed because the trap is invisible
until the switch is flipped, and because the pressure to flip it is real: with
<code>strict: true</code> and several concurrent loops, every merge forces every other open
PR to rebase and re-run its full matrix, which is exactly the problem merge queues solve.

Fix before enabling, not after: add <code>merge_group:</code> to each workflow that produces
a required context, and extend <code>scripts/check_required_checks.py</code> to fail when a
required name comes from a workflow lacking that trigger — the same gate that now catches
<code>paths:</code> filters.
