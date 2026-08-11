---
id: zizmor-ignores-drift-and-make-lint-never-ran-it
board: code
section: pipeline
status: shipped
category: Build · Bug
complexity: S
impact: Med
wow: 4
note: a comment four lines long un-silenced a reviewed finding, and no local gate could see it
order: 110
owner: fix/parse-spec-control-chars
pr:
title: A line-anchored suppression drifted, and make lint never ran the tool
---
<code>.github/zizmor.yml</code> silences accepted workflow-SAST findings by
<b><code>file:LINE</code></b>. That anchor is fragile in a specific way: insert anything above the
construct and the ignore stops applying — or, worse, starts applying to a <i>different</i> construct
nobody reviewed.

It drifted here. Adding a header comment to <code>ci-failure-issue.yml</code> (explaining the
alerting-coverage fix) moved its <code>on:</code> block from <b>line 12 to line 28</b>, and CI's
<code>lint</code> job went red on <code>dangerous-triggers</code> — for a <code>workflow_run</code>
trigger that had been reviewed and accepted months earlier, with the reasoning written out in the
config right above the anchor.

<b>The config predicted it.</b> Its own note reads: <i>"these ignores are keyed by file:LINE, so
editing anything above a workflow's <code>on:</code> block moves it and silently un-ignores the
finding."</i> A warning in a comment is not a control — it depends on the next person reading the
file they are not editing.

<b>The second half is why nothing local caught it.</b> <code>make lint</code> <b>never ran
zizmor</b>. The recipe runs ruff, mypy, pyright, import-linter, vulture, xenon, interrogate, refurb,
codespell and actionlint — and CI's <code>lint</code> job additionally runs zizmor, which the
Makefile did not. So <code>make lint</code> could return <b>0</b> on a branch whose <code>lint</code>
job was already red, which is exactly what happened: the gate was run, it passed, and it had not
looked. (<code>CLAUDE.md</code> and an operator note both listed zizmor among the tools
<code>make lint</code> runs. Neither was true.)

Both halves are closed. zizmor now runs in <code>make lint</code>, guarded the same way actionlint
is — present, or an explicit "skipping (CI enforces it)" rather than silence — and
<code>--offline</code>, because the impostor and ref audits need GitHub API access the dev sandbox's
proxy flakes on.

And <code>tests/unit/test_zizmor_ignores_still_anchor.py</code> checks the cheap mechanical property
the line numbers depend on: every <code>dangerous-triggers</code> anchor still lands on an
<code>on:</code> line, no anchor points past the end of its file, no ignore names a workflow that no
longer exists, and no anchor is duplicated. It does not re-run zizmor — CI owns that — it asserts
that the anchors still mean what they say.

<b>Both fixes were verified by re-breaking the tree.</b> With the anchor put back to
<code>:12</code>, the new test goes red naming the drift, and <code>make lint</code> exits
<b>2</b> — the failure that previously only appeared in CI, now reproducible in one command before
the push.
