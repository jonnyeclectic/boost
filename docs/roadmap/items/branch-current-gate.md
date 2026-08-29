---
id: branch-current-gate
board: code
section: health
status: inflight
category: CI · Release safety
complexity: S
impact: High
wow: 4
note: two protection mechanisms disagreed; the binding one had the safety off
order: 10
owner: loop/generated-freshness
pr:
title: main went red because "require branches up to date" was never actually on
---
Two pull requests, each green against the <code>main</code> it was tested on, merged into a
combination that turned <code>main</code> red. Their source files did not conflict. The
<b>generated</b> <code>docs/roadmap.html</code> did — and a squash merge takes one side of a
generated file <b>without ever reporting a conflict</b>. The board's "Loop finds" counter was
correct on both branches and wrong for their union.
<b>Seventeen jobs failed on one line.</b> Ten test legs, the lint job and all six mutation
shards — the shards because the unit suite runs inside <code>mutants/</code>, where
<code>test_roadmap_fresh</code> fails baseline <i>collection</i>, so a stale generated file
reads as "the mutation gate could not start". And because <code>ci</code> was red on
<code>main</code>, the release workflow's guard never armed: two merged pull requests, one of
them the reproducible-build pipeline, sat on <code>main</code> with no tag.
<b>The root cause was a setting, and the trap was that it looked set.</b> The repository asks
GitHub to require branches be up to date <b>twice</b>. Classic branch protection has
<code>strict: true</code> — and <code>enforce_admins: false</code>, so it does not apply to the
one account that merges. The active ruleset, which has no bypass actors and therefore does
apply, had <code>strict_required_status_checks_policy: false</code>. Two mechanisms, and the
binding one had the safety off. They also disagreed on how many checks are required: 14, 20,
and 21 in <code>required-checks.txt</code>.
<b>Fixed both ways.</b> The ruleset now enforces up-to-date merges, verified by reading it back
from the API rather than trusting the settings page. And <code>branch-current</code> is now a
required check, because that setting is invisible config that drifted once and can drift again
— a required check is in the diff, in <code>required-checks.txt</code>, and shows up in review.
Within minutes of the fix, GitHub moved two open pull requests to <code>behind</code> and
refused them; an hour earlier both would have merged and broken <code>main</code> a second time.
