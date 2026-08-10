---
id: eval-stats-could-never-publish
board: code
section: pipeline
status: shipped
category: Build · Bug
complexity: S
impact: Med
wow: 4
note: the published-metrics file has ONE commit in its whole history — the one that created it
order: 109
owner: fix/eval-stats-push-auth
pr:
title: The published metrics could never be published
---
<code>eval-stats.yml</code> regenerates <code>docs/eval-latest.json</code> — the payload the docs site
reads — commits it, and pushes to <code>main</code> on a schedule. The proof that it never landed is
in the file's own history: <b>one commit, ever</b>, the one that created it in
<code>#421</code>.

<b>The cause is a pair of individually-correct lines.</b> The checkout sets
<code>persist-credentials: false</code>, which is right and is what zizmor's
<code>artipacked</code> rule asks for. Ninety lines later the job runs
<code>git push origin HEAD:main</code>. With no persisted credentials the remote carries no auth, so
that push cannot work — and nothing in either line looks wrong on its own. The defect only exists
in the distance between them.

<b>It reported success while doing nothing, which is why it survived.</b> The step exits 0 early
when there is nothing to commit, so a run that found no metric drift and a run that could not
publish are the same green tick. Of the two scheduled runs, one passed that way and one failed —
and the failure was invisible for the same reason <code>fuzz</code> and <code>shards</code> were:
until <code>#508</code>, <code>ci-failure-issue.yml</code> watched 2 of 26 workflows, and a cron
job's failure is a red square on a page nobody opens.

<b>The fix was already in the repo.</b> <code>ci.yml</code> pushes its badges branch to an explicit
<code>x-access-token</code> URL — keeping the safe checkout default <i>and</i> being able to push.
The same three lines applied here. Nothing about the problem was novel; what was missing was anything
that compared the two workflows.

So the guard does that comparison. <code>tests/unit/test_workflow_push_has_credentials.py</code>
fails the build when a workflow checks out without persisting credentials and then pushes without
supplying any. It folds shell line-continuations before matching, because a push carrying a token in
its URL is long enough to wrap — matching per physical line would have failed the correct fix and
passed the broken one, which is the failure mode a guard can least afford. Both directions were
verified: green on the fix, and red again when the bare push is restored.
